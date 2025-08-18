from django.contrib import admin
from django.utils.html import format_html
from .models import (
    OwnerProfile, OwnerPhoto, Menu,
    StudentGroupProfile, StudentPhoto,
    StudentProfile
)


# ------ 업체 프로필 관련 Admin ------

class OwnerPhotoInline(admin.TabularInline):
    model = OwnerPhoto
    extra = 1
    fields = ('image', 'order')
    readonly_fields = ('uploaded_at',)
    
    def get_extra(self, request, obj=None, **kwargs):
        # 기존 객체가 있으면 extra를 0으로 설정
        if obj:
            return 0
        return self.extra


class MenuInline(admin.TabularInline):
    model = Menu
    extra = 1
    fields = ('name', 'price', 'image', 'order')
    
    def get_extra(self, request, obj=None, **kwargs):
        # 기존 객체가 있으면 extra를 0으로 설정
        if obj:
            return 0
        return self.extra


@admin.register(OwnerProfile)
class OwnerProfileAdmin(admin.ModelAdmin):
    list_display = [
        'profile_name', 'user', 'business_type', 
        'campus_name', 'partnership_goal', 
        'average_sales', 'margin_rate',
        'photo_count', 'menu_count', 'created_at', 'contact'
    ]
    list_filter = [
        'business_type', 'partnership_goal', 
        'available_service', 'created_at'
    ]
    search_fields = [
        'profile_name', 'user__username', 'user__email',
        'campus_name', 'comment', 'contact'
    ]
    readonly_fields = ['created_at', 'modified_at']
    
    fieldsets = (
        ('기본 정보', {
            'fields': ('user', 'profile_name', 'campus_name', 'business_type', 'comment', 'contact')
        }),
        ('영업 정보', {
            'fields': ('business_day', 'peak_time', 'off_peak_time')
        }),
        ('제휴 정보', {
            'fields': (
                'partnership_goal', 'partnership_goal_other',
                'available_service', 'available_service_other'
            )
        }),
        ('재정 정보', {
            'fields': ('average_sales', 'margin_rate')
        }),
        ('시스템 정보', {
            'fields': ('created_at', 'modified_at'),
            'classes': ('collapse',)
        })
    )
    
    inlines = [OwnerPhotoInline, MenuInline]
    
    def photo_count(self, obj):
        return obj.photos.count()
    photo_count.short_description = '사진 수'
    
    def menu_count(self, obj):
        return obj.menus.count()
    menu_count.short_description = '메뉴 수'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user').prefetch_related('photos', 'menus')


@admin.register(OwnerPhoto)
class OwnerPhotoAdmin(admin.ModelAdmin):
    list_display = ['id', 'owner_profile', 'image_preview', 'order', 'uploaded_at']
    list_filter = ['uploaded_at', 'owner_profile__business_type']
    search_fields = ['owner_profile__profile_name']
    readonly_fields = ['uploaded_at', 'image_preview']
    list_editable = ['order']
    
    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="width: 50px; height: 50px; object-fit: cover;" />',
                obj.image.url
            )
        return "이미지 없음"
    image_preview.short_description = '미리보기'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('owner_profile')


@admin.register(Menu)
class MenuAdmin(admin.ModelAdmin):
    list_display = ['name', 'owner_profile', 'price', 'image_preview', 'order']
    list_filter = ['owner_profile__business_type']
    search_fields = ['name', 'owner_profile__profile_name']
    list_editable = ['price', 'order']
    readonly_fields = ['image_preview']
    
    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="width: 50px; height: 50px; object-fit: cover;" />',
                obj.image.url
            )
        return "이미지 없음"
    image_preview.short_description = '미리보기'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('owner_profile')


# ------ 학생단체 프로필 관련 Admin ------

class StudentPhotoInline(admin.TabularInline):
    model = StudentPhoto
    extra = 1
    fields = ('image', 'order')
    readonly_fields = ('uploaded_at',)
    
    def get_extra(self, request, obj=None, **kwargs):
        if obj:
            return 0
        return self.extra


@admin.register(StudentGroupProfile)
class StudentGroupProfileAdmin(admin.ModelAdmin):
    list_display = [
        'council_name', 'department', 'user', 'university_name', 
        'position', 'student_size', 'partnership_count',
        'term_period', 'partnership_period', 'photo_count', 'contact'
    ]
    list_filter = [
        'university_name', 'department', 'position', 'partnership_count'
    ]
    search_fields = [
        'council_name', 'user__username', 'user__email',
        'university_name', 'position', 'contact'
    ]
    list_editable = ['partnership_count']
    
    fieldsets = (
        ('기본 정보', {
            'fields': ('user', 'university_name', 'council_name', 'department', 'position', 'student_size', 'contact')
        }),
        ('임기 정보', {
            'fields': ('term_start', 'term_end')
        }),
        ('제휴 정보', {
            'fields': ('partnership_start', 'partnership_end', 'partnership_count')
        })
    )
    
    inlines = [StudentPhotoInline]
    
    def term_period(self, obj):
        return f"{obj.term_start} ~ {obj.term_end}"
    term_period.short_description = '임기'
    
    def partnership_period(self, obj):
        return f"{obj.partnership_start} ~ {obj.partnership_end}"
    partnership_period.short_description = '제휴기간'
    
    def photo_count(self, obj):
        return obj.photos.count()
    photo_count.short_description = '사진 수'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user').prefetch_related('photos')


@admin.register(StudentPhoto)
class StudentPhotoAdmin(admin.ModelAdmin):
    list_display = ['id', 'student_group_profile', 'image_preview', 'order', 'uploaded_at']
    list_filter = ['uploaded_at', 'student_group_profile__university_name']
    search_fields = ['student_group_profile__council_name']
    readonly_fields = ['uploaded_at', 'image_preview']
    list_editable = ['order']
    
    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="width: 50px; height: 50px; object-fit: cover;" />',
                obj.image.url
            )
        return "이미지 없음"
    image_preview.short_description = '미리보기'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('student_group_profile')


# ------ 학생 프로필 관련 Admin ------

@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'university_name', 'image_preview']
    list_filter = ['university_name']
    search_fields = ['name', 'user__username', 'user__email', 'university_name']
    readonly_fields = ['image_preview']
    
    fieldsets = (
        ('기본 정보', {
            'fields': ('user', 'name', 'university_name')
        }),
        ('프로필 사진', {
            'fields': ('image', 'image_preview')
        })
    )
    
    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="width: 100px; height: 100px; object-fit: cover; border-radius: 50%;" />',
                obj.image.url
            )
        return "이미지 없음"
    image_preview.short_description = '프로필 사진'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


# ------ Admin Site 설정 ------

# Admin 사이트 헤더 및 제목 커스터마이징
admin.site.site_header = "파트너십 관리 시스템"
admin.site.site_title = "파트너십 Admin"
admin.site.index_title = "관리자 대시보드"