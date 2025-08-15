from django.db import models
from django.core.exceptions import ValidationError
from accounts.models import User

class Proposal(models.Model):
    '''
    제안서 모델
    - 학생단체(STUDENT_GROUP)와 사장님(OWNER) 모두 작성 가능
    - ChatGPT를 통해 프로필 기반 생성되고 사용자가 수정 가능
    '''
    
    # 제안서 작성자 (학생단체 또는 사장님)
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        limit_choices_to={'user_role__in': [User.Role.STUDENT_GROUP, User.Role.OWNER]},
        related_name='authored_proposals',
        verbose_name='제안서 작성자',
        help_text='제안서를 작성하는 학생단체 또는 사장님'
    )
    
    # 제안서 핵심 내용
    contents = models.TextField(
        verbose_name='요청 개요',
        help_text='제휴 요청의 전반적인 개요를 작성해주세요'
    )
    
    partnership_purpose = models.TextField(
        verbose_name='제휴 목적',
        help_text='이번 제휴를 통해 달성하고자 하는 목적을 작성해주세요'
    )
    
    expected_effects = models.TextField(
        verbose_name='기대 효과',
        help_text='제휴를 통해 기대되는 효과나 결과를 작성해주세요'
    )
    
    # 연락 정보
    contact_info = models.CharField(
        max_length=200,
        verbose_name='연락처',
        help_text='담당자 연락처 (전화번호, 이메일 등)'
    )
    
    sender = models.CharField(
        max_length=100,
        verbose_name='발신인',
        help_text='제안서를 보내는 학생단체명 또는 담당자명'
    )
    
    recipient = models.CharField(
        max_length=100,
        verbose_name='수신인',
        help_text='제안서를 받을 업체명 또는 담당자명'
    )
    '''
    와프 5.2.S 참고해서 보면
    업체 정보 관련해서 업종, 대표 사진, 업체명이 있는데 이건 그냥 프로필에서 가져오면 되겠지?
    그리고 제휴 조건 필드를 만들어야 할 듯? 적용 대상, 적용 시간대, 혜택 내용, 제휴 기간
    물론 이건 gpt 돌려서 입력받긴 하지만 필드는 만들어 놔야 하지 않을까
    '''

    # ChatGPT 생성 관련
    is_ai_generated = models.BooleanField(
        default=False,
        verbose_name='AI 생성 여부',
        help_text='ChatGPT를 통해 생성된 제안서인지 여부'
    )
    
    ai_prompt = models.TextField(
        blank=True,
        null=True,
        verbose_name='AI 생성 프롬프트',
        help_text='ChatGPT에 전달한 프롬프트 (디버깅 및 개선용)'
    )
    
    # 시간 관리
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='생성일자')
    modified_at = models.DateTimeField(auto_now=True, verbose_name='수정일자')
    
    class Meta:
        verbose_name = '제안서'
        verbose_name_plural = '제안서들'
        ordering = ['-created_at']
    
    def clean(self):
        """
        작성자 역할 검증
        """
        if self.author and self.author.user_role not in [User.Role.STUDENT_GROUP, User.Role.OWNER]:
            raise ValidationError({
                'author': '학생단체 또는 사장님만 제안서를 작성할 수 있습니다.'
            })
    
    def save(self, *args, **kwargs):
        is_new = self.pk is None
        self.clean()
        super().save(*args, **kwargs)
        
        # 새로 생성된 제안서라면 초기 상태 생성
        if is_new:
            ProposalStatus.objects.create(
                proposal=self,
                status=ProposalStatus.Status.UNREAD,
                changed_by=self.author,
                comment='제안서 초기 생성'
            )
    
    def __str__(self):
        author_type = "학생단체" if self.author.user_role == User.Role.STUDENT_GROUP else "사장님"
        return f"제안서 ({author_type}: {self.author.username} → {self.recipient})"
    
    @property
    def current_status(self):
        """현재 상태 반환"""
        latest_status = self.status_history.latest('changed_at')
        return latest_status.status if latest_status else ProposalStatus.Status.UNREAD
    
    @property
    def current_status_object(self):
        """현재 상태 객체 반환"""
        return self.status_history.latest('changed_at')
    
    @property
    def is_editable(self):
        """수정 가능 여부 확인"""
        return self.current_status == ProposalStatus.Status.UNREAD
    
    @property
    def is_partnership_made(self):
        """제휴체결 여부 확인"""
        return self.current_status == ProposalStatus.Status.PARTNERSHIP
    
    def change_status(self, new_status, changed_by, comment=''):
        """상태 변경 메서드"""
        ProposalStatus.objects.create(
            proposal=self,
            status=new_status,
            changed_by=changed_by,
            comment=comment
        )



class ProposalStatus(models.Model):
    '''
    제안서 상태 히스토리 모델
    - 제안서의 모든 상태 변경을 추적
    - 누가 언제 상태를 변경했는지 기록
    '''
    
    class Status(models.TextChoices):
        UNREAD = 'UNREAD', '미열람'
        READ = 'READ', '열람'
        PARTNERSHIP = 'PARTNERSHIP', '제휴체결'
        REJECTED = 'REJECTED', '거절'
    
    proposal = models.ForeignKey(
        Proposal,
        on_delete=models.CASCADE,
        related_name='status_history',
        verbose_name='제안서'
    )
    
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        verbose_name='상태'
    )
    
    changed_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='proposal_status_changes',
        verbose_name='상태 변경자',
        help_text='상태를 변경한 사용자'
    )
    
    changed_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='변경일시'
    )
    
    # 상태 변경 사유는 없어도 될듯?
    comment = models.TextField(
        blank=True,
        verbose_name='변경 사유/코멘트',
        help_text='상태 변경 사유, 거절 사유, 제휴 조건 등'
    )   
    class Meta:
        verbose_name = '제안서 상태'
        verbose_name_plural = '제안서 상태 히스토리'
        ordering = ['-changed_at']
        indexes = [
            models.Index(fields=['proposal', '-changed_at']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"{self.proposal} - {self.get_status_display()} ({self.changed_by.username})"
    
    def clean(self):
        """
        상태 변경 규칙 검증
        """
        # 4단계 상태 전이 규칙
        valid_transitions = {
            self.Status.UNREAD: [self.Status.READ],  # 미열람 → 열람
            self.Status.READ: [self.Status.PARTNERSHIP, self.Status.REJECTED],  # 열람 → 제휴체결 또는 거절
            self.Status.PARTNERSHIP: [],  # 제휴체결 (최종 상태)
            self.Status.REJECTED: [self.Status.UNREAD],  # 거절 → 재제출 가능 (미열람으로)
        }
        
        if self.proposal_id:
            current_status = self.proposal.current_status
            if current_status and self.status not in valid_transitions.get(current_status, []):
                raise ValidationError({
                    'status': f'{current_status}에서 {self.status}로 직접 변경할 수 없습니다.'
                })
    
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)