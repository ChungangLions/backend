from django.shortcuts import render
from django.db.models import Q, OuterRef, Subquery, Value
from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import Proposal, ProposalStatus
from .serializers import (
    ProposalReadSerializer,
    ProposalWriteSerializer,
    ProposalStatusChangeSerializer,
    ProposalSentListSerializer,
    ProposalReceivedListSerializer
)

# GPT를 이용한 제안서 생성 서비스
from profiles.serializers import OwnerProfileForAISerializer
from proposals.services.get_info import get_owner_profile_snapshot_by_user_id
from proposals.services.make_prompt import generate_proposal_from_owner_profile
from accounts.models import User
from profiles.models import OwnerProfile, StudentGroupProfile

# 필요한 view 목록
'''
1. 제안서 목록 조회 (작성 일자를 기준으로 정렬)
2. 제안서 상세 조회 (화면 UI에서 해당 제안서를 클릭 시 내용이 나올 수 있게 GET 요청)
3. 제안서 생성 (수동으로 생성을 하거나 GPT AI를 활용해서 생성할 수 있게 만들기)
4. 제안서 수정 (수정할 제안서를 선택하고, 수정 내용을 입력받아 업데이트)
5. 제안서 상태 변경 (제안서의 현재 상태를 확인하고, 새로운 상태로 변경) -> 거절, 수락 UI 버튼이 존재하며, 해당 버튼 클릭 시 상태 변경이 됨
6. 제안서 삭제 (제안서를 선택하고 삭제 요청을 처리)
7. 제안서 검색 (제안서 제목, 작성자, 작성일 등을 기준으로 검색할 수 있는 기능)
'''


# --- 객체 단위 권한: 작성자 또는 수신자만 접근 ---
class IsAuthorOrRecipient(permissions.BasePermission):
    def has_object_permission(self, request, view, obj: Proposal):
        u = request.user
        return u.is_authenticated and (u == obj.author or u == obj.recipient)


