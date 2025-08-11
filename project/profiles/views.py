from django.shortcuts import render
from serializers import (
OwnerProfileCreateSerializer, 
OwnerProfileSerializer, 
StudentGroupProfileCreateSerializer,
StudentGroupProfileSerializer)
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.http import Http404

from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.db.models import Q
from .models import (
    OwnerProfile, OwnerPhoto, Menu, 
    StudentGroupProfile, StudentPhoto
)
from .serializers import (
    OwnerProfileSerializer, OwnerProfileCreateSerializer,
    OwnerPhotoSerializer, MenuSerializer,
    StudentGroupProfileSerializer, StudentGroupProfileCreateSerializer,
    StudentPhotoSerializer
)

# ------ 사장님 프로필 관련 Views ------
class OwnerProfileListCreateView(APIView):
    """사장님 프로필 목록 조회 및 생성"""
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    
    def get(self, request):
        """사장님 프로필 목록 조회"""
        profiles = OwnerProfile.objects.select_related('user').prefetch_related('photos', 'menus')
        
        # 필터링
        business_type = request.query_params.get('business_type')
        partnership_goal = request.query_params.get('partnership_goal')
        campus_name = request.query_params.get('campus_name')
        
        if business_type:
            profiles = profiles.filter(business_type=business_type)
        if partnership_goal:
            profiles = profiles.filter(partnership_goal=partnership_goal)
        if campus_name:
            profiles = profiles.filter(campus_name__icontains=campus_name)
            
        serializer = OwnerProfileSerializer(profiles, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    def post(self, request):
        """사장님 프로필 생성"""
        serializer = OwnerProfileCreateSerializer(data=request.data)
        if serializer.is_valid():
            with transaction.atomic():
                profile = serializer.save(user=request.user)
                
                # 프로필 사진 업로드 처리
                photos = request.FILES.getlist('photos')
                for idx, photo in enumerate(photos):
                    OwnerPhoto.objects.create(
                        owner_profile=profile,
                        image=photo,
                        order=idx
                    )
                
                # 메뉴 이미지 처리
                menu_images = request.FILES.getlist('menu_images')
                menus_data = request.data.getlist('menus', [])
                
                for idx, menu_data in enumerate(menus_data):
                    menu_image = menu_images[idx] if idx < len(menu_images) else None
                    Menu.objects.create(
                        owner_profile=profile,
                        name=menu_data.get('name'),
                        price=menu_data.get('price'),
                        image=menu_image,
                        order=idx
                    )
            
            # 생성된 프로필을 다시 조회하여 관련 데이터와 함께 반환
            created_profile = OwnerProfile.objects.select_related('user').prefetch_related('photos', 'menus').get(id=profile.id)
            return Response(
                OwnerProfileSerializer(created_profile).data, 
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class OwnerProfileDetailView(APIView):
    """사장님 프로필 상세 조회, 수정, 삭제"""
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    
    def get_object(self, pk):
        return get_object_or_404(
            OwnerProfile.objects.select_related('user').prefetch_related('photos', 'menus'),
            pk=pk
        )
    
    def get(self, request, pk):
        """프로필 상세 조회"""
        profile = self.get_object(pk)
        serializer = OwnerProfileSerializer(profile)
        return Response(serializer.data, status=status.HTTP_200_OK)
    '''
    def put(self, request, pk):
        """프로필 전체 수정"""
        profile = self.get_object(pk)
        
        # 권한 확인 (본인만 수정 가능)
        if profile.user != request.user:
            return Response(
                {'error': '본인의 프로필만 수정할 수 있습니다.'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = OwnerProfileCreateSerializer(profile, data=request.data)
        if serializer.is_valid():
            with transaction.atomic():
                profile = serializer.save()
                
                # 기존 사진들 삭제 후 새로 업로드
                if 'photos' in request.FILES:
                    profile.photos.all().delete()
                    photos = request.FILES.getlist('photos')
                    for idx, photo in enumerate(photos):
                        OwnerPhoto.objects.create(
                            owner_profile=profile,
                            image=photo,
                            order=idx
                        )
                
                # 기존 메뉴들 삭제 후 새로 생성
                if request.data.get('menus'):
                    profile.menus.all().delete()
                    menus_data = request.data.getlist('menus', [])
                    menu_images = request.FILES.getlist('menu_images', [])
                    
                    for idx, menu_data in enumerate(menus_data):
                        menu_image = menu_images[idx] if idx < len(menu_images) else None
                        Menu.objects.create(
                            owner_profile=profile,
                            name=menu_data.get('name'),
                            price=menu_data.get('price'),
                            image=menu_image,
                            order=idx
                        )
            
            # 수정된 프로필을 다시 조회하여 반환
            updated_profile = OwnerProfile.objects.select_related('user').prefetch_related('photos', 'menus').get(id=profile.id)
            return Response(
                OwnerProfileSerializer(updated_profile).data, 
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    '''
    def patch(self, request, pk):
        """프로필 부분 수정"""
        profile = self.get_object(pk)
        
        if profile.user != request.user:
            return Response(
                {'error': '본인의 프로필만 수정할 수 있습니다.'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = OwnerProfileCreateSerializer(profile, data=request.data, partial=True)
        if serializer.is_valid():
            profile = serializer.save()
            updated_profile = OwnerProfile.objects.select_related('user').prefetch_related('photos', 'menus').get(id=profile.id)
            return Response(
                OwnerProfileSerializer(updated_profile).data, 
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, pk):
        """프로필 삭제"""
        profile = self.get_object(pk)
        
        if profile.user != request.user:
            return Response(
                {'error': '본인의 프로필만 삭제할 수 있습니다.'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        profile.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class OwnerPhotoView(APIView):
    """사장님 프로필 사진 관리"""
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    
    def post(self, request, profile_id):
        """프로필 사진 추가"""
        profile = get_object_or_404(OwnerProfile, pk=profile_id)
        
        if profile.user != request.user:
            return Response(
                {'error': '본인의 프로필에만 사진을 추가할 수 있습니다.'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = OwnerPhotoSerializer(data=request.data)
        if serializer.is_valid():
            photo = serializer.save(owner_profile=profile)
            return Response(
                OwnerPhotoSerializer(photo).data, 
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, profile_id, photo_id):
        """특정 사진 삭제"""
        photo = get_object_or_404(OwnerPhoto, pk=photo_id, owner_profile_id=profile_id)
        
        if photo.owner_profile.user != request.user:
            return Response(
                {'error': '본인의 사진만 삭제할 수 있습니다.'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        photo.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MenuView(APIView):
    """메뉴 관리"""
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    
    def get(self, request, profile_id):
        """특정 프로필의 메뉴 목록 조회"""
        profile = get_object_or_404(OwnerProfile, pk=profile_id)
        menus = profile.menus.all()
        serializer = MenuSerializer(menus, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    def post(self, request, profile_id):
        """메뉴 추가"""
        profile = get_object_or_404(OwnerProfile, pk=profile_id)
        
        if profile.user != request.user:
            return Response(
                {'error': '본인의 프로필에만 메뉴를 추가할 수 있습니다.'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = MenuSerializer(data=request.data)
        if serializer.is_valid():
            menu = serializer.save(owner_profile=profile)
            return Response(
                MenuSerializer(menu).data, 
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def put(self, request, profile_id, menu_id):
        """메뉴 수정"""
        menu = get_object_or_404(Menu, pk=menu_id, owner_profile_id=profile_id)
        
        if menu.owner_profile.user != request.user:
            return Response(
                {'error': '본인의 메뉴만 수정할 수 있습니다.'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = MenuSerializer(menu, data=request.data)
        if serializer.is_valid():
            menu = serializer.save()
            return Response(
                MenuSerializer(menu).data, 
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, profile_id, menu_id):
        """메뉴 삭제"""
        menu = get_object_or_404(Menu, pk=menu_id, owner_profile_id=profile_id)
        
        if menu.owner_profile.user != request.user:
            return Response(
                {'error': '본인의 메뉴만 삭제할 수 있습니다.'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        menu.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ------ 학생단체 프로필 관련 Views ------
class StudentGroupProfileListCreateView(APIView):
    """학생단체 프로필 목록 조회 및 생성"""
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    
    def get(self, request):
        """학생단체 프로필 목록 조회"""
        profiles = StudentGroupProfile.objects.select_related('user').prefetch_related('photos')
        
        # 필터링
        university_name = request.query_params.get('university_name')
        partnership_record = request.query_params.get('partnership_record')
        council_name = request.query_params.get('council_name')
        
        if university_name:
            profiles = profiles.filter(university_name__icontains=university_name)
        if partnership_record:
            profiles = profiles.filter(partnership_record=partnership_record)
        if council_name:
            profiles = profiles.filter(council_name__icontains=council_name)
            
        serializer = StudentGroupProfileSerializer(profiles, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    def post(self, request):
        """학생단체 프로필 생성"""
        serializer = StudentGroupProfileCreateSerializer(data=request.data)
        if serializer.is_valid():
            with transaction.atomic():
                profile = serializer.save(user=request.user)
                
                # 프로필 사진 업로드 처리
                photos = request.FILES.getlist('photos')
                for idx, photo in enumerate(photos):
                    StudentPhoto.objects.create(
                        owner_profile=profile,
                        image=photo,
                        order=idx
                    )
            
            # 생성된 프로필을 다시 조회하여 관련 데이터와 함께 반환
            created_profile = StudentGroupProfile.objects.select_related('user').prefetch_related('photos').get(id=profile.id)
            return Response(
                StudentGroupProfileSerializer(created_profile).data, 
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class StudentGroupProfileDetailView(APIView):
    """학생단체 프로필 상세 조회, 수정, 삭제"""
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    
    def get_object(self, pk):
        return get_object_or_404(
            StudentGroupProfile.objects.select_related('user').prefetch_related('photos'),
            pk=pk
        )
    
    def get(self, request, pk):
        """프로필 상세 조회"""
        profile = self.get_object(pk)
        serializer = StudentGroupProfileSerializer(profile)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    def put(self, request, pk):
        """프로필 전체 수정"""
        profile = self.get_object(pk)
        
        if profile.user != request.user:
            return Response(
                {'error': '본인의 프로필만 수정할 수 있습니다.'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = StudentGroupProfileCreateSerializer(profile, data=request.data)
        if serializer.is_valid():
            with transaction.atomic():
                profile = serializer.save()
                
                # 기존 사진들 삭제 후 새로 업로드
                if 'photos' in request.FILES:
                    profile.photos.all().delete()
                    photos = request.FILES.getlist('photos')
                    for idx, photo in enumerate(photos):
                        StudentPhoto.objects.create(
                            owner_profile=profile,
                            image=photo,
                            order=idx
                        )
            
            # 수정된 프로필을 다시 조회하여 반환
            updated_profile = StudentGroupProfile.objects.select_related('user').prefetch_related('photos').get(id=profile.id)
            return Response(
                StudentGroupProfileSerializer(updated_profile).data, 
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def patch(self, request, pk):
        """프로필 부분 수정"""
        profile = self.get_object(pk)
        
        if profile.user != request.user:
            return Response(
                {'error': '본인의 프로필만 수정할 수 있습니다.'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = StudentGroupProfileCreateSerializer(profile, data=request.data, partial=True)
        if serializer.is_valid():
            profile = serializer.save()
            updated_profile = StudentGroupProfile.objects.select_related('user').prefetch_related('photos').get(id=profile.id)
            return Response(
                StudentGroupProfileSerializer(updated_profile).data, 
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, pk):
        """프로필 삭제"""
        profile = self.get_object(pk)
        
        if profile.user != request.user:
            return Response(
                {'error': '본인의 프로필만 삭제할 수 있습니다.'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        profile.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class StudentPhotoView(APIView):
    """학생단체 프로필 사진 관리"""
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    
    def post(self, request, profile_id):
        """프로필 사진 추가"""
        profile = get_object_or_404(StudentGroupProfile, pk=profile_id)
        
        if profile.user != request.user:
            return Response(
                {'error': '본인의 프로필에만 사진을 추가할 수 있습니다.'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = StudentPhotoSerializer(data=request.data)
        if serializer.is_valid():
            photo = serializer.save(owner_profile=profile)
            return Response(
                StudentPhotoSerializer(photo).data, 
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, profile_id, photo_id):
        """특정 사진 삭제"""
        photo = get_object_or_404(StudentPhoto, pk=photo_id, owner_profile_id=profile_id)
        
        if photo.owner_profile.user != request.user:
            return Response(
                {'error': '본인의 사진만 삭제할 수 있습니다.'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        photo.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

# ------ 내 프로필 조회 Views ------
class MyProfileView(APIView):
    """현재 사용자의 프로필 조회"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """현재 사용자의 프로필 정보 반환"""
        user = request.user
        result = {}
        
        # 사장님 프로필 확인
        try:
            owner_profile = OwnerProfile.objects.select_related('user').prefetch_related('photos', 'menus').get(user=user)
            result['owner_profile'] = OwnerProfileSerializer(owner_profile).data
            result['profile_type'] = 'owner'
        except OwnerProfile.DoesNotExist:
            pass
        
        # 학생단체 프로필 확인
        try:
            student_profile = StudentGroupProfile.objects.select_related('user').prefetch_related('photos').get(user=user)
            result['student_profile'] = StudentGroupProfileSerializer(student_profile).data
            result['profile_type'] = result.get('profile_type', 'student')
            if 'owner_profile' in result:
                result['profile_type'] = 'both'
        except StudentGroupProfile.DoesNotExist:
            pass
        
        if not result:
            return Response(
                {'message': '등록된 프로필이 없습니다.'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        return Response(result, status=status.HTTP_200_OK)


# ------ 매칭 및 검색 Views ------
class PartnershipMatchView(APIView):
    """제휴 매칭 추천"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """현재 사용자에게 적합한 제휴 파트너 추천"""
        user = request.user
        result = {'matches': []}
        
        # 사용자 프로필 타입 확인
        try:
            owner_profile = OwnerProfile.objects.get(user=user)
            # 사장님인 경우 - 주변 학생단체 추천
            matched_profiles = StudentGroupProfile.objects.filter(
                university_name__icontains=owner_profile.campus_name
            ).select_related('user').prefetch_related('photos')[:10]
            
            result['user_type'] = 'owner'
            result['matches'] = StudentGroupProfileSerializer(matched_profiles, many=True).data
            
        except OwnerProfile.DoesNotExist:
            try:
                student_profile = StudentGroupProfile.objects.get(user=user)
                # 학생단체인 경우 - 주변 사장님 추천
                matched_profiles = OwnerProfile.objects.filter(
                    campus_name__icontains=student_profile.university_name
                ).select_related('user').prefetch_related('photos', 'menus')[:10]
                
                result['user_type'] = 'student'
                result['matches'] = OwnerProfileSerializer(matched_profiles, many=True).data
                
            except StudentGroupProfile.DoesNotExist:
                return Response(
                    {'error': '프로필을 먼저 작성해주세요.'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        return Response(result, status=status.HTTP_200_OK)
