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

        serializer = OwnerProfileCreateSerializer(profile, data=request.data, partial=True)
        if serializer.is_valid():
            with transaction.atomic():
                profile = serializer.save()

                # 1. 삭제할 사진 ID 목록 (photos_to_delete)
                photos_to_delete_ids = request.data.getlist('photos_to_delete')
                if photos_to_delete_ids:
                    # request.data.getlist는 문자열 리스트를 반환하므로 정수형으로 변환
                    photo_ids_to_delete = [int(id_str) for id_str in photos_to_delete_ids if id_str.isdigit()]
                    if photo_ids_to_delete:
                        OwnerPhoto.objects.filter(owner_profile=profile, id__in=photo_ids_to_delete).delete()

                # 2. 새로 추가할 사진 파일 목록 (new_photos)
                new_photos = request.FILES.getlist('new_photos')
                if new_photos:
                    # 기존 사진 개수 확인
                    existing_photo_count = profile.photos.count()
                    if existing_photo_count + len(new_photos) > MAX_OWNER_PHOTOS:
                        return Response(
                            {"message": f"대표 사진은 최대 {MAX_OWNER_PHOTOS}장까지 업로드할 수 있습니다."},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                    
                    # 가장 높은 order 값을 찾아 그 다음부터 순서 부여
                    last_order = profile.photos.order_by('-order').first()
                    start_order = (last_order.order + 1) if last_order else 0

                    for i, photo in enumerate(new_photos):
                        OwnerPhoto.objects.create(
                            owner_profile=profile,
                            image=photo,
                            order=start_order + i
                        )

                # 1. 삭제할 메뉴 ID 처리 ('X' 버튼 누른 메뉴)
                menus_to_delete_ids = request.data.getlist('menus_to_delete')
                if menus_to_delete_ids:
                    menu_ids_to_delete = [int(id_str) for id_str in menus_to_delete_ids if id_str.isdigit()]
                    if menu_ids_to_delete:
                        Menu.objects.filter(owner_profile=profile, id__in=menu_ids_to_delete).delete()

                # 2. 새로 추가할 메뉴 데이터 및 이미지 파일 처리 ('+' 버튼으로 추가한 메뉴)
                new_menus_raw = request.data.get('new_menus_data', '[]')
                new_menu_images = request.FILES.getlist('new_menu_images')
                try:
                    new_menus_data = json.loads(new_menus_raw)
                except json.JSONDecodeError:
                     return Response({"detail": "잘못된 형식의 새 메뉴 데이터입니다."}, status=status.HTTP_400_BAD_REQUEST)

                if new_menus_data:
                    # 현재 메뉴 개수와 새로 추가할 메뉴 개수의 합이 최대치를 넘지 않는지 확인
                    if profile.menus.count() + len(new_menus_data) > MAX_OWNER_MENUS:
                        return Response({"detail": f"메뉴는 최대 {MAX_OWNER_MENUS}개까지 등록할 수 있습니다."}, status=status.HTTP_400_BAD_REQUEST)

                    # 기존 메뉴 중 가장 높은 order 값을 찾아 그 다음부터 순서 부여
                    last_order = profile.menus.order_by('-order').first()
                    start_order = (last_order.order + 1) if last_order else 0

                    for i, menu_data in enumerate(new_menus_data):
                        Menu.objects.create(
                            owner_profile=profile,
                            name=menu_data.get('name'),
                            price=menu_data.get('price'),
                            image=new_menu_images[i] if i < len(new_menu_images) else None,
                            order=start_order + i
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
            with transaction.atomic():
                profile = serializer.save()

                # 1. 삭제할 사진 ID 목록 (photos_to_delete)
                photos_to_delete_ids = request.data.getlist('photos_to_delete')
                if photos_to_delete_ids:
                    photo_ids_to_delete = [int(id_str) for id_str in photos_to_delete_ids if id_str.isdigit()]
                    if photo_ids_to_delete:
                        StudentPhoto.objects.filter(student_group_profile=profile, id__in=photo_ids_to_delete).delete()

                # 2. 새로 추가할 사진 파일 목록 (new_photos)
                new_photos = request.FILES.getlist('new_photos')
                if new_photos:
                    # 기존 사진 개수 확인 (필요 시 MAX_PHOTOS 같은 변수 정의)
                    # last_order를 찾아 순서 부여
                    last_order = profile.photos.order_by('-order').first()
                    start_order = (last_order.order + 1) if last_order else 0
                    
                    for i, photo in enumerate(new_photos):
                        StudentPhoto.objects.create(
                            student_group_profile=profile,
                            image=photo,
                            order=start_order + i
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
        
        # 1. 기존 이미지 삭제 요청 처리
        #    프론트에서 'delete_image': 'true' 와 같은 신호를 보내면 기존 이미지 삭제
        if request.data.get('delete_image') == 'true':
            if profile.image:
                profile.image.delete(save=False) # 파일만 삭제, 모델 필드는 serializer가 처리

        # 2. 새 이미지 파일이 있는지 확인
        #    'image' 키로 새 파일이 오면 기존 파일을 덮어쓰게 됨
        new_image = request.FILES.get('image')
        
        # serializer를 먼저 호출하여 텍스트 데이터 유효성 검사
        serializer = StudentProfileCreateSerializer(profile, data=request.data, partial=True)
        if serializer.is_valid():
            # new_image가 있으면 validated_data에 포함시켜 함께 저장
            profile = serializer.save()
            
            # (참고) new_image가 있으면 serializer.save()가 자동으로 이미지 교체 처리
            # 명시적으로 한 번 더 처리하여 안전성 확보
            if new_image:
                 profile.image = new_image
                 profile.save()

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
