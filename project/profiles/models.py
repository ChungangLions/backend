from django.db import models
from accounts.models import User
from django.core.validators import MinValueValidator, MaxValueValidator

class PartnershipGoal(models.TextChoices):
        NEW_CUSTOMERS = "NEW_CUSTOMERS", "신규 고객 유입"
        REVISIT = "REVISIT", "재방문 증가"
        CLEAR_STOCK = "CLEAR_STOCK", "재고 소진"
        SPREAD_PEAK = "SPREAD_PEAK", "피크타임 분산"
        SNS_MARKETING = "SNS_MARKETING", "SNS 홍보"
        COLLECT_REVIEWS = "COLLECT_REVIEWS", "리뷰 확보"
        OTHER = "OTHER", "기타"

class BusinessType(models.TextChoices):
        RESTAURANT = 'RESTAURANT', '식당'
        CAFE = 'CAFE', '카페'
        BAR = 'BAR', '주점'

class Service(models.TextChoices):
        SIDE_MENU = 'SIDE_MENU', '사이드 메뉴'
        DRINK = 'DRINK', '음료수'
        OTHER = 'OTHERS', '기타'

class PartnershipRecord(models.TextChoices):
        TRUE = 'TRUE', '있음'
        FALSE = 'FALSE', '없음'


# ------ 사장님 프로필 ------
class OwnerProfile(models.Model):

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='owner_profile')
    
    # 주변 캠퍼스 
    campus_name = models.CharField(
        max_length = 100, blank=True, null=True,
        verbose_name="대학교명",
        help_text="검색으로 선택한 캠퍼스명"
    )


    # 업종
    business_type = models.CharField(
        max_length=20,
        choices=BusinessType.choices,
        blank=False,            
        db_index=True,                   
        verbose_name='업종',
        help_text='식당, 카페, 주점 중 하나'
    )

    # 가게명
    profile_name = models.CharField(max_length=30)

    # 영업일
    business_day = models.JSONField(
        default=dict, blank = False,
        help_text = '요일별 시간대 배열 JSON' # 예: {"월": ["09:00-15:00"], "수": ["18:00-24:00"]}
    )

    # 제휴 목표
    partnership_goal = models.CharField(
        max_length=20,
        choices=PartnershipGoal.choices,
        blank=False,            
        db_index=True,                   
        verbose_name='제휴 목표',
        help_text='신규 고객 유입, 재방문 증가, 재고 소진, 피크타임 분산, SNS 홍보, 리뷰 확보, 기타 중 하나'
    )
    partnership_goal_other = models.CharField(
        max_length=200, blank=True,
        verbose_name="기타 상세",
        help_text='제휴 목표가 기타(OTHER)일 때 상세'
    )

    # 평균 인당 매출
    average_sales = models.PositiveIntegerField(
        validators=[MinValueValidator(0)],
        help_text='원 단위'
    )

    # 마진율
    margin_rate = models.DecimalField(
        max_digits=5, decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text='0~100 사이 퍼센트'
    )

    # 바쁜 시간대
    peak_time = models.JSONField(
        default=list, blank=True,
        help_text='문자열 구간 배열' # 예 : ["11:00-14:00", "18:00-21:00"]
    )

    # 한산 시간대
    off_peak_time = models.JSONField(
        default=list, blank=True,
        help_text='문자열 구간 배열' # 예 : ["11:00-14:00", "18:00-21:00"]
    )

    # 추가 제공 가능 서비스
    available_service = models.CharField(
        max_length=20,
        choices=Service.choices,
        blank=False,             
        db_index=True,                   
        verbose_name='추가 제공 가능 서비스',
        help_text='음료수, 사이드 메뉴, 기타 중 하나'
    )
    available_service_other = models.CharField(
        max_length=200, blank=True,
        verbose_name="기타 상세",
        help_text='추가 제공 가능 서비스가 기타(OTHER)일 때 상세'
    )

    # 한줄소개
    comment = models.CharField(max_length=100)

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='생성일')
    modified_at = models.DateTimeField(auto_now=True, verbose_name='수정일')

    def __str__(self):
        return self.profile_name
    
    # 제휴 유형
    partnership_type = models.JSONField(
        default=list, blank=True,
        help_text='할인형, 리뷰형, 서비스제공형, 타임형 중 하나 이상' # 예 : ["할인형", "리뷰형"]   
    )
    
