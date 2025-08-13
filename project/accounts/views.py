# accounts/views.py
from django.db.models import Count, Prefetch
from rest_framework import viewsets, mixins, status, permissions, filters, generics
from rest_framework.decorators import action
from rest_framework.response import Response

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

# 토큰 발급용
from rest_framework_simplejwt.views import TokenObtainPairView
from .serializers import EmailRoleAwareTokenObtainPairSerializer, RegisterSerializer

from .models import User, Like
from .serializers import (
    UserSerializer,
    MiniUserSerializer,
    LikeReadSerializer,
    LikeWriteSerializer,
    LikeToggleSerializer,
)

# 회원가입용 뷰셋
class RegisterView(generics.CreateAPIView):
    """
    회원가입: email, username(선택), password, password2, user_role(선택)
    성공 시 user + access/refresh 토큰 반환
    """
    permission_classes = [permissions.AllowAny]
    serializer_class = RegisterSerializer
# 로그인을 위한 뷰셋
class LoginView(TokenObtainPairView):
    serializer_class = EmailRoleAwareTokenObtainPairSerializer
class IsAuthenticatedOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_authenticated


class UserViewSet(viewsets.ReadOnlyModelViewSet):
    """
    사용자 목록/상세 조회
    - 필터링/검색/정렬 지원
    - 찜(좋아요) 토글/생성/삭제 커스텀 액션 제공
    """
    queryset = (
        User.objects
        .select_related()  # 확장 필드가 없으면 영향은 적지만 명시해 둠
        .prefetch_related(
            Prefetch('liked_targets', queryset=User.objects.only('id', 'username', 'user_role')),
            Prefetch('liked_by', queryset=User.objects.only('id', 'username', 'user_role')),
        )
        .annotate(
            likes_given_count=Count('likes_given', distinct=True),
            likes_received_count=Count('likes_received', distinct=True),
        )
    )
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['username', 'email']
    ordering_fields = ['date_joined', 'likes_received_count']
    ordering = ['-date_joined']

    # --- 목록/상세 문서화 ---
    @swagger_auto_schema(
        operation_summary="유저 목록 조회",
        operation_description="검색/정렬이 가능한 유저 목록을 반환합니다.",
        manual_parameters=[
            openapi.Parameter('search', openapi.IN_QUERY, description="username/email 검색", type=openapi.TYPE_STRING),
            openapi.Parameter('ordering', openapi.IN_QUERY, description="정렬 필드: date_joined, likes_received_count (예: -likes_received_count)", type=openapi.TYPE_STRING),
        ],
        responses={200: UserSerializer(many=True)},
        tags=["Users"],
        operation_id="listUsers",
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="유저 상세 조회",
        security=[{"Bearer": []}],
        responses={200: UserSerializer()},
        tags=["Users"],
        operation_id="retrieveUser",
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    # --- 찜 생성/삭제(REST 정석) ---
    @swagger_auto_schema(
        method='post',
        security=[{"Bearer": []}],
        operation_summary="특정 유저 찜 생성",
        operation_description="대상 유저를 찜합니다. 요청자는 인증 필요.",
        request_body=openapi.Schema(type=openapi.TYPE_OBJECT),  # body 없이 호출
        responses={
            201: openapi.Response("liked", schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    "status": openapi.Schema(type=openapi.TYPE_STRING, example="liked"),
                    "like_id": openapi.Schema(type=openapi.TYPE_INTEGER, example=123),
                }
            )),
            400: "유효성 오류",
            401: "인증 필요",
        },
        tags=["Likes"],
        operation_id="likeUser",
    )
    @swagger_auto_schema(
        method='delete',
        security=[{"Bearer": []}],
        operation_summary="특정 유저 찜 삭제",
        operation_description="대상 유저에 대한 찜을 해제합니다. 멱등(이미 없어도 204).",
        responses={204: "No Content", 401: "인증 필요"},
        tags=["Likes"],
        operation_id="unlikeUser",
    )
    # tests.py를 이용한 디버그, 액션 단위의 인증 요청
    @action(detail=True, methods=['post', 'delete'], url_path='like', permission_classes=[permissions.IsAuthenticated]) # 인증 강제
    def like(self, request, pk=None):
        if not request.user.is_authenticated:
            return Response({'detail': '인증 필요'}, status=status.HTTP_401_UNAUTHORIZED)

        target = self.get_object()
        if request.method.lower() == 'post':
            ser = LikeWriteSerializer(data={'target': target.id}, context={'request': request})
            ser.is_valid(raise_exception=True)
            like = ser.save()
            return Response({'status': 'liked', 'like_id': like.id}, status=status.HTTP_201_CREATED)

        obj = Like.objects.filter(user=request.user, target=target).first()
        if obj:
            obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    # --- 찜 토글(단일 엔드포인트 UX용) ---
    @swagger_auto_schema(
        method='post',
        operation_summary="특정 유저 찜 토글",
        operation_description="대상 유저에 대해 찜이 없으면 생성, 있으면 삭제합니다.",
        request_body=openapi.Schema(type=openapi.TYPE_OBJECT),
        responses={
            201: openapi.Response("liked", schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    "status": openapi.Schema(type=openapi.TYPE_STRING, example="liked"),
                    "like_id": openapi.Schema(type=openapi.TYPE_INTEGER, example=123),
                }
            )),
            200: openapi.Response("unliked", schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={"status": openapi.Schema(type=openapi.TYPE_STRING, example="unliked")}
            )),
            401: "인증 필요",
        },
        tags=["Likes"],
        operation_id="toggleLikeUser",
    )
    @action(detail=True, methods=['post'], url_path='like-toggle', permission_classes=[permissions.IsAuthenticated])
    def like_toggle(self, request, pk=None):
        if not request.user.is_authenticated:
            return Response({'detail': '인증 필요'}, status=status.HTTP_401_UNAUTHORIZED)

        target = self.get_object()
        ser = LikeToggleSerializer(data={'target': target.id}, context={'request': request})
        ser.is_valid(raise_exception=True)
        obj = ser.save()
        if obj is None:
            return Response({'status': 'unliked'}, status=status.HTTP_200_OK)
        return Response({'status': 'liked', 'like_id': obj.id}, status=status.HTTP_201_CREATED)


