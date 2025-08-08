from rest_framework import serializers
from django.db import IntegrityError
from django.utils.translation import gettext_lazy as _
from .models import User, Like

# --- 유저의 경량 표현 (중첩을 이용해 재사용하기) ---
class MiniUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "user_role")


# --- 유저 상세/목록 공용 ---
class UserSerializer(serializers.ModelSerializer):
    # 읽기 전용 헬퍼/카운트
    is_owner = serializers.ReadOnlyField()
    is_student = serializers.ReadOnlyField()
    likes_given_count = serializers.SerializerMethodField()
    likes_received_count = serializers.SerializerMethodField()

    # N:N 읽기 (중첩/경량 표현) — write는 LikeSerializer로만 허용
    liked_targets = MiniUserSerializer(many=True, read_only=True)
    liked_by = MiniUserSerializer(many=True, read_only=True)

    class Meta:
        model = User
        fields = (
            "id", "username", "email", "user_role",
            "is_owner", "is_student",
            "created_at", "modified_at",
            "likes_given_count", "likes_received_count",
            "liked_targets", "liked_by",
        )
        read_only_fields = ("created_at", "modified_at")

    def get_likes_given_count(self, obj):
        return obj.likes_given.count()

    def get_likes_received_count(self, obj):
        return obj.likes_received.count()


# --- 찜(Like) 읽기용 ---
class LikeReadSerializer(serializers.ModelSerializer):
    user = MiniUserSerializer(read_only=True)
    target = MiniUserSerializer(read_only=True)

    class Meta:
        model = Like
        fields = ("id", "user", "target", "created_at")


# --- 찜(Like) 생성/삭제용 ---
class LikeWriteSerializer(serializers.ModelSerializer):
    """
    - 기본 패턴: 요청 보낸 주체가 user (request.user)
    - payload에는 보통 target만 넘기도록 설계 (user는 서버에서 주입)
    """
    user = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), required=False, write_only=True
    )
    target = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())

    class Meta:
        model = Like
        fields = ("id", "user", "target", "created_at")
        read_only_fields = ("id", "created_at")

    def validate(self, attrs):
        # user 주입(미제공 시 request.user 사용)
        request = self.context.get("request")
        if "user" not in attrs:
            if request and request.user and request.user.is_authenticated:
                attrs["user"] = request.user
            else:
                raise serializers.ValidationError(_("인증이 필요합니다!"))
        user = attrs["user"]
        target = attrs["target"]

        if user == target:
            raise serializers.ValidationError(_("자기 자신을 찜할 수 없습니다!"))

        return attrs

    def create(self, validated_data):
        try:
            # UniqueConstraint(uq_like_user_target) 위배시 IntegrityError
            return Like.objects.create(**validated_data)
        except IntegrityError:
            # 이미 존재하는 경우 친절한 메시지로 변환
            raise serializers.ValidationError(_("이미 찜한 사용자입니다!"))


# --- 한 줄짜리 엔드포인트용 시리얼라이저 (타겟만 받기) ---
class LikeToggleSerializer(serializers.Serializer):
    """
    /users/{id}/like/ 같은 커스텀 액션에 붙이기 좋음.
    - POST: like 생성
    - DELETE: like 제거 (뷰에서 처리)
    """
    target = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())

    def save(self, **kwargs):
        # create 전용 간이 버전
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError(_("인증이 필요합니다."))
        user = request.user
        target = self.validated_data["target"]
        if user == target:
            raise serializers.ValidationError(_("자기 자신을 찜할 수 없습니다."))
        obj, created = Like.objects.get_or_create(user=user, target=target)
        if not created:
            # 이미 있으면 그대로 반환 (id 포함)
            return obj
        return obj
