from django.db import models
from django.contrib.auth.models import AbstractUser

# 사용자 정의 User 모델
class User(AbstractUser):
    class Role(models.TextChoices):
        OWNER = 'OWNER', '사장님'
        STUDENT = 'STUDENT_GROUP', '학생단체'

    # 기본 필드(username, password, email 등)는 AbstractUser에 이미 포함되어 있음
    user_role = models.CharField(
        max_length=20,
        choices=Role.choices,
        verbose_name='사용자 역할'
    )

    # 찜(좋아요) 기능을 위한 다대다 관계
    # 'self'는 User 모델 자신을 가리킴
    # symmetrical=False는 A가 B를 찜해도 B가 A를 찜한 것은 아님을 의미
    liked_targets = models.ManyToManyField(
        'self',
        symmetrical=False,
        related_name='liked_by',
        blank=True,
        verbose_name='찜한 대상 목록'
    )

    # 1. 내가 찜한 목록 가져오기
    # 'user_A'라는 유저 객체를 가져옵니다.
    #user_a = User.objects.get(username='user_A')
    # user_A가 찜한 모든 유저 목록(QuerySet)을 가져옵니다.
    # Django가 내부적으로 중개 테이블을 JOIN하여 처리합니다.
    # my_liked_list = user_a.liked_targets.all()
    #
    # 출력:
    # user_B
    # user_C

    # 2. 나를 찜한 목록 가져오기
    # 'user_B'라는 유저 객체를 가져옵니다.
    # user_b = User.objects.get(username='user_B')
    # user_B를 찜한 모든 유저 목록(QuerySet)을 가져옵니다.
    # users_who_like_me = user_b.liked_by.all()
    # for fan in users_who_like_me:
    #     print(fan.username)
    # 출력:
    # user_A

    # 3. 찜과 관련된 관계 추가 및 삭제
    # user_A가 user_D를 추가로 찜하기
    # user_d = User.objects.get(username='user_D')
    # user_a.liked_targets.add(user_d)
    # user_A가 user_B 찜하기를 취소
    # user_b = User.objects.get(username='user_B')
    # user_a.liked_targets.remove(user_b)

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='생성일')
    modified_at = models.DateTimeField(auto_now=True, verbose_name='수정일')

    def __str__(self):
        return self.username