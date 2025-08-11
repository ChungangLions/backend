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
    
    # 공통/매칭 관련
    MyProfileView,
    PartnershipMatchView,
)

app_name = 'profiles'

urlpatterns = [
    
    # ------ 공통/매칭 관련 URLs ------
    path('my-profile/', MyProfileView.as_view(), name='my-profile'),
    path('partnership/match/', PartnershipMatchView.as_view(), name='partnership-match'),
    
    
    # ------ 사장님 프로필 관련 URLs ------
    
    # 프로필 목록 및 생성
    path('owners/', OwnerProfileListCreateView.as_view(), name='owner-list-create'),
    
    # 프로필 상세 (조회/수정/삭제)
    path('owners/<int:pk>/', OwnerProfileDetailView.as_view(), name='owner-detail'),
    
    # 프로필 사진 관리
    path('owners/<int:profile_id>/photos/', OwnerPhotoView.as_view(), name='owner-photo-add'),
    path('owners/<int:profile_id>/photos/<int:photo_id>/', OwnerPhotoView.as_view(), name='owner-photo-delete'),
    
    # 메뉴 관리
    path('owners/<int:profile_id>/menus/', MenuView.as_view(), name='menu-list-create'),
    path('owners/<int:profile_id>/menus/<int:menu_id>/', MenuView.as_view(), name='menu-detail'),
    
    
    # ------ 학생단체 프로필 관련 URLs ------
    
    # 프로필 목록 및 생성  
    path('students/', StudentGroupProfileListCreateView.as_view(), name='student-list-create'),
    
    # 프로필 상세 (조회/수정/삭제)
    path('students/<int:pk>/', StudentGroupProfileDetailView.as_view(), name='student-detail'),
    
    # 프로필 사진 관리
    path('students/<int:profile_id>/photos/', StudentPhotoView.as_view(), name='student-photo-add'),
    path('students/<int:profile_id>/photos/<int:photo_id>/', StudentPhotoView.as_view(), name='student-photo-delete'),
]