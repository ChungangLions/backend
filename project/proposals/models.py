from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.db.models import Q, F
from accounts.models import User

# ----- 제휴 조건 보조 enum -----
# 제안이 적용되는 유형
class ApplyTarget(models.TextChoices):
    STUDENTS = "STUDENTS", "대학생 전체"
    GROUP_MEMBERS = "GROUP_MEMBERS", "학생단체 구성원"
    ALL_CUSTOMERS = "ALL_CUSTOMERS", "모든 손님"
    OTHER = "OTHER", "기타"

# 제안의 방식
class BenefitType(models.TextChoices):
    PERCENT_DISCOUNT = "PERCENT_DISCOUNT", "퍼센트 할인"
    AMOUNT_DISCOUNT  = "AMOUNT_DISCOUNT",  "정액 할인"
    FREE_ITEM        = "FREE_ITEM",        "무료 제공"
    OTHER            = "OTHER",            "기타"


# ----- 제안서 -----
class Proposal(models.Model):
    """
    제안서
    - 작성자(author): 학생단체(STUDENT_GROUP) 또는 사장님(OWNER)
    - 수신자(recipient): 작성자의 반대 역할(OWNER ↔ STUDENT_GROUP)
    - 프로필을 읽어 AI 생성할 수 있지만, 프롬프트 자체는 저장하지 않음
    - 필요한 내용: 제안 제목, 인삿말, 내용, 제휴(적용 대상, 혜택 내용, 적용 시간대, 제휴 기간), 기대 효과, 연락처 (담당자, 연락처)
    """

    # 작성자
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        limit_choices_to={'user_role__in': [User.Role.STUDENT_GROUP, User.Role.OWNER]},
        related_name='proposals_authored',
        verbose_name='작성자',
    )

    # 수신자 (역할은 author의 반대여야 함)
    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        limit_choices_to={'user_role__in': [User.Role.STUDENT_GROUP, User.Role.OWNER]},
        related_name='proposals_received',
        verbose_name='수신자',
    )

    
    # 표시용 이름(선택) — 담당자/상호 같은 텍스트 스냅샷
    sender_name = models.CharField(max_length=100, blank=True, verbose_name='발신인(표시용)')
    recipient_display_name = models.CharField(max_length=100, blank=True, verbose_name='수신자 표시명(스냅샷)')

    # 제안 본문
    title = models.CharField(max_length=120, verbose_name='제안 제목')
    contents = models.TextField(verbose_name='요청 개요')
    # partnership_purpose = models.TextField(verbose_name='제휴 목적') -> PM이 필요 없다고 한 부분
    expected_effects = models.TextField(verbose_name='기대 효과')
    partnership_type = models.JSONField(default = list, blank=True, verbose_name='제휴 방식', help_text='할인형, 리뷰형, 서비스제공형, 타임형 중 하나 이상')
    # 예: ["할인형", "리뷰형"]

    # 연락 정보
    contact_info = models.CharField(max_length=200, verbose_name='연락처')

    # === 제휴 조건 ===
    # 적용 대상에 대한 상세 정보를 주로 사용할 것으로 예상 함
    # 학생회 제휴이기 때문에 대체로 학생회 관련 인원을 대상으로 제휴를 할 가능성이 높음
    apply_target = models.CharField(
        max_length=40, choices=ApplyTarget.choices, default=ApplyTarget.GROUP_MEMBERS, db_index=True,
        verbose_name='적용 대상'
    )
    apply_target_other = models.CharField(
        max_length=200, blank=True, verbose_name='적용 대상(기타 상세)'
    )

    # 시간대는 유연하게 JSON 사용
    # 예: [{"days":["Mon","Tue"],"start":"14:00","end":"17:00"}]
    time_windows = models.JSONField(
        default=list, blank=True, verbose_name='적용 시간대'
    )

    # 혜택의 종류, 혜택 설명이 있기 때문에 사용하지 않을 수 있음
    benefit_type = models.CharField(
        max_length=30, choices=BenefitType.choices, default=BenefitType.PERCENT_DISCOUNT, db_index=True,
        verbose_name='혜택 유형'
    )
    
    # 혜택 설명, 수치로 적을 필요 없고 문장 형태로 작성
    benefit_description = models.CharField(
        max_length=250, blank=True, verbose_name='혜택 상세 설명(예: 무료 음료 1잔)'
    )

    # 제휴 기간
    # 기간은 선택적(제휴가 영구적일 수도 있으므로)
    period_start = models.DateField(null=True, blank=True, verbose_name='제휴 시작일')
    period_end   = models.DateField(null=True, blank=True, verbose_name='제휴 종료일')

    # min_order_amount        = models.PositiveIntegerField(null=True, blank=True, verbose_name='최소 결제 금액(원)')
    # max_redemptions_per_user = models.PositiveIntegerField(null=True, blank=True, verbose_name='1인 최대 사용 횟수')
    # max_total_redemptions    = models.PositiveIntegerField(null=True, blank=True, verbose_name='전체 최대 사용 횟수')

    # 시간 (제휴 제안서의 생성 및 수정 시각) ->> 생성일자를 기준으로 목록 정렬에 사용
    # 수정일자는 자동으로 갱신됨
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='생성일자')
    modified_at = models.DateTimeField(auto_now=True, verbose_name='수정일자')

    # 인삿말을 위한 함수
    def build_greeting(self):
        # 역할에 따라 약간씩 다르게
        # 사장님이 작성한 제안서의 경우, 학생회에 대한 감사 인사
        if self.author.user_role == User.Role.OWNER:
            to_who = "학생회"
            return (
            f"안녕하세요.\n"
            f"귀 {to_who}의 적극적인 학생 복지 및 교내 활동 지원에 항상 감사드립니다.\n"
            f"저희 업체는 학생들에게 더 나은 서비스를 제공하고자 , 아래와 같이 제휴를 제안드립니다.")
        else:
            # 학생회가 작성한 제안서의 경우, 사장님에 대한 존경 인사
            return (
            f"안녕하세요.\n"
            f"학생들의 학교생활과 지역 상권과의 상생을 위해, 귀 가게와의 제휴를 정중하게 요청드립니다\n"
            f"아래의 내용을 참고하시어 긍정적인 검토 부탁드립니다.")

    # 끝맺음말을 위한 함수
    def build_closing(self):
        name = (
            self.sender_name
            or (self.author.get_full_name() if hasattr(self.author, "get_full_name") else None)
            or self.author.username
            or (self.author.email or "")
        )
        contact = self.contact_info or ""
        return f"\n감사합니다.\n{name}\n{contact}"

    class Meta:
        verbose_name = '제안서'
        verbose_name_plural = '제안서들'
        ordering = ['-created_at']
        constraints = [
            # 자기 자신에게 보낼 수 없음
            models.CheckConstraint(check=~Q(author=F('recipient')), name='ck_proposal_no_self'),
        ]
        indexes = [
            models.Index(fields=['recipient']),
            models.Index(fields=['author', 'recipient']),
        ]

    # ---- 유효성 검증 ----
    def clean(self):
        # 역할 매칭: (학생회 → 사장님) 또는 (사장님 → 학생회)
        if self.author_id and self.recipient_id:
            pair = (self.author.user_role, self.recipient.user_role)
            valid_pairs = {
                (User.Role.STUDENT_GROUP, User.Role.OWNER),
                (User.Role.OWNER, User.Role.STUDENT_GROUP),
            }
            if pair not in valid_pairs:
                raise ValidationError({'recipient': '작성자와 수신자는 서로 반대 역할(학생단체 ↔ 사장님)이어야 합니다.'})

        # 기타 상세 필수
        if self.apply_target == ApplyTarget.OTHER and not self.apply_target_other:
            raise ValidationError({'apply_target_other': '적용 대상이 기타일 때 상세를 입력하세요.'})

        # 기간 검증
        if self.period_start and self.period_end and self.period_start > self.period_end:
            raise ValidationError({'period_end': '제휴 종료일은 시작일 이후여야 합니다.'})

        # FREE_ITEM/OTHER 는 값 없어도 OK

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        self.full_clean()
        super().save(*args, **kwargs)

        # 최초 생성 시 상태를 UNREAD로 기록
        if is_new:
            ProposalStatus.objects.create(
                proposal=self,
                status=ProposalStatus.Status.UNREAD,
                changed_by=self.recipient,  # "미열람" 상태의 소유자는 수신자 관점
                comment='제안서 초기 생성'
            )

    # ---- 편의 ----
    def __str__(self):
        a = "학생단체" if self.author.user_role == User.Role.STUDENT_GROUP else "사장님"
        b = "사장님" if self.recipient.user_role == User.Role.OWNER else "학생단체"
        return f"제안서({a}: {self.author.username} → {b}: {self.recipient.username})"

    @property
    def current_status(self):
        """현재 상태 코드 반환 (없으면 UNREAD)"""
        try:
            latest = self.status_history.latest('changed_at')
            return latest.status
        except ProposalStatus.DoesNotExist:
            return ProposalStatus.Status.UNREAD

    @property
    def current_status_object(self):
        """현재 상태 객체 반환 (없으면 None)"""
        try:
            return self.status_history.latest('changed_at')
        except ProposalStatus.DoesNotExist:
            return None

    @property
    def is_editable(self):
        # 작성자는 '미열람'일 때만 수정 가능하도록 예시
        return self.current_status == ProposalStatus.Status.UNREAD

    @property
    def is_partnership_made(self):
        return self.current_status == ProposalStatus.Status.PARTNERSHIP

    @transaction.atomic
    def change_status(self, new_status, changed_by, comment=''):
        """
        상태 변경 (권한 체크/전이 규칙은 ProposalStatus.clean()에서 검증)
        """
        ProposalStatus.objects.create(
            proposal=self,
            status=new_status,
            changed_by=changed_by,
            comment=comment
        )