# 대표 사진 : 여러개 저장을 위해 별도 테이블 생성
class OwnerPhoto(models.Model):
    owner_profile = models.ForeignKey(
        OwnerProfile, on_delete=models.CASCADE, related_name="photos"
    )
    image = models.ImageField(upload_to="owner_profile/photos/")
    order = models.PositiveSmallIntegerField(
        default=0, help_text="표시 순서"
    )
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name='생성일')

    class Meta:
        ordering = ["order", "id"] # 쿼리셋 정렬 순서 order -> id
    
    def __str__(self):
        return f"{self.owner_profile.profile_name} - photo#{self.pk}"

# 대표 메뉴 : 여러개 저장을 위해 별도 테이블 생성
class Menu(models.Model):
    owner_profile = models.ForeignKey(
        OwnerProfile, on_delete=models.CASCADE, related_name="menus"
    )
    name = models.CharField(max_length=50)
    price = models.PositiveIntegerField(validators=[MinValueValidator(0)])
    image = models.ImageField(
        upload_to="owner_profile/menus/",
        blank=True, null=True,
    )
    order = models.PositiveSmallIntegerField(
        default=0, help_text="표시 순서"
    )

    class Meta:
        ordering = ["order", "id"] # 쿼리셋 정렬 순서 order -> id
        unique_together = [("owner_profile", "name")]  # 같은 상호 내 중복 메뉴명 방지

    def __str__(self):
        return f"{self.owner_profile.profile_name} - {self.name}"

class PartnershipTpye(models.Model):
    profile_id = models.ForeignKey(
    OwnerProfile, on_delete=models.CASCADE, related_name="partnership_type"
    )
    name = models.CharField(max_length=50)
    price = models.PositiveIntegerField(validators=[MinValueValidator(0)])
    image = models.ImageField(
        upload_to="owner_profile/menus/",
        blank=True, null=True,
    )
    order = models.PositiveSmallIntegerField(
        default=0, help_text="표시 순서"
    )

    class Meta:
        ordering = ["order", "id"] # 쿼리셋 정렬 순서 order -> id
        unique_together = [("owner_profile", "name")]  # 같은 상호 내 중복 메뉴명 방지

    def __str__(self):
        return f"{self.owner_profile.profile_name} - {self.name}"
     
     
    
# ------ 학생단체 프로필 ------
class StudentGroupProfile(models.Model):

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='student_group_profile')

    # 학교
    university_name = models.CharField(
        max_length=100, 
        blank=True, 
        null=True,
        verbose_name="소속대학교명",
        help_text="검색으로 선택한 대학교명 (예: 서울대학교)"
    )

    # 소속 
    council_name = models.CharField(
        max_length = 100, blank=True, null=True,
        help_text="소속된 학생회"
    )
    
    # 직책
    position = models.CharField(max_length=30)

    # 소속 단위 학생 수
    student_size = models.PositiveIntegerField(
        validators=[MinValueValidator(0)],
        help_text='명 단위'
    )

    # 임기
    term_start = models.DateField(verbose_name="임기 시작일")
    term_end = models.DateField(verbose_name="임기 종료일")
    
    # 제휴 기간
    partnership_start = models.DateField(verbose_name="제휴 시작일")
    partnership_end = models.DateField(verbose_name="제휴 종료일")

    # 제휴 이력
    partnership_record = models.CharField(
        max_length=5,
        choices=PartnershipRecord.choices,
        blank=False,            
        db_index=True,                   
        verbose_name='제휴 이력',
        help_text='있음, 없음 중 하나'
    )
    record_name = models.CharField(max_length=100, blank=True, verbose_name="제휴 업체명")
    record_start = models.DateField(verbose_name="제휴 시작일")
    record_end = models.DateField(verbose_name="제휴 종료일")

# 학생 단체 대표 사진 : 여러개 저장을 위해 별도 테이블 생성
class StudentPhoto(models.Model):
    owner_profile = models.ForeignKey(
        StudentGroupProfile, on_delete=models.CASCADE, related_name="photos"
    )
    image = models.ImageField(upload_to="student_group_profile/photos/")
    order = models.PositiveSmallIntegerField(
        default=0, help_text="표시 순서"
    )
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name='생성일')

    class Meta:
        ordering = ["order", "id"] # 쿼리셋 정렬 순서 order -> id
    
    def __str__(self):
        return f"{self.owner_profile.profile_name} - photo#{self.pk}"
