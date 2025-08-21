from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.shortcuts import get_object_or_404
from django.db import transaction
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
import json
from .permissions import IsOwnerOrReadOnly
from .models import (
    OwnerProfile, OwnerPhoto, Menu, 
    StudentGroupProfile, StudentPhoto,
    StudentProfile
)
from .serializers import (
    OwnerProfileSerializer, OwnerProfileCreateSerializer,
    StudentGroupProfileSerializer, StudentGroupProfileCreateSerializer,
    StudentProfileSerializer, StudentProfileCreateSerializer
)
from django.conf import settings

MAX_OWNER_PHOTOS = 10
MAX_OWNER_MENUS = 8

class BaseProfileMixin:
    """프로필 관련 뷰의 공통 기능"""
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

class BaseDetailMixin(BaseProfileMixin):
    """상세 뷰의 공통 기능"""
    permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]

# ------ 사장님 프로필 관련 Views ------
class OwnerProfileListCreateView(BaseProfileMixin, APIView):
    """사장님 프로필 목록 조회, 생성"""
    @swagger_auto_schema(
        operation_summary="사장님 프로필 목록 조회",
        operation_description="모든 사장님 프로필을 조회합니다.",
        responses={200: OwnerProfileSerializer(many=True)}
    )
    def get(self, request):
        profiles = OwnerProfile.objects.select_related('user').prefetch_related('photos', 'menus')
        
        # 필터링
        business_type = request.query_params.get('business_type')
        
        if business_type:
            profiles = profiles.filter(business_type=business_type)
              
        serializer = OwnerProfileSerializer(profiles, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_summary="사장님 프로필 생성",
        operation_description="새로운 사장님 프로필을 생성합니다.",
        request_body=OwnerProfileCreateSerializer,
        responses={201: OwnerProfileCreateSerializer, 400: "잘못된 요청"}
    )
    def post(self, request):
        serializer = OwnerProfileCreateSerializer(data=request.data)
        if serializer.is_valid():
            with transaction.atomic():
                profile = serializer.save(user=request.user)
                # 대표 사진 업로드 처리
                photos = request.FILES.getlist('photos')
                if photos:
                    if len(photos) > MAX_OWNER_PHOTOS:
                        return Response(
                            {"message": f"대표 사진은 최대 {MAX_OWNER_PHOTOS}장까지 업로드할 수 있습니다."},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                    for idx, photo in enumerate(photos):
                        photo.seek(0)
                        owner_photo = OwnerPhoto.objects.create(
                            owner_profile=profile,
                            image=photo,
                            order=idx
                        )
                        owner_photo.save()

                # 메뉴 이미지 처리
                menu_images = request.FILES.getlist('menus_images')
                menus_data_raw = request.data.get('menus_data', [])
                try:
                    menus_data = json.loads(menus_data_raw)
                except json.JSONDecodeError:
                    menus_data = []
                
                if menus_data:
                    if len(menus_data) > MAX_OWNER_MENUS:
                        return Response(
                            {"detail": f"대표 메뉴는 최대 {MAX_OWNER_MENUS}개까지 등록할 수 있습니다."},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                    for idx, menu_data in enumerate(menus_data):
                        menu_image = menu_images[idx] if (idx) < len(menu_images) else None
                        Menu.objects.create(
                            owner_profile=profile,
                            name=menu_data.get('name'),
                            price=menu_data.get('price'),
                            image=menu_image,
                            order=idx
                        )

                # ---- 기본 대표 사진 자동 생성 ----
                if profile.photos.count() == 0:
                    OwnerPhoto.objects.create(
                        owner_profile=profile,
                        image=settings.DEFAULT_OWNER_PHOTO_PATH,
                        order=0
                    )

            # 생성된 프로필을 다시 조회하여 관련 데이터와 함께 반환
            created_profile = OwnerProfile.objects.select_related('user').prefetch_related('photos', 'menus').get(id=profile.id)
            return Response(
                OwnerProfileSerializer(created_profile).data, 
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class OwnerProfileDetailView(BaseDetailMixin, APIView):
    """사장님 프로필 상세 조회, 수정, 삭제"""
    def get_object(self, pk):
        return get_object_or_404(
            OwnerProfile.objects.select_related('user').prefetch_related('photos', 'menus'),
            pk=pk
        )
    
    @swagger_auto_schema(
        operation_summary="사장님 프로필 상세 조회",
        operation_description="상세 사장님 프로필을 조회합니다.",
        responses={200: OwnerProfileSerializer}
    )
    def get(self, request, pk):
        profile = self.get_object(pk)
        serializer = OwnerProfileSerializer(profile)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    @swagger_auto_schema(
        operation_summary="사장님 프로필 부분 수정",
        operation_description=(
            "사장님 프로필의 일부 필드를 수정합니다."
        ),
        request_body=OwnerProfileCreateSerializer,  
        responses={
            200: OwnerProfileSerializer,          
            400: "유효성 검사 실패",
            403: "권한 없음",
            404: "프로필 없음"
        }
    )
    def patch(self, request, pk):
        profile = self.get_object(pk)
        
        self.check_object_permissions(request, profile)

        # 요청 데이터 타입 확인
        serializer = OwnerProfileCreateSerializer(profile, data=request.data, partial=True)
        if serializer.is_valid():
            # 검증된 데이터 확인
            profile = serializer.save()

            # 대표 사진 업로드 처리
            photos = request.FILES.getlist('photos')
            if photos:
                # 기존 사진 삭제
                profile.photos.all().delete()
                if len(photos) > MAX_OWNER_PHOTOS:
                    return Response(
                        {"message": f"대표 사진은 최대 {MAX_OWNER_PHOTOS}장까지 업로드할 수 있습니다."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                for i, photo in enumerate(photos):
                    OwnerPhoto.objects.create(
                        owner_profile=profile,
                        image=photo,
                        order=i
                    )
            
            # 메뉴 이미지 처리
            if 'menus_data' in request.data:  # menus_data 키가 request에 존재하면
                menu_images = request.FILES.getlist('menus_images')
                menus_data_raw = request.data.get('menus_data')

                menus_data = []
                if isinstance(menus_data_raw, str):
                    try:
                        menus_data = json.loads(menus_data_raw)
                    except json.JSONDecodeError:
                        menus_data = []
                elif isinstance(menus_data_raw, list):
                    menus_data = menus_data_raw
                else:
                    menus_data = []

                # menus_data가 실제로 들어왔을 때만 기존 메뉴 삭제 + 갱신
                if menus_data:
                    if len(menus_data) > MAX_OWNER_MENUS:
                        return Response(
                            {"detail": f"대표 메뉴는 최대 {MAX_OWNER_MENUS}개까지 등록할 수 있습니다."},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                    profile.menus.all().delete()
                    for idx, menu_data in enumerate(menus_data):
                        menu_image = menu_images[idx] if idx < len(menu_images) else None
                        Menu.objects.create(
                            owner_profile=profile,
                            name=menu_data.get('name'),
                            price=menu_data.get('price'),
                            image=menu_image,
                            order=idx
                        )
            
            # ---- 기본 대표 사진 자동 생성 ----
            if profile.photos.count() == 0:
                OwnerPhoto.objects.create(
                    owner_profile=profile,
                    image=settings.DEFAULT_OWNER_PHOTO_PATH,
                    order=0
                )

            updated_profile = OwnerProfile.objects.select_related('user').prefetch_related('photos', 'menus').get(id=profile.id)
            return Response(
                OwnerProfileSerializer(updated_profile).data, 
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @swagger_auto_schema(
        operation_summary="사장님 프로필 삭제",
        operation_description=(
            "본인이 소유한 사장님 프로필을 삭제합니다."
        ),
        responses={
            204: openapi.Response(description="삭제 성공"),
            403: "권한 없음",
            404: "프로필 없음"
        }
    )
    def delete(self, request, pk):
        profile = self.get_object(pk)
        
        self.check_object_permissions(request, profile)
        
        profile.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

# ------ 학생단체 프로필 관련 Views ------
class StudentGroupProfileListCreateView(BaseProfileMixin, APIView):
    """학생단체 프로필 목록 조회 및 생성"""
    @swagger_auto_schema(
        operation_summary="학생단체 프로필 목록 조회",
        operation_description="모든 학생단체 프로필을 조회합니다.",
        responses={200: StudentGroupProfileSerializer(many=True)}
    )
    def get(self, request):
        profiles = StudentGroupProfile.objects.select_related('user').prefetch_related('photos')
        
        # 필터링
        partnership_count = request.query_params.get('partnership_count')
        
        if partnership_count:
            profiles = profiles.filter(partnership_count=partnership_count)
            
        serializer = StudentGroupProfileSerializer(profiles, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    @swagger_auto_schema(
        operation_summary="학생단체 프로필 생성",
        operation_description="새로운 학생단체 프로필을 생성합니다.",
        request_body=StudentGroupProfileCreateSerializer,
        responses={201: StudentGroupProfileCreateSerializer, 400: "잘못된 요청"}
    )
    def post(self, request):
        serializer = StudentGroupProfileCreateSerializer(data=request.data)
        if serializer.is_valid():
            with transaction.atomic():
                profile = serializer.save(user=request.user)
                
                # 프로필 사진 업로드 처리
                photos = request.FILES.getlist('photos')
                for idx, photo in enumerate(photos):
                    photo.seek(0)
                    student_group_photo = StudentPhoto.objects.create(
                        student_group_profile=profile,
                        image=photo,
                        order=idx
                    )
                    student_group_photo.save()
            
            # 생성된 프로필을 다시 조회하여 관련 데이터와 함께 반환
            created_profile = StudentGroupProfile.objects.select_related('user').prefetch_related('photos').get(id=profile.id)
            return Response(
                StudentGroupProfileSerializer(created_profile).data, 
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class StudentGroupProfileDetailView(BaseDetailMixin, APIView):
    """학생단체 프로필 상세 조회, 수정, 삭제"""
    def get_object(self, pk):
        return get_object_or_404(
            StudentGroupProfile.objects.select_related('user').prefetch_related('photos'),
            pk=pk
        )
    
    @swagger_auto_schema(
        operation_summary="학생단체 프로필 상세 조회",
        operation_description="상세 학생단체 프로필을 조회합니다.",
        responses={200: StudentGroupProfileSerializer}
    )
    def get(self, request, pk):
        profile = self.get_object(pk)
        serializer = StudentGroupProfileSerializer(profile)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    @swagger_auto_schema(
        operation_summary="학생단체 프로필 부분 수정",
        operation_description=(
            "학생단체 프로필의 일부 필드를 수정합니다."
        ),
        request_body=StudentGroupProfileCreateSerializer,  
        responses={
            200: StudentGroupProfileSerializer,          
            400: "유효성 검사 실패",
            403: "권한 없음",
            404: "프로필 없음"
        }
    )
    def patch(self, request, pk):
        profile = self.get_object(pk)
        
        self.check_object_permissions(request, profile)
        
        serializer = StudentGroupProfileCreateSerializer(profile, data=request.data, partial=True)
        if serializer.is_valid():
            profile = serializer.save()

            photos = request.FILES.getlist('photos')
            # 사진 수정 로직
            if photos:
                # 기존 사진 삭제
                profile.photos.all().delete()
                # 새 사진 저장
                for idx, photo in enumerate(request.FILES.getlist('photos')):
                    StudentPhoto.objects.create(
                        student_group_profile=profile,
                        image=photo,
                        order=idx
                    )

            updated_profile = StudentGroupProfile.objects.select_related('user').prefetch_related('photos').get(id=profile.id)
            return Response(
                StudentGroupProfileSerializer(updated_profile).data, 
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @swagger_auto_schema(
        operation_summary="학생단체 프로필 삭제",
        operation_description=(
            "본인이 소유한 학생단체 프로필을 삭제합니다."
        ),
        responses={
            204: openapi.Response(description="삭제 성공"),
            403: "권한 없음",
            404: "프로필 없음"
        }
    )
    def delete(self, request, pk):
        profile = self.get_object(pk)
        
        self.check_object_permissions(request, profile)
        
        profile.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

# ------ 학생 프로필 관련 Views ------
class StudentProfileListCreateView(BaseProfileMixin, APIView):
    """학생 프로필 목록 조회 및 생성""" 
    @swagger_auto_schema(
        operation_summary="학생 프로필 목록 조회",
        operation_description="모든 학생 프로필을 조회합니다.",
        responses={200: StudentProfileSerializer(many=True)}
    )
    def get(self, request):
        profiles = StudentProfile.objects.select_related('user')
            
        serializer = StudentProfileSerializer(profiles, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    @swagger_auto_schema(
        operation_summary="학생 프로필 생성",
        operation_description="새로운 학생 프로필을 생성합니다.",
        request_body=StudentProfileCreateSerializer,
        responses={201: StudentProfileCreateSerializer, 400: "잘못된 요청"}
    )
    def post(self, request):
        serializer = StudentProfileCreateSerializer(data=request.data)
        if serializer.is_valid():
    
            profile = serializer.save(user=request.user)
            
            # 생성된 프로필을 다시 조회하여 관련 데이터와 함께 반환
            created_profile = StudentProfile.objects.select_related('user').get(id=profile.id)
            return Response(
                StudentProfileSerializer(created_profile).data, 
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class StudentProfileDetailView(BaseDetailMixin, APIView):
    """학생 프로필 상세 조회, 수정, 삭제"""   
    def get_object(self, pk):
        return get_object_or_404(
            StudentProfile.objects.select_related('user'),
            pk=pk
        )
    
    @swagger_auto_schema(
        operation_summary="학생 프로필 상세 조회",
        operation_description="상세 학생 프로필을 조회합니다.",
        responses={200: StudentProfileSerializer}
    )
    def get(self, request, pk):
        profile = self.get_object(pk)
        serializer = StudentProfileSerializer(profile)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    @swagger_auto_schema(
        operation_summary="학생 프로필 부분 수정",
        operation_description=(
            "학생 프로필의 일부 필드를 수정합니다."
        ),
        request_body=StudentProfileCreateSerializer,  
        responses={
            200: StudentProfileSerializer,          
            400: "유효성 검사 실패",
            403: "권한 없음",
            404: "프로필 없음"
        }
    )
    def patch(self, request, pk):
        profile = self.get_object(pk)
        
        self.check_object_permissions(request, profile)
        
        new_image = request.FILES.get('image')

        if new_image:
            if profile.image:
                profile.image.delete(save=False)

        serializer = StudentProfileCreateSerializer(profile, data=request.data, partial=True)
        if serializer.is_valid():
            profile = serializer.save()
            updated_profile = StudentProfile.objects.select_related('user').get(id=profile.id)
            return Response(
                StudentProfileSerializer(updated_profile).data, 
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @swagger_auto_schema(
        operation_summary="학생 프로필 삭제",
        operation_description=(
            "본인이 소유한 학생 프로필을 삭제합니다."
        ),
        responses={
            204: openapi.Response(description="삭제 성공"),
            403: "권한 없음",
            404: "프로필 없음"
        }
    )
    def delete(self, request, pk):
        profile = self.get_object(pk)
        
        self.check_object_permissions(request, profile)
        
        profile.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
