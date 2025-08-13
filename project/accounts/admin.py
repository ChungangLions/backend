from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from .models import User, Like, Recommendation
from django.contrib.auth import get_user_model

User = get_user_model()

@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ('id', 'username', 'email', 'user_role', 'is_active', 'is_staff', 'date_joined')
    list_filter = ('user_role', 'is_active', 'is_staff', 'is_superuser')
    search_fields = ('username', 'email')
    ordering = ('-date_joined',)

    # CHANGE 페이지: 기본 fieldsets에 'email' 이미 포함되어 있음
    # 중복 없이 'Role' 섹션만 추가
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'email')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
        ('Role', {'fields': ('user_role',)}),  # ← 여기는 중복 없이 한 번만
    )

    # ADD 페이지: 이메일이 안 보였던 부분 → 여기에만 email 추가
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2', 'user_role'),
        }),
    )
@admin.register(Like)
class LikeAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'target', 'created_at')
    search_fields = ('user__username', 'user__email', 'target__username', 'target__email')
    list_filter = ('created_at',)

@admin.register(Recommendation)
class RecommendationAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'target', 'created_at')
    search_fields = ('user__username', 'user__email', 'target__username', 'target__email')
    list_filter = ('created_at',)
