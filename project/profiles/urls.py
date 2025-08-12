from django.urls import path
from .views import (
    # 사장님 프로필 관련
    OwnerProfileListCreateView,
    OwnerProfileDetailView,
    OwnerPhotoView,
    MenuView,
    
    # 학생단체 프로필 관련
    StudentGroupProfileListCreateView,
    StudentGroupProfileDetailView,
    StudentPhotoView,
    
    # 학생단체 프로필 관련
    StudentProfileListCreateView,
    StudentProfileDetailView,
)

app_name = 'profiles'

urlpatterns = [
    # ------ 사장님 프로필 관련 URLs ------
    
    # 프로필 목록 및 생성
    path('owners/', OwnerProfileListCreateView.as_view(), name='owner-list'),
    
    # 프로필 상세 (조회/수정/삭제)
    path('owners/<int:pk>/', OwnerProfileDetailView.as_view(), name='owner-detail'),
    
    # 프로필 사진 관리
    path('owners/<int:profile_id>/photos/', OwnerPhotoView.as_view(), name='owner-photo-list'),
    path('owners/<int:profile_id>/photos/<int:photo_id>/', OwnerPhotoView.as_view(), name='owner-photo-detail'),
    
    # 메뉴 관리
    path('owners/<int:profile_id>/menus/', MenuView.as_view(), name='menu-list'),
    path('owners/<int:profile_id>/menus/<int:menu_id>/', MenuView.as_view(), name='menu-detail'),
    
    
    # ------ 학생단체 프로필 관련 URLs ------
    
    # 프로필 목록 및 생성  
    path('student-groups/', StudentGroupProfileListCreateView.as_view(), name='student-group-list'),
    
    # 프로필 상세 (조회/수정/삭제)
    path('student-groups/<int:pk>/', StudentGroupProfileDetailView.as_view(), name='student-group-detail'),
    
    # 프로필 사진 관리
    path('student-groups/<int:profile_id>/photos/', StudentPhotoView.as_view(), name='student-group-photo-list'),
    path('student-groups/<int:profile_id>/photos/<int:photo_id>/', StudentPhotoView.as_view(), name='student-group-photo-detail'),

    # ------ 학생 프로필 관련 URLs ------
    
    # 프로필 목록 및 생성  
    path('students/', StudentProfileListCreateView.as_view(), name='student-list'),
    
    # 프로필 상세 (조회/수정/삭제)
    path('students/<int:pk>/', StudentProfileDetailView.as_view(), name='student-detail'),
]