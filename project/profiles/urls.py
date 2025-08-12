from django.urls import path
from .views import (
    # ����� ������ ����
    OwnerProfileListCreateView,
    OwnerProfileDetailView,
    OwnerPhotoView,
    MenuView,
    
    # �л���ü ������ ����
    StudentGroupProfileListCreateView,
    StudentGroupProfileDetailView,
    StudentPhotoView,
    
    # �л���ü ������ ����
    StudentProfileListCreateView,
    StudentProfileDetailView,
)

app_name = 'profiles'

urlpatterns = [
    # ------ ����� ������ ���� URLs ------
    
    # ������ ��� �� ����
    path('owners/', OwnerProfileListCreateView.as_view(), name='owner-list'),
    
    # ������ �� (��ȸ/����/����)
    path('owners/<int:pk>/', OwnerProfileDetailView.as_view(), name='owner-detail'),
    
    # ������ ���� ����
    path('owners/<int:profile_id>/photos/', OwnerPhotoView.as_view(), name='owner-photo-list'),
    path('owners/<int:profile_id>/photos/<int:photo_id>/', OwnerPhotoView.as_view(), name='owner-photo-detail'),
    
    # �޴� ����
    path('owners/<int:profile_id>/menus/', MenuView.as_view(), name='menu-list'),
    path('owners/<int:profile_id>/menus/<int:menu_id>/', MenuView.as_view(), name='menu-detail'),
    
    
    # ------ �л���ü ������ ���� URLs ------
    
    # ������ ��� �� ����  
    path('student-groups/', StudentGroupProfileListCreateView.as_view(), name='student-group-list'),
    
    # ������ �� (��ȸ/����/����)
    path('student-groups/<int:pk>/', StudentGroupProfileDetailView.as_view(), name='student-group-detail'),
    
    # ������ ���� ����
    path('student-groups/<int:profile_id>/photos/', StudentPhotoView.as_view(), name='student-group-photo-list'),
    path('student-groups/<int:profile_id>/photos/<int:photo_id>/', StudentPhotoView.as_view(), name='student-group-photo-detail'),

    # ------ �л� ������ ���� URLs ------
    
    # ������ ��� �� ����  
    path('students/', StudentProfileListCreateView.as_view(), name='student-list'),
    
    # ������ �� (��ȸ/����/����)
    path('students/<int:pk>/', StudentProfileDetailView.as_view(), name='student-detail'),
]