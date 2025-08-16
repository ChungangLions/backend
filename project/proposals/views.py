from django.shortcuts import render
from django.db.models import Q, OuterRef, Subquery
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
)

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
    search_fields = ["title", "author__username", "recipient__username", "contact_info"]
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

        return qs

    def get_serializer_class(self):
        if self.action in ("list", "retrieve"):
            return ProposalReadSerializer
        return ProposalWriteSerializer

    # --- 생성/수정은 serializer에서 author/권한 검증 수행 ---
    def perform_create(self, serializer):
        # author는 serializer.validate에서 request.user 사용
        # user = self.request.user
        # recipient = serializer.validated_data['recipient']
        # serializer.save(
        #     author=user,
        #     sender_name=user.username,
        #     recipient_display_name=recipient.username,
        # )
        serializer.save()

    def perform_update(self, serializer):
        serializer.save()

    # --- 삭제: 작성자 & 미열람(UNREAD)일 때만 허용 ---
    @swagger_auto_schema(
        operation_summary="제안서 삭제",
        operation_description="작성자이며 제안서가 '미열람(UNREAD)' 상태일 때만 삭제 가능합니다.",
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
            openapi.Parameter("date_from", openapi.IN_QUERY, type=openapi.FORMAT_DATE, description="생성일 시작(YYYY-MM-DD)"),
            openapi.Parameter("date_to", openapi.IN_QUERY, type=openapi.FORMAT_DATE, description="생성일 종료(YYYY-MM-DD)"),
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
        # resp = super().create(request, *args, **kwargs)
        # # 생성 직후 상세 포맷으로 돌려주기
        # if resp.status_code == status.HTTP_201_CREATED:
        #     obj = Proposal.objects.get(pk=resp.data["id"])
        #     return Response(ProposalReadSerializer(obj, context={"request": request}).data, status=201)
        # return resp
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