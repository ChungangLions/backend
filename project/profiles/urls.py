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
    
    # ����/��Ī ����
    MyProfileView,
    PartnershipMatchView,
)

app_name = 'profiles'

urlpatterns = [
    
    # ------ ����/��Ī ���� URLs ------
    path('my-profile/', MyProfileView.as_view(), name='my-profile'),
    path('partnership/match/', PartnershipMatchView.as_view(), name='partnership-match'),
    
    
    # ------ ����� ������ ���� URLs ------
    
    # ������ ��� �� ����
    path('owners/', OwnerProfileListCreateView.as_view(), name='owner-list-create'),
    
    # ������ �� (��ȸ/����/����)
    path('owners/<int:pk>/', OwnerProfileDetailView.as_view(), name='owner-detail'),
    
    # ������ ���� ����
    path('owners/<int:profile_id>/photos/', OwnerPhotoView.as_view(), name='owner-photo-add'),
    path('owners/<int:profile_id>/photos/<int:photo_id>/', OwnerPhotoView.as_view(), name='owner-photo-delete'),
    
    # �޴� ����
    path('owners/<int:profile_id>/menus/', MenuView.as_view(), name='menu-list-create'),
    path('owners/<int:profile_id>/menus/<int:menu_id>/', MenuView.as_view(), name='menu-detail'),
    
    
    # ------ �л���ü ������ ���� URLs ------
    
    # ������ ��� �� ����  
    path('students/', StudentGroupProfileListCreateView.as_view(), name='student-list-create'),
    
    # ������ �� (��ȸ/����/����)
    path('students/<int:pk>/', StudentGroupProfileDetailView.as_view(), name='student-detail'),
    
    # ������ ���� ����
    path('students/<int:profile_id>/photos/', StudentPhotoView.as_view(), name='student-photo-add'),
    path('students/<int:profile_id>/photos/<int:photo_id>/', StudentPhotoView.as_view(), name='student-photo-delete'),
]