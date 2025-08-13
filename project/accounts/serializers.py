from rest_framework import serializers
from django.db import IntegrityError, transaction
from django.utils.translation import gettext_lazy as _
from .models import User, Like
from django.contrib.auth import get_user_model, password_validation

# 사용자 정의 토큰 발급 시리얼라이저
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()

class RegisterSerializer(serializers.ModelSerializer):
    # 비번 확인용 필드(선택) — 프론트에서 함께 보내면 검증
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})
    password2 = serializers.CharField(write_only=True, style={'input_type': 'password'})
    # user_role은 선택: 미보내면 서버 기본값(User.Role.OWNER) 사용
    user_role = serializers.ChoiceField(
        choices=User.Role.choices, required=False
    )

    class Meta:
        model = User
        fields = ("email", "username", "password", "password2", "user_role")

    def validate_email(self, value):
        # 이메일 중복(대소문자 무시) 방지 — DB 유니크가 없다면 앱 레벨에서 강제
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("이미 사용 중인 이메일입니다.")
        return value

    def validate(self, attrs):
        # 비밀번호 일치
        if attrs["password"] != attrs["password2"]:
            raise serializers.ValidationError({"password2": "비밀번호가 일치하지 않습니다."})

        # Django의 공식 비밀번호 정책 검증 (settings.AUTH_PASSWORD_VALIDATORS 참고)
        password_validation.validate_password(attrs["password"])
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password")
        validated_data.pop("password2", None)

        # username이 비어 있으면 이메일 앞부분으로 자동 생성(선택)
        if not validated_data.get("username"):
            email = validated_data.get("email", "")
            validated_data["username"] = (email.split("@")[0] or "user").lower()

        user = User(**validated_data)
        user.set_password(password)
        user.save()

        # 가입 직후 토큰 발급(선택)
        refresh = RefreshToken.for_user(user)
        return {
            "user": user,
            "refresh": str(refresh),
            "access": str(refresh.access_token),
        }

    def to_representation(self, instance):
        # create()에서 dict를 반환했으므로 여기서 직렬화 포맷을 정리
        user = instance["user"]
        return {
            "user": {
                "id": user.id,
                "email": user.email,
                "username": user.username,
                "user_role": user.user_role,
                "created_at": user.created_at,
            },
            "access": instance["access"],
            "refresh": instance["refresh"],
        }
class EmailRoleAwareTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    이메일 + 비밀번호로 로그인.
    - 요청 바디는 {"email": "...", "password": "..."}
    - 토큰 페이로드와 응답 바디에 user_role/username 포함
    """
    # 기본 TokenObtainPairSerializer는 USERNAME_FIELD를 사용하지만,
    # 우리는 email만 받기 위해 필드 자체를 재정의한다.
    email = serializers.EmailField(write_only=True)
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")
        invalid_msg = "이메일 또는 비밀번호가 올바르지 않습니다."

        if not email or not password:
            raise serializers.ValidationError(invalid_msg)

        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            raise serializers.ValidationError(invalid_msg)

        if not user.check_password(password):
            raise serializers.ValidationError(invalid_msg)
        if not user.is_active:
            raise serializers.ValidationError("비활성화된 계정입니다.")

        # ← super().validate({}) 호출하지 말고 직접 토큰 생성
        refresh = RefreshToken.for_user(user)

        # (선택) self.user를 세팅해두면 로그 등에서 참조 가능
        self.user = user

        return {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "user_role": user.user_role,
            "username": user.username,
        }

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["user_role"] = user.user_role
        token["username"] = user.username
        return token

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
    # user = serializers.PrimaryKeyRelatedField(
    #     queryset=User.objects.all(), required=False, write_only=True
    # )
    # target = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    target = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    class Meta:
        model = Like
        fields = ("id", "target", "created_at")
        read_only_fields = ("id", "created_at")

    def validate(self, attrs):
        # user 주입(미제공 시 request.user 사용)
        request = self.context.get("request")
        # if "user" not in attrs:
        #     if request and request.user and request.user.is_authenticated:
        #         attrs["user"] = request.user
        #     else:
        #         raise serializers.ValidationError(_("인증이 필요합니다!"))
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError(_("인증이 필요합니다!"))

        user = request.user
        target = attrs["target"]

        if user == target:
            raise serializers.ValidationError(_("자기 자신을 찜할 수 없습니다!"))

        if user.user_role == target.user_role:
            raise serializers.ValidationError(_("같은 역할의 사용자를 찜할 수 없습니다!"))

        return attrs

    def create(self, validated_data):
        user = validated_data["user"]
        target = validated_data["target"]
        try:
            with transaction.atomic():
                obj, created = Like.objects.get_or_create(user=user, target=target)
                if not created:
                    # 중복 생성 시 사용자 친화 에러
                    raise serializers.ValidationError(_("이미 찜한 사용자입니다!"))
                return obj
        except IntegrityError:
            # 경합 상황 대비
            raise serializers.ValidationError(_("이미 찜한 사용자입니다!"))
        # try:
        #     # UniqueConstraint(uq_like_user_target) 위배시 IntegrityError
        #     return Like.objects.create(**validated_data)
        # except IntegrityError:
        #     # 이미 존재하는 경우 친절한 메시지로 변환
        #     raise serializers.ValidationError(_("이미 찜한 사용자입니다!"))


# --- 한 줄짜리 엔드포인트용 시리얼라이저 (타겟만 받기) ---
class LikeToggleSerializer(serializers.Serializer):
    """
    /users/{id}/like/ 같은 커스텀 액션에 붙이기 좋음.
    - POST: like 생성
    - DELETE: like 제거 (뷰에서 처리)
    """
    target = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())

    def save(self, **kwargs):
        # 토글 기능: 있으면 삭제하고 None 반환, 없으면 생성해서 반환
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError(_("인증이 필요합니다."))
        user = request.user
        target = self.validated_data["target"]
        if user == target:
            raise serializers.ValidationError(_("자기 자신을 찜할 수 없습니다."))
        
        # 기존 찜이 있는지 확인
        try:
            existing_like = Like.objects.get(user=user, target=target)
            # 있으면 삭제하고 None 반환
            existing_like.delete()
            return None
        except Like.DoesNotExist:
            # 없으면 생성해서 반환
            return Like.objects.create(user=user, target=target)
