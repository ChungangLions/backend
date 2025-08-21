from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.db.models import OuterRef, Subquery
from .models import Proposal, ProposalStatus

# ---- inline: 상태 히스토리 ----
class ProposalStatusInline(admin.TabularInline):
    model = ProposalStatus
    extra = 0
    fields = ("status", "changed_by", "changed_at", "comment")
    readonly_fields = ("changed_at",)
    ordering = ("-changed_at",)


# ---- 리스트 필터: 현재 상태 ----
class LatestStatusFilter(admin.SimpleListFilter):
    title = "현재 상태"
    parameter_name = "latest_status"

    def lookups(self, request, model_admin):
        return ProposalStatus.Status.choices

    def queryset(self, request, queryset):
        latest_status_subq = (
            ProposalStatus.objects.filter(proposal=OuterRef("pk"))
            .order_by("-changed_at")
            .values("status")[:1]
        )
        qs = queryset.annotate(_latest_status=Subquery(latest_status_subq))
        if self.value():
            qs = qs.filter(_latest_status=self.value())
        return qs


@admin.register(Proposal)
class ProposalAdmin(admin.ModelAdmin):
    list_display = (
        "id", "author", "recipient",
        "current_status_admin", "created_at",
    )
    list_select_related = ("author", "recipient")
    list_filter = ("author__user_role", "recipient__user_role", LatestStatusFilter)
    search_fields = ("author__username", "recipient__username", "contact_info")
    ordering = ("-created_at",)
    date_hierarchy = "created_at"

    inlines = [ProposalStatusInline]

    readonly_fields = ("created_at", "modified_at")

    fieldsets = (
        ("기본 정보", {
            "fields": ("author", "recipient",
                       "sender_name", "recipient_display_name", "contact_info")
        }),
        ("본문", {"fields": ("expected_effects",)}),
        ("제휴 조건", {
            "fields": (
                "apply_target",
                "benefit_description",
                "time_windows", "partnership_type",
                "period_start", "period_end",
            )
        }),
        ("메타", {"fields": ("created_at", "modified_at")}),
    )

    # 현재 상태 표시 (annotate 없을 때도 안전)
    def current_status_admin(self, obj: Proposal):
        cs = obj.current_status
        return dict(ProposalStatus.Status.choices).get(cs, cs)
    current_status_admin.short_description = "현재 상태"

    # 일괄 액션들 (모델의 clean() 규칙을 따름)
    actions = ["act_mark_read", "act_mark_partnership", "act_mark_rejected", "act_reset_unread"]

    def _bulk_transition(self, request, queryset, to_status, who):
        """공통 유틸: 상태 전이. who='recipient' 또는 'author'."""
        ok, fail = 0, 0
        for p in queryset:
            changer = getattr(p, who)
            try:
                ProposalStatus.objects.create(
                    proposal=p,
                    status=to_status,
                    changed_by=changer,
                    comment=f"[Admin] {to_status}로 변경",
                )
                ok += 1
            except ValidationError as e:
                fail += 1
        if ok:
            self.message_user(request, f"{ok}건 변경 완료.", level=messages.SUCCESS)
        if fail:
            self.message_user(request, f"{fail}건은 전이 규칙에 맞지 않아 실패.", level=messages.WARNING)

    def act_mark_read(self, request, queryset):
        self._bulk_transition(request, queryset, ProposalStatus.Status.READ, "recipient")
    act_mark_read.short_description = "선택 항목을 '열람(READ)'으로"

    def act_mark_partnership(self, request, queryset):
        self._bulk_transition(request, queryset, ProposalStatus.Status.PARTNERSHIP, "recipient")
    act_mark_partnership.short_description = "선택 항목을 '제휴체결'로"

    def act_mark_rejected(self, request, queryset):
        self._bulk_transition(request, queryset, ProposalStatus.Status.REJECTED, "recipient")
    act_mark_rejected.short_description = "선택 항목을 '거절'로"

    def act_reset_unread(self, request, queryset):
        self._bulk_transition(request, queryset, ProposalStatus.Status.UNREAD, "author")
    act_reset_unread.short_description = "선택 항목을 '미열람'으로(재제출)"


@admin.register(ProposalStatus)
class ProposalStatusAdmin(admin.ModelAdmin):
    list_display = ("id", "proposal", "status", "changed_by", "changed_at")
    list_select_related = ("proposal", "changed_by")
    list_filter = ("status",)
    search_fields = (
        "proposal__author__username",
        "proposal__recipient__username",
        "changed_by__username",
    )
    ordering = ("-changed_at",)
    date_hierarchy = "changed_at"
