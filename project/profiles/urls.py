from django.urls import path
from .views import (
    # 사장님 프로필 관련
    OwnerProfileListCreateView,
    OwnerProfileDetailView,
    
    # 학생단체 프로필 관련
    StudentGroupProfileListCreateView,
    StudentGroupProfileDetailView,
    
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
    
    # ------ 학생단체 프로필 관련 URLs ------
    
    # 프로필 목록 및 생성  
    path('student-groups/', StudentGroupProfileListCreateView.as_view(), name='student-group-list'),
    
    # 프로필 상세 (조회/수정/삭제)
    path('student-groups/<int:pk>/', StudentGroupProfileDetailView.as_view(), name='student-group-detail'),

    # ------ 학생 프로필 관련 URLs ------
    
    # 프로필 목록 및 생성  
    path('students/', StudentProfileListCreateView.as_view(), name='student-list'),
    
    # 프로필 상세 (조회/수정/삭제)
    path('students/<int:pk>/', StudentProfileDetailView.as_view(), name='student-detail'),
]