class LikeViewSet(mixins.CreateModelMixin,
                  mixins.DestroyModelMixin,
                  mixins.ListModelMixin,
                  viewsets.GenericViewSet):
    """
    찜 리소스 전용 뷰셋
    - GET /likes/             : 내가 누른 찜 목록 (기본)
      GET /likes/?mode=received : 내가 받은 찜 목록
    - POST /likes/            : 생성 (payload: {"target": <user_id>})
    - DELETE /likes/{id}/     : 삭제
    """
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        mode = self.request.query_params.get('mode', 'given')
        base = Like.objects.select_related('user', 'target')
        if mode == 'received':
            return base.filter(target=user).order_by('-created_at')
        return base.filter(user=user).order_by('-created_at')

    def get_serializer_class(self):
        if self.action in ('list', 'retrieve'):
            return LikeReadSerializer
        return LikeWriteSerializer

    @swagger_auto_schema(
        operation_summary="찜 목록 조회",
        operation_description="기본은 내가 누른 찜 목록. `?mode=received`로 내가 받은 찜 목록 조회.",
        manual_parameters=[
            openapi.Parameter('mode', openapi.IN_QUERY, type=openapi.TYPE_STRING,
                              enum=['given', 'received'], description="조회 모드"),
        ],
        responses={200: LikeReadSerializer(many=True)},
        tags=["Likes"],
        operation_id="listLikes",
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="찜 생성",
        request_body=LikeWriteSerializer,
        responses={201: LikeReadSerializer, 400: "유효성 오류"},
        tags=["Likes"],
        operation_id="createLike",
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="찜 삭제",
        operation_description="리소스형 삭제: /likes/{id}/",
        responses={204: "No Content"},
        tags=["Likes"],
        operation_id="deleteLike",
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.context.update({'request': self.request})
        serializer.save()