class ProposalViewSet(viewsets.ModelViewSet):
    """
    목록/상세/생성/수정/삭제 + 상태변경 액션 제공
    - 목록 기본 정렬: 최신 생성순(-created_at)
    - 기본 조회 범위: 내가 보낸/받은 제안서만
    """
    permission_classes = [permissions.IsAuthenticated, IsAuthorOrRecipient]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["author__username", "recipient__username", "contact_info"]
    ordering_fields = ["created_at", "modified_at", "id"]
    ordering = ["-created_at"]

    def get_queryset(self):
        user = self.request.user

        # 내가 보낸/받은 것만 기본 표시 (관리자는 전체 허용)
        qs = Proposal.objects.select_related("author", "recipient") \
                             .prefetch_related("status_history")
        if not user.is_staff:
            qs = qs.filter(Q(author=user) | Q(recipient=user))

        # 최신 상태를 annotation (status 필터에 사용)
        latest_status_subq = ProposalStatus.objects.filter(
            proposal=OuterRef("pk")
        ).order_by("-changed_at").values("status")[:1]
        # 이력이 없으면 DRAFT로 간주 (2025/08/23)
        qs = qs.annotate(latest_status=Subquery(latest_status_subq))

        # box 필터: inbox/sent/all (기본 all=양쪽)
        box = self.request.query_params.get("box", "all")
        if box == "inbox":
            qs = qs.filter(recipient=user)
        elif box == "sent":
            qs = qs.filter(author=user)

        # 상태 필터 (현재 상태 기준)
        status_param = self.request.query_params.get("status")
        if status_param:
            qs = qs.filter(latest_status=status_param)

        # 생성일 범위 필터 (YYYY-MM-DD)
        date_from = self.request.query_params.get("date_from")
        date_to = self.request.query_params.get("date_to")
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)

        # 수신자는 상대방의 DRAFT를 볼 수 없어야 함 (2025/08/23)
        if not user.is_staff:
            qs = qs.exclude(Q(recipient=user) & Q(latest_status=ProposalStatus.Status.DRAFT))

        return qs

    def get_serializer_class(self):
        if self.action in ("list", "retrieve"):
            return ProposalReadSerializer
        return ProposalWriteSerializer

    # --- 생성/수정은 serializer에서 author/권한 검증 수행 ---
    def perform_create(self, serializer):
        serializer.save()

    def perform_update(self, serializer):
        serializer.save()

    # --- 삭제: 작성자 & 미열람(UNREAD)일 때만 허용 ---
    @swagger_auto_schema(
        operation_summary="제안서 삭제",
        operation_description="작성자이며 제안서가 '미열람(UNREAD)' 상태 혹은 '초안(DRAFT)' 상태일 때만 삭제 가능합니다.",
        responses={204: "No Content", 400: "Bad Request", 403: "Forbidden"},
        tags=["Proposals"],
    )
    def destroy(self, request, *args, **kwargs):
        obj: Proposal = self.get_object()
        if request.user != obj.author:
            return Response({"detail": "작성자만 삭제할 수 있습니다."}, status=status.HTTP_403_FORBIDDEN)
        if not obj.is_editable:
            return Response({"detail": "열람 이후에는 삭제할 수 없습니다."}, status=status.HTTP_400_BAD_REQUEST)
        return super().destroy(request, *args, **kwargs)

    # --- 상태 변경 액션 ---
    @swagger_auto_schema(
        method="post",
        operation_summary="제안서 상태 변경",
        operation_description=(
            "현재 상태를 변경합니다.\n"
            "- UNREAD → READ: 수신자만\n"
            "- READ → PARTNERSHIP/REJECTED: 수신자만\n"
            "- REJECTED → UNREAD: 작성자만 (재제출)\n"
        ),
        request_body=ProposalStatusChangeSerializer,
        responses={200: ProposalReadSerializer, 400: "유효성 오류", 403: "권한 없음"},
        tags=["Proposals"],
    )
    @action(detail=True, methods=["post"], url_path="status")
    def change_status(self, request, pk=None):
        proposal = self.get_object()  # IsAuthorOrRecipient로 기본 접근 제한
        ser = ProposalStatusChangeSerializer(
            data=request.data,
            context={"request": request, "proposal": proposal},
        )
        ser.is_valid(raise_exception=True)
        ser.save()
        # 변경 후 최신 상태를 포함한 상세 반환
        return Response(ProposalReadSerializer(proposal, context={"request": request}).data)

    # ---- Swagger 문서화(목록/상세/생성/수정) ----
    @swagger_auto_schema(
        operation_summary="제안서 목록 조회",
        operation_description="내가 보낸/받은 제안서를 최신 생성순으로 반환합니다.",
        manual_parameters=[
            openapi.Parameter("box", openapi.IN_QUERY, type=openapi.TYPE_STRING,
                              enum=["all", "inbox", "sent"],
                              description="all(기본)=전체, inbox=받은함, sent=보낸함"),
            openapi.Parameter("status", openapi.IN_QUERY, type=openapi.TYPE_STRING,
                              enum=[c for c, _ in ProposalStatus.Status.choices],
                              description="현재 상태로 필터"),
            openapi.Parameter("date_from", openapi.IN_QUERY, type=openapi.TYPE_STRING, format=openapi.FORMAT_DATE, description="생성일 시작(YYYY-MM-DD)"),
            openapi.Parameter("date_to", openapi.IN_QUERY, type=openapi.TYPE_STRING, format=openapi.FORMAT_DATE, description="생성일 종료(YYYY-MM-DD)"),
            openapi.Parameter("search", openapi.IN_QUERY, type=openapi.TYPE_STRING,
                              description="제목/작성자/수신자/연락처 검색"),
            openapi.Parameter("ordering", openapi.IN_QUERY, type=openapi.TYPE_STRING,
                              description="정렬 필드: created_at, modified_at (예: -created_at)"),
        ],
        responses={200: ProposalReadSerializer(many=True)},
        tags=["Proposals"],
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="제안서 상세 조회",
        responses={200: ProposalReadSerializer},
        tags=["Proposals"],
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="제안서 생성",
        request_body=ProposalWriteSerializer,
        responses={201: ProposalReadSerializer, 400: "유효성 오류"},
        tags=["Proposals"],
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        instance = serializer.instance  # ✅ 방금 저장된 객체
        out = ProposalReadSerializer(instance, context=self.get_serializer_context())
        headers = self.get_success_headers(out.data)
        return Response(out.data, status=status.HTTP_201_CREATED, headers=headers)

    @swagger_auto_schema(
        operation_summary="제안서 수정",
        request_body=ProposalWriteSerializer,
        responses={200: ProposalReadSerializer, 400: "유효성 오류", 403: "권한 없음"},
        tags=["Proposals"],
    )
    def update(self, request, *args, **kwargs):
        resp = super().update(request, *args, **kwargs)
        if resp.status_code in (status.HTTP_200_OK, status.HTTP_202_ACCEPTED):
            obj = self.get_object()
            return Response(ProposalReadSerializer(obj, context={"request": request}).data)
        return resp

    @swagger_auto_schema(
        operation_summary="제안서 부분 수정",
        request_body=ProposalWriteSerializer,
        responses={200: ProposalReadSerializer, 400: "유효성 오류", 403: "권한 없음"},
        tags=["Proposals"],
    )
    def partial_update(self, request, *args, **kwargs):
        resp = super().partial_update(request, *args, **kwargs)
        if resp.status_code in (status.HTTP_200_OK, status.HTTP_202_ACCEPTED):
            obj = self.get_object()
            return Response(ProposalReadSerializer(obj, context={"request": request}).data)
        return resp
    

    #--- GPT 기반 제안서 자동 생성 액션 ---
    @swagger_auto_schema(
        method='post',
        operation_summary="(AI) 사장님 프로필 기반 제안서 자동 생성",
        tags=["Proposals"],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["recipient"],
            properties={
                "recipient": openapi.Schema(type=openapi.TYPE_INTEGER, description="사장님(User.id)"),
                "contact_info": openapi.Schema(type=openapi.TYPE_STRING, description="작성자 연락처(선택; 미지정 시 학생 프로필의 연락처를 사용)"),
            }
        ),
        responses={201: ProposalReadSerializer()},
        security=[{"Bearer": []}],
    )
    @action(detail=False, methods=['post'], url_path='ai-draft')
    def ai_draft(self, request):
        """
        - request.user: 작성자(학생단체)
        - recipient: 사장님(User.id) — 이 사장님의 OwnerProfile을 읽어 제안서 초안 생성
        """
        recipient_id = request.data.get("recipient")
        if not recipient_id:
            return Response({"detail": "recipient는 필수입니다."}, status=400)

        # 수신자 존재/역할 체크
        try:
            recipient = User.objects.get(pk=recipient_id)
        except User.DoesNotExist:
            return Response({"detail": "수신자(유저)가 존재하지 않습니다."}, status=404)

        # 여기선 '사장님 프로필 기반'이므로 수신자가 OWNER인지 확인
        if recipient.user_role != User.Role.OWNER:
            return Response({"detail": "수신자는 사장님(OWNER)이어야 합니다."}, status=400)

        # 사장님 프로필 스냅샷 추출
        try:
            profile_dict = get_owner_profile_snapshot_by_user_id(recipient_id)
        except OwnerProfile.DoesNotExist:
            return Response({"detail": "수신자 사장님의 프로필이 없습니다."}, status=400)


        # 작성자의 정보에서 author_contact를 profiles에서 id랑 매칭 후 가져와야함.
        # 작성자 정보 (작성자는 여기선 학생단체임)
        author = request.user
        author_name = author.username or (author.email or "")

        # 2025/08/22 코드 추가 내용 (학생회 프로필에서 값을 가져와 author_contact에 할당)
        body_contact = (request.data.get("contact_info") or "").strip()
        if body_contact: # 프론트에서 body에 값이 있다면 그것을 사용
            author_contact = body_contact
        else: # 프론트에서 body 값이 없다면 학생 프로필 모델의 contact 필드의 값을 가져옴
            author_contact = (
                StudentGroupProfile.objects
                .filter(user=author)
                .values_list("contact", flat=True)
                .first()
            ) or ""
                
        # GPT 호출 → 초안(JSON)
        ai_dict = generate_proposal_from_owner_profile(
            owner_profile=profile_dict,
            author_name=author_name,
            author_contact=author_contact,
        )

        # 서버에서 recipient 주입 후, 표준 WriteSerializer로 검증/생성
        ai_dict["recipient"] = recipient_id
        serializer = ProposalWriteSerializer(data=ai_dict, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            ProposalReadSerializer(serializer.instance, context={"request": request}).data,
            status=status.HTTP_201_CREATED
        )
        
    @swagger_auto_schema(
    method='post',
    operation_summary="(AI) 사장님 → 학생단체 제안서 자동 생성",
    operation_description=(
        "- 작성자가 반드시 사장님(OWNER)이어야 합니다.\n"
        "- recipient는 학생단체(STUDENT_GROUP) 유저의 id여야 하며, contact_info는 미입력시 작성자의 이메일이 자동 저장됩니다.\n"
        "- 작성자의 OwnerProfile 기반으로 AI가 제안서 초안을 생성합니다.\n"
        "- 성공 시 생성된 제안서 객체를 반환합니다."
    ),
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["recipient"],
        properties={
            "recipient": openapi.Schema(
                type=openapi.TYPE_INTEGER,
                description="학생단체(User.id, 필수)"
            ),
            "contact_info": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="작성자 연락처(선택; 미입력 시 사장님 프로필에 저장된 연락처를 사용함)"
            ),
        },
        example={
            "recipient": 42,
            "contact_info": "010-xxxx-xxxx 혹은 비어있는 string"
        }
    ),
    responses={
        201: openapi.Response(
            "AI가 생성한 제안서 예시",
            ProposalReadSerializer,
            examples={
                "application/json": {
                    "id": 123,
                    "author": 10,
                    "recipient": 42,
                    "contact_info": "010-xxxx-xxxx",
                    "created_at": "2025-08-20T07:00:00Z",
                    "status": "UNREAD",
                }
            }
        ),
        400: openapi.Response(
            description="필수 파라미터 누락, 역할 불일치, 프로필 없음 등",
            examples={"application/json": {"detail": "recipient는 필수입니다."}}
        ),
        403: openapi.Response(
            description="작성자 권한 없음",
            examples={"application/json": {"detail": "작성자는 사장님(OWNER)이어야 합니다."}}
        ),
        404: openapi.Response(
            description="수신자 없음",
            examples={"application/json": {"detail": "수신자(유저)가 존재하지 않습니다."}}
        ),
    },
    security=[{"Bearer": []}],
    tags=["Proposals"],
    )
    @action(detail=False, methods=['post'], url_path='ai-draft-to-student')
    def ai_draft_to_student(self, request):
        """
        - request.user: 작성자(사장님) - 작성자가 사장님이지만 제안서의 input으로 들어가는 데이터는 사장님의 프로필이다.
        - recipient: 학생단체(User.id)
        - AI 입력은 '작성자(사장님)의 OwnerProfile' 스냅샷을 사용
        """
        recipient_id = request.data.get("recipient")
        if not recipient_id:
            return Response({"detail": "recipient는 필수입니다."}, status=400)

        # 수신자 존재/역할 체크
        try:
            recipient = User.objects.get(pk=recipient_id)
        except User.DoesNotExist:
            return Response({"detail": "수신자(유저)가 존재하지 않습니다."}, status=404)

        # 학생단체 역할 확인 (❗ STUDENT_GROUP 이 맞습니다)
        if recipient.user_role != User.Role.STUDENT_GROUP:
            return Response({"detail": "수신자는 학생단체(STUDENT_GROUP)이어야 합니다."}, status=400)

        # 작성자(사장님)의 OwnerProfile 스냅샷 추출 (수신자 아님!)
        author = request.user
        try:
            profile_dict = get_owner_profile_snapshot_by_user_id(author.id)
        except OwnerProfile.DoesNotExist:
            return Response({"detail": "작성자(사장님)의 프로필이 없습니다."}, status=400)

        # 작성자 정보
        # 사장 프로필의 contact을 사용하는 것이 나음 -> 수정을 해야 함 (2025/08/22)
        author = request.user
        author_name = author.username or (author.email or "")
        # author_contact = request.data.get("contact_info") or author.email or ""

        body_contact = (request.data.get("contact_info") or "").strip()
        if body_contact: # 프론트에서 body에 값이 있다면 그것을 사용
            author_contact = body_contact
        else: # 프론트에서 body 값이 없다면 사장님 프로필 모델의 contact 필드의 값을 가져옴
            author_contact = (
                OwnerProfile.objects
                .filter(user=author)
                .values_list("contact", flat=True)
                .first()
            ) or ""

        # GPT 호출 → 초안(JSON)
        ai_dict = generate_proposal_from_owner_profile(
            owner_profile=profile_dict,
            author_name=author_name,
            author_contact=author_contact,
        )

        # 서버에서 recipient 주입 후, 표준 WriteSerializer로 검증/생성
        ai_dict["recipient"] = recipient_id
        serializer = ProposalWriteSerializer(data=ai_dict, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            ProposalReadSerializer(serializer.instance, context={"request": request}).data,
            status=status.HTTP_201_CREATED
        )            
    
    @swagger_auto_schema(
        method='get',
        operation_summary="특정 유저가 보낸(작성한) 제안서 목록",
        operation_description="경로의 user_id가 작성자인 제안서들을 작성일 내림차순으로 반환합니다.",
        responses={200: ProposalSentListSerializer(many=True)},
        tags=["Proposals"],
        manual_parameters=[
            openapi.Parameter(
                name="user_id",
                in_=openapi.IN_PATH,
                description="작성자(User) ID",
                type=openapi.TYPE_INTEGER,
                required=True,
            ),
        ],
        security=[{"Bearer": []}],
    )
    @action(detail=False, methods=["get"], url_path=r"send/(?P<user_id>\d+)",
            permission_classes=[permissions.IsAuthenticated])
    def sent_by_user(self, request, user_id=None):
        # 유저 검증 (존재하지 않으면 404)
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return Response({"detail": "해당 사용자가 존재하지 않습니다."}, status=status.HTTP_404_NOT_FOUND)

        # 해당 유저가 작성한 제안서만 (최신순)
        qs = (
            Proposal.objects
            .filter(author=user)
            .only("id", "partnership_type", "created_at", "modified_at")
            .order_by("-created_at")
        )

        data = ProposalSentListSerializer(qs, many=True).data
        return Response(data, status=status.HTTP_200_OK)
    
    @swagger_auto_schema(
        method='get',
        operation_summary="특정 유저가 받은 제안서 목록",
        operation_description="경로의 user_id가 제안 수신인인 제안서들을 작성일 내림차순으로 반환합니다.",
        responses={200: ProposalReceivedListSerializer(many=True)},
        tags=["Proposals"],
        manual_parameters=[
            openapi.Parameter(
                name="user_id",
                in_=openapi.IN_PATH,
                description="작성자(User) ID",
                type=openapi.TYPE_INTEGER,
                required=True,
            ),
        ],
        security=[{"Bearer": []}],
    )
    @action(detail=False, methods=["get"], url_path=r"received/(?P<user_id>\d+)",
            permission_classes=[permissions.IsAuthenticated])
    def received_by_user(self, request, user_id=None):
        # 유저 검증 (존재하지 않으면 404)
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return Response({"detail": "해당 사용자가 존재하지 않습니다."}, status=status.HTTP_404_NOT_FOUND)

        # 해당 유저가 작성한 제안서만 (최신순)
        qs = (
            Proposal.objects
            .filter(recipient=user)
            .only("id", "partnership_type", "created_at", "modified_at")
            .order_by("-created_at")
        )

        data = ProposalReceivedListSerializer(qs, many=True).data
        return Response(data, status=status.HTTP_200_OK)