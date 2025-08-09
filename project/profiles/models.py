from django.db import models
from accounts.models import User
from django.core.validators import MinValueValidator, MaxValueValidator

class PartnershipGoal(models.TextChoices):
        NEW_CUSTOMERS = "NEW_CUSTOMERS", "�ű� �� ����"
        REVISIT = "REVISIT", "��湮 ����"
        CLEAR_STOCK = "CLEAR_STOCK", "��� ����"
        SPREAD_PEAK = "SPREAD_PEAK", "��ũŸ�� �л�"
        SNS_MARKETING = "SNS_MARKETING", "SNS ȫ��"
        COLLECT_REVIEWS = "COLLECT_REVIEWS", "���� Ȯ��"
        OTHER = "OTHER", "��Ÿ"

class BusinessType(models.TextChoices):
        RESTAURANT = 'RESTAURANT', '�Ĵ�'
        CAFE = 'CAFE', 'ī��'
        BAR = 'BAR', '����'

class Service(models.TextChoices):
        SIDE_MENU = 'SIDE_MENU', '���̵� �޴�'
        DRINK = 'DRINK', '�����'
        OTHER = 'OTHERS', '��Ÿ'

class PartnershipRecord(models.TextChoices):
        TRUE = 'TRUE', '����'
        FALSE = 'FALSE', '����'


# ------ ����� ������ ------
class OwnerProfile(models.Model):

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='owner_profile')
    '''
    # �ֺ� ķ�۽� 
    campus_name = models.CharField(
        max_length = 100, blank=True, null=True,
        help_text="�˻����� ������ ķ�۽���"
    )
    campus_address = models.CharField(
        max_length = 300, blank = True, null=True,
        help_text = "���� ķ�۽��� �ּ�"
    )
    '''

    # ����
    business_type = models.CharField(
        max_length=20,
        choices=BusinessType.choices,
        blank=False,            
        db_index=True,                   
        verbose_name='����',
        help_text='�Ĵ�, ī��, ���� �� �ϳ�'
    )

    # ���Ը�
    profile_name = models.CharField(max_length=30)

    # ������
    business_day = models.JSONField(
        default=dict, blank = False,
        help_text = '���Ϻ� �ð��� �迭 JSON' # ��: {"��": ["09:00-15:00"], "��": ["18:00-24:00"]}
    )

    # ���� ��ǥ
    partnership_goal = models.CharField(
        max_length=20,
        choices=PartnershipGoal.choices,
        blank=False,            
        db_index=True,                   
        verbose_name='���� ��ǥ',
        help_text='�ű� �� ����, ��湮 ����, ��� ����, ��ũŸ�� �л�, SNS ȫ��, ���� Ȯ��, ��Ÿ �� �ϳ�'
    )
    partnership_goal_other = models.CharField(
        max_length=200, blank=True,
        verbose_name="��Ÿ ��",
        help_text='���� ��ǥ�� ��Ÿ(OTHER)�� �� ��'
    )

    # ��� �δ� ����
    average_sales = models.PositiveIntegerField(
        validators=[MinValueValidator(0)],
        help_text='�� ����'
    )

    # ������
    margin_rate = models.DecimalField(
        max_digits=5, decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text='0~100 ���� �ۼ�Ʈ'
    )

    # �ٻ� �ð���
    peak_time = models.JSONField(
        default=list, blank=True,
        help_text='���ڿ� ���� �迭' # �� : ["11:00-14:00", "18:00-21:00"]
    )

    # �ѻ� �ð���
    off_peak_time = models.JSONField(
        default=list, blank=True,
        help_text='���ڿ� ���� �迭' # �� : ["11:00-14:00", "18:00-21:00"]
    )

    # �߰� ���� ���� ����
    available_service = models.CharField(
        max_length=20,
        choices=Service.choices,
        blank=False,             
        db_index=True,                   
        verbose_name='�߰� ���� ���� ����',
        help_text='�����, ���̵� �޴�, ��Ÿ �� �ϳ�'
    )
    available_service_other = models.CharField(
        max_length=200, blank=True,
        verbose_name="��Ÿ ��",
        help_text='�߰� ���� ���� ���񽺰� ��Ÿ(OTHER)�� �� ��'
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='������')
    modified_at = models.DateTimeField(auto_now=True, verbose_name='������')

    def __str__(self):
        return self.profile_name
    
# ��ǥ ���� : ������ ������ ���� ���� ���̺� ����
class OwnerPhoto(models.Model):
    owner_profile = models.ForeignKey(
        OwnerProfile, on_delete=models.CASCADE, related_name="photos"
    )
    image = models.ImageField(upload_to="owner_profile/photos/")
    order = models.PositiveSmallIntegerField(
        default=0, help_text="ǥ�� ����"
    )
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name='������')

    class Meta:
        ordering = ["order", "id"] # ������ ���� ���� order -> id
    
    def __str__(self):
        return f"{self.owner_profile.profile_name} - photo#{self.pk}"

# ��ǥ �޴� : ������ ������ ���� ���� ���̺� ����
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
        default=0, help_text="ǥ�� ����"
    )

    class Meta:
        ordering = ["order", "id"] # ������ ���� ���� order -> id
        unique_together = [("owner_profile", "name")]  # ���� ��ȣ �� �ߺ� �޴��� ����

    def __str__(self):
        return f"{self.owner_profile.profile_name} - {self.name}"
    
# ------ �л���ü ������ ------
class StudentGroupProfile(models.Model):

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='student_group_profile')

    # �Ҽ� 
    '''
    ������� ���� ���� �ʿ�
    profile_name = models.CharField(
        max_length = 100, blank=True, null=True,
        help_text="�˻����� ������ ��ü��"
    )
    '''
    # ��å
    position = models.CharField(max_length=30)

    # �Ҽ� ���� �л� ��
    student_size = models.PositiveIntegerField(
        validators=[MinValueValidator(0)],
        help_text='�� ����'
    )

    # �ӱ�
    term_start = models.DateField(verbose_name="�ӱ� ������")
    term_end = models.DateField(verbose_name="�ӱ� ������")
    
    # ���� �Ⱓ
    partnership_start = models.DateField(verbose_name="���� ������")
    partnership_end = models.DateField(verbose_name="���� ������")

    # ���� �̷�
    partnership_record = models.CharField(
        max_length=5,
        choices=PartnershipRecord.choices,
        blank=False,            
        db_index=True,                   
        verbose_name='���� �̷�',
        help_text='����, ���� �� �ϳ�'
    )
    record_name = models.CharField(max_length=100, blank=True, verbose_name="���� ��ü��")
    record_start = models.DateField(verbose_name="���� ������")
    record_end = models.DateField(verbose_name="���� ������")

# �л� ��ü ��ǥ ���� : ������ ������ ���� ���� ���̺� ����
class StudentPhoto(models.Model):
    owner_profile = models.ForeignKey(
        StudentGroupProfile, on_delete=models.CASCADE, related_name="photos"
    )
    image = models.ImageField(upload_to="student_group_profile/photos/")
    order = models.PositiveSmallIntegerField(
        default=0, help_text="ǥ�� ����"
    )
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name='������')

    class Meta:
        ordering = ["order", "id"] # ������ ���� ���� order -> id
    
    def __str__(self):
        return f"{self.owner_profile.profile_name} - photo#{self.pk}"
