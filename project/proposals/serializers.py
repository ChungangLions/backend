# proposals/serializers.py
from django.db import transaction
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from accounts.models import User
from .models import (
    Proposal, ProposalStatus,
    ApplyTarget, BenefitType,
)

from profiles.models import StudentGroupProfile

# ---- 공용: 경량 유저 표현 ----
class MiniUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "user_role")
        ref_name = "ProposalMiniUser"


# ---- 상태 이력(Read) ----
class ProposalStatusReadSerializer(serializers.ModelSerializer):
    changed_by = MiniUserSerializer(read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = ProposalStatus
        fields = ("id", "status", "status_display", "changed_by", "changed_at", "comment")
        read_only_fields = fields


# ---- 제안서(Read) ----
class ProposalReadSerializer(serializers.ModelSerializer):
    author = MiniUserSerializer(read_only=True)
    recipient = MiniUserSerializer(read_only=True)
    current_status = serializers.SerializerMethodField()
    greeting = serializers.SerializerMethodField()
    closing = serializers.SerializerMethodField()
    status_history = ProposalStatusReadSerializer(many=True, read_only=True)
    is_editable = serializers.ReadOnlyField()
    is_partnership_made = serializers.ReadOnlyField()

    class Meta:
        model = Proposal
        fields = [
            # 식별/참조
            "id", "author", "recipient",
            # 스냅샷(표시용)
            "sender_name", "recipient_display_name",
            # 본문
            "title", "contents", "expected_effects", "partnership_type",
            # 연락
            "contact_info",
            # 제휴 조건
            "apply_target", "apply_target_other", "time_windows",
            "benefit_type", "benefit_description",
            "period_start", "period_end",
            # "min_order_amount", "max_redemptions_per_user", "max_total_redemptions",
            # 계산/메타
            "current_status", "greeting", "closing", "status_history",
            "is_editable", "is_partnership_made",
            "created_at", "modified_at",
        ]
        read_only_fields = [
            "id", "author", "recipient",
            "sender_name", "recipient_display_name",
            "current_status", "greeting", "closing", "status_history",
            "is_editable", "is_partnership_made",
            "created_at", "modified_at",
        ]

    def get_current_status(self, obj):
        return obj.current_status

    def get_greeting(self, obj):
        return obj.build_greeting()

    def get_closing(self, obj):
        return obj.build_closing()


# ---- 제안서(Write: 생성/수정) ----
class ProposalWriteSerializer(serializers.ModelSerializer):
    """
    - author는 request.user에서 자동 주입 (토큰 필요)
    - recipient만 PK로 입력
    """
    recipient = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())

    class Meta:
        model = Proposal
        fields = [
            "recipient",
            # 본문
            "title", "contents", "expected_effects", "partnership_type",
            # 연락
            "contact_info",
            # 제휴 조건
            "apply_target", "apply_target_other", "time_windows",
            "benefit_type", "benefit_description",
            "period_start", "period_end",
            # "min_order_amount", "max_redemptions_per_user", "max_total_redemptions",
        ]

    # --- 공통 검증 ---
    def validate(self, attrs):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError(_("인증이 필요합니다."))

        author = request.user
        recipient = attrs.get("recipient")

        # 역할 매칭: (학생회 → 사장님) 또는 (사장님 → 학생회)
        pair = (author.user_role, recipient.user_role)
        valid_pairs = {
            (User.Role.STUDENT_GROUP, User.Role.OWNER),
            (User.Role.OWNER, User.Role.STUDENT_GROUP),
        }
        if pair not in valid_pairs:
            raise serializers.ValidationError({"recipient": _("작성자와 수신자는 서로 반대 역할이어야 합니다.")})

        # 자기 자신 금지
        if author.pk == recipient.pk:
            raise serializers.ValidationError({"recipient": _("자기 자신에게 제안서를 보낼 수 없습니다.")})

        # 기타 상세 필수
        if attrs.get("apply_target") == ApplyTarget.OTHER and not attrs.get("apply_target_other"):
            raise serializers.ValidationError({"apply_target_other": _("적용 대상이 기타일 때 상세를 입력하세요.")})

        # 기간 검증
        ps, pe = attrs.get("period_start"), attrs.get("period_end")
        if ps and pe and ps > pe:
            raise serializers.ValidationError({"period_end": _("제휴 종료일은 시작일 이후여야 합니다.")})

        return attrs

    # --- 생성 ---
    def create(self, validated_data):
        request = self.context.get("request")
        author = request.user
        recipient = validated_data["recipient"]

        # 표시용 스냅샷 기본값
        sender_name = author.username or (author.email or "")
        recipient_display = recipient.username or (recipient.email or "")

        instance = Proposal(
            author=author,
            recipient=recipient,
            sender_name=sender_name,
            recipient_display_name=recipient_display,
            **{k: v for k, v in validated_data.items() if k != "recipient"},
        )
        # 모델의 clean()과 제약은 save()에서 full_clean으로 재확인
        instance.save()
        return instance

    # --- 수정 ---
    def update(self, instance, validated_data):
        request = self.context.get("request")
        user = request.user

        # 작성자만, 그리고 UNREAD일 때만 수정 가능(모델 속성 활용)
        if user != instance.author:
            raise serializers.ValidationError(_("작성자만 수정할 수 있습니다."))
        if not instance.is_editable:
            raise serializers.ValidationError(_("열람 이후에는 수정할 수 없습니다."))

        # recipient는 고정 (변경 불가)
        validated_data.pop("recipient", None)

        for k, v in validated_data.items():
            setattr(instance, k, v)
        instance.save()
        return instance


# ---- 상태 변경(Write) ----
class ProposalStatusChangeSerializer(serializers.ModelSerializer):
    """
    사용 예)
      POST /proposals/{id}/status/
      { "status": "READ", "comment": "확인했습니다" }
    - proposal은 view에서 context로 주입
    - changed_by는 request.user에서 자동 주입
    """
    status = serializers.ChoiceField(choices=ProposalStatus.Status.choices)

    class Meta:
        model = ProposalStatus
        fields = ("status", "comment")

    @transaction.atomic
    def create(self, validated_data):
        request = self.context.get("request")
        proposal = self.context["proposal"]

        obj = ProposalStatus(
            proposal=proposal,
            changed_by=request.user,
            **validated_data,
        )
        obj.save()  # clean() 내부에서 전이 규칙/권한을 검증

        if validated_data["status"] == "PARTNERSHIP":
            # 학생단체가 author인 경우
            if proposal.author.user_role == User.Role.STUDENT_GROUP:
                try:
                    profile = proposal.author.student_group_profile.get()
                    profile.partnership_count += 1
                    profile.save()
                except StudentGroupProfile.DoesNotExist:
                    pass  # 프로필 없으면 무시

            # 학생단체가 recipient인 경우
            elif proposal.recipient.user_role == User.Role.STUDENT_GROUP:
                try:
                    profile = proposal.recipient.student_group_profile.get()
                    profile.partnership_count += 1
                    profile.save()
                except StudentGroupProfile.DoesNotExist:
                    pass
        return obj