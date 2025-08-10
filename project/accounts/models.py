from django.db import models
from django.contrib.auth.models import AbstractUser, Group
from django.db.models import Q, F
from django.utils import timezone

# 사용자 정의 유저 모델
# - 역할: 사장님/학생단체를 구분 + (2025-08-10 추가): 학생 role도 추가
class User(AbstractUser):
    """
    기본 User 모델 확장: 역할/헬퍼/인덱스/스코프
    """
    class Role(models.TextChoices):
        OWNER = 'OWNER', '사장님'
        STUDENT_GROUP = 'STUDENT_GROUP', '학생단체'
        STUDENT = 'STUDENT', '학생'

    user_role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.OWNER,              #  기본값 (변경 가능)
        db_index=True,                   #  역할로 필터링 잦으면 인덱스
        verbose_name='사용자 역할',
        help_text='사장님, 학생단체, 학생 중 하나'
    )

    # 자기참조 M2M는 through로 관리 (시간/제약/확장성)
    liked_targets = models.ManyToManyField(
        'self',
        through='Like', # Like 모델을 통한 다대다 관계, Like 모델은 중간 계층의 모델
        through_fields=('user', 'target'),
        symmetrical=False,
        related_name='liked_by',
        blank=True,
        verbose_name='찜한 대상 목록'
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='생성일')
    modified_at = models.DateTimeField(auto_now=True, verbose_name='수정일')

    # ---- 헬퍼 프로퍼티 ----
    @property
    def is_owner(self) -> bool:
        return self.user_role == self.Role.OWNER

    @property
    def is_student_group(self) -> bool:
        return self.user_role == self.Role.STUDENT_GROUP

    @property
    def is_student(self) -> bool:
        return self.user_role == self.Role.STUDENT

    # 헬퍼 프로퍼티 사용 방법, 함수 처럼 사용 가능
    '''
    u = User.objects.get(username='Alice')

    if u.is_owner:
        print("사장님 권한 메뉴 노출")
    elif u.is_student_group:
        print("학생단체 권한 메뉴 노출")
    elif u.is_student:
        print("학생 권한 메뉴 노출")
    '''

    def __str__(self):
        return self.username


class Like(models.Model):
    """
    유저 간 찜 관계 (N:N) — through 테이블
    """
    user   = models.ForeignKey(User, on_delete=models.CASCADE, related_name='likes_given')
    target = models.ForeignKey(User, on_delete=models.CASCADE, related_name='likes_received')
    created_at = models.DateTimeField(auto_now_add=True)

    # Constraints: 유저 간 찜 관계는 유일해야 하며, 자기 자신을 찜할 수 없다.
    # Indexes: user와 user, target을 동시에 쿼리할 때 성능 향상
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'target'], name='uq_like_user_target'),
            models.CheckConstraint(check=~Q(user=F('target')), name='ck_like_no_self'),
        ]
        indexes = [
            models.Index(fields=['target']),
            models.Index(fields=['user', 'target']),
        ]

    ''' 
    Like 모델 사용 방법의 예시:
    
    # A가 B를 찜
    Like.objects.create(user=a, target=b)

    # A가 찜한 사람들(User)
    a.liked_targets.all()

    # B를 찜한 사람들(User)
    b.liked_by.all()

    # liked_targets와 liked_by는 User 모델에 의해 자동 생성된 역참조 이름이다.

    # A가 B를 찜했는지 여부
    Like.objects.filter(user=a, target=b).exists()

    # 내가 최근에 찜한 순
    User.objects.filter(liked_by=a).order_by('-like__created_at')  # through의 created_at 경유
    # (ORM이 through 모델 이름을 경로에 노출합니다. 안 되면 annotate/values로 우회)

    # 받은 찜 수 랭킹 정렬
    from django.db.models import Count
    User.objects.annotate(cnt=Count('likes_received')).order_by('-cnt')
    '''

    def __str__(self):
        return f'{self.user} → {self.target}' 