# ----- 상태 이력 -----
class ProposalStatus(models.Model):
    """
    제안서 상태 이력
    UNREAD → READ → PARTNERSHIP/REJECTED
    REJECTED → UNREAD (재제출 허용)
    """
    class Status(models.TextChoices):
        UNREAD      = 'UNREAD',      '미열람'
        READ        = 'READ',        '열람'
        PARTNERSHIP = 'PARTNERSHIP', '제휴체결'
        REJECTED    = 'REJECTED',    '거절'

    proposal   = models.ForeignKey(Proposal, on_delete=models.CASCADE, related_name='status_history')
    status     = models.CharField(max_length=20, choices=Status.choices)
    changed_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='proposal_status_changes')
    changed_at = models.DateTimeField(auto_now_add=True)
    comment    = models.TextField(blank=True)

    class Meta:
        verbose_name = '제안서 상태'
        verbose_name_plural = '제안서 상태 히스토리'
        ordering = ['-changed_at']
        get_latest_by = 'changed_at'
        indexes = [
            models.Index(fields=['proposal', 'changed_at']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.proposal_id} - {self.get_status_display()} by {self.changed_by.username}"

    def clean(self):
        """
        상태 전이 규칙 + 주체 권한 간단 검증:
        - UNREAD → READ: 수신자만 가능(열람은 수신자의 행위)
        - READ → PARTNERSHIP/REJECTED: 수신자만 가능(수락/거절권자는 제안을 받은 쪽)
        - REJECTED → UNREAD: 작성자만 가능(재제출은 보낸 쪽)
        """
        if not self.proposal_id or not self.changed_by_id:
            return

         # ▶ 첫 상태라면 UNREAD만 허용하고 전이 검증은 스킵
        latest = self.proposal.status_history.order_by('-changed_at').first()
        if latest is None:
            if self.status != self.Status.UNREAD:
                raise ValidationError({'status': '첫 상태는 UNREAD여야 합니다.'})
            return
        
        curr = self.proposal.current_status
        nxt  = self.status
        author    = self.proposal.author
        recipient = self.proposal.recipient

        valid_transitions = {
            self.Status.UNREAD:      [self.Status.READ],
            self.Status.READ:        [self.Status.PARTNERSHIP, self.Status.REJECTED],
            self.Status.PARTNERSHIP: [],
            self.Status.REJECTED:    [self.Status.UNREAD],
        }
        if nxt not in valid_transitions.get(curr, []):
            raise ValidationError({'status': f'{curr} → {nxt} 전이는 허용되지 않습니다.'})

        # 전이의 주체 권한
        if curr == self.Status.UNREAD and nxt == self.Status.READ:
            if self.changed_by != recipient:
                raise ValidationError('열람(READ)은 수신자만 할 수 있습니다.')
        elif curr == self.Status.READ and nxt in (self.Status.PARTNERSHIP, self.Status.REJECTED):
            if self.changed_by != recipient:
                raise ValidationError('수락/거절은 수신자만 할 수 있습니다.')
        elif curr == self.Status.REJECTED and nxt == self.Status.UNREAD:
            if self.changed_by != author:
                raise ValidationError('재제출(UNREAD 복귀)은 작성자만 할 수 있습니다.')

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)