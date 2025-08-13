from django.urls import path
from .views import (
    # 사장님 프로필 관련
    OwnerProfileListCreateView,
    OwnerProfileDetailView,
    OwnerPhotoCreateView, OwnerPhotoDeleteView,
    MenuCreateView, MenuDetailView,
    
    # 학생단체 프로필 관련
    StudentGroupProfileListCreateView,
    StudentGroupProfileDetailView,
    StudentPhotoCreateView, StudentPhotoDeleteView,
    
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
    path('owners/<int:profile_id>/photos/', OwnerPhotoCreateView.as_view(), name='owner-photo-list'),
    path('owners/<int:profile_id>/photos/<int:photo_id>/', OwnerPhotoDeleteView.as_view(), name='owner-photo-detail'),
    
    # 메뉴 관리
    path('owners/<int:profile_id>/menus/', MenuCreateView.as_view(), name='menu-list'),
    path('owners/<int:profile_id>/menus/<int:menu_id>/', MenuDetailView.as_view(), name='menu-detail'),
    
    
    # ------ 학생단체 프로필 관련 URLs ------
    
    # 프로필 목록 및 생성  
    path('student-groups/', StudentGroupProfileListCreateView.as_view(), name='student-group-list'),
    
    # 프로필 상세 (조회/수정/삭제)
    path('student-groups/<int:pk>/', StudentGroupProfileDetailView.as_view(), name='student-group-detail'),
    
    # 프로필 사진 관리
    path('student-groups/<int:profile_id>/photos/', StudentPhotoCreateView.as_view(), name='student-group-photo-list'),
    path('student-groups/<int:profile_id>/photos/<int:photo_id>/', StudentPhotoDeleteView.as_view(), name='student-group-photo-detail'),

    # ------ 학생 프로필 관련 URLs ------
    
    # 프로필 목록 및 생성  
    path('students/', StudentProfileListCreateView.as_view(), name='student-list'),
    
    # 프로필 상세 (조회/수정/삭제)
    path('students/<int:pk>/', StudentProfileDetailView.as_view(), name='student-detail'),
]