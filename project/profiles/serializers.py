from rest_framework import serializers
from .models import (
    OwnerProfile, OwnerPhoto, Menu,
    StudentGroupProfile, StudentPhoto,
    PartnershipGoal, Service, PartnershipRecord
)

# ------ 업체 프로필 관련 Serializers ------

class OwnerPhotoSerializer(serializers.ModelSerializer):
    class Meta:
        model = OwnerPhoto
        fields = ["id", "image", "order", "uploaded_at"]
        read_only_fields = ["id", "uploaded_at"]

class MenuSerializer(serializers.ModelSerializer):
    class Meta:
        model = Menu
        fields = ["id", "name", "price", "image", "order"]
        read_only_fields = ["id"]

class StudentPhotoSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentPhoto
        fields = ["id", "image", "order", "uploaded_at"]
        read_only_fields = ["id", "uploaded_at"]

# --- 업체 프로필 조회용 --- 
class OwnerProfileSerializer(serializers.ModelSerializer):

    photos = OwnerPhotoSerializer(many=True, required=False)
    menus = MenuSerializer(many=True, required=False)

    class Meta:
        model = OwnerProfile
        fields = [
            'id', 'user', 'user_email', 'campus_name',
            'business_type', 'profile_name', 'business_day',
            'partnership_goal', 'partnership_goal_other',
            'average_sales', 'margin_rate',
            'peak_time', 'off_peak_time',
            'available_service', 'available_service_other',
            'created_at', 'modified_at',
            'photos', 'menus', 'partnership_type', 'comment'
        ]
        read_only_fields = ['id', 'created_at', 'modified_at']
    
# --- 업체 프로필 생성/수정용 ---
class OwnerProfileCreateSerializer(serializers.ModelSerializer):
    
    photos_data = OwnerPhotoSerializer(many=True, required=False)
    menus_data = MenuSerializer(many=True, required=False)
    
    class Meta:
        model = OwnerProfile
        fields = [
            'user', 'business_type', 'profile_name', 'business_day',
            'partnership_goal', 'partnership_goal_other', 'campus_name',
            'average_sales', 'margin_rate',
            'peak_time', 'off_peak_time',
            'available_service', 'available_service_other',
            'photos_data', 'menus_data', 'partnership_type', 'comment'
        ]
        
    def validate_margin_rate(self, value):
        if value < 0 or value > 100:
            raise serializers.ValidationError("마진율은 0과 100 사이여야 합니다.")
        return value
    
    def validate_partnership_goal_other(self, value):
        partnership_goal = self.initial_data.get('partnership_goal')
        if partnership_goal == PartnershipGoal.OTHER and not value:
            raise serializers.ValidationError("제휴 목표가 '기타'일 때는 상세 내용을 입력해야 합니다.")
        return value
    
    def validate_available_service_other(self, value):
        available_service = self.initial_data.get('available_service')
        if available_service == Service.OTHER and not value:
            raise serializers.ValidationError("추가 서비스가 '기타'일 때는 상세 내용을 입력해야 합니다.")
        return value
    
    def create(self, validated_data):
        photos_data = validated_data.pop('photos_data', [])
        menus_data = validated_data.pop('menus_data', [])
        
        owner_profile = OwnerProfile.objects.create(**validated_data)
        
        for photo_data in photos_data:
            OwnerPhoto.objects.create(owner_profile=owner_profile, **photo_data)
        
        for menu_data in menus_data:
            Menu.objects.create(owner_profile=owner_profile, **menu_data)
        
        return owner_profile
    
    def update(self, instance, validated_data):
        photos_data = validated_data.pop('photos_data', [])
        menus_data = validated_data.pop('menus_data', [])
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        if photos_data:
            instance.photos.all().delete()
            for photo_data in photos_data:
                OwnerPhoto.objects.create(owner_profile=instance, **photo_data)
        
        if menus_data:
            instance.menus.all().delete()
            for menu_data in menus_data:
                Menu.objects.create(owner_profile=instance, **menu_data)
        
        return instance


# ------ 학생단체 프로필 관련 Serializers ------

class StudentPhotoSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentPhoto
        fields = ['id', 'image', 'order', 'uploaded_at']
        read_only_fields = ['id', 'uploaded_at']

# --- 학생단체 프로필 조회용 ---
class StudentGroupProfileSerializer(serializers.ModelSerializer):
    
    photos = StudentPhotoSerializer(many=True, read_only=True)
    
    class Meta:
        model = StudentGroupProfile
        fields = [
            'id', 'user', 'council_name',
            'position', 'student_size',
            'term_start', 'term_end', 'term_duration',
            'partnership_start', 'partnership_end', 'partnership_duration',
            'partnership_record',
            'record_name', 'record_start', 'record_end',
            'photos', 'university_name'
        ]
        read_only_fields = ['id']

# --- 학생단체 프로필 생성/수정용 ---
class StudentGroupProfileCreateSerializer(serializers.ModelSerializer):
    
    photos_data = StudentPhotoSerializer(many=True, required=False)
    
    class Meta:
        model = StudentGroupProfile
        fields = [
            'user', 'position', 'student_size', 'council_name',
            'term_start', 'term_end',
            'partnership_start', 'partnership_end',
            'partnership_record', 'record_name', 'record_start', 'record_end',
            'photos_data', 'university_name'
        ]

    def validate(self, data):
        # 임기 날짜 검증
        if data.get('term_start') and data.get('term_end'):
            if data['term_start'] >= data['term_end']:
                raise serializers.ValidationError("임기 종료일은 시작일보다 늦어야 합니다.")
        
        # 제휴 기간 날짜 검증
        if data.get('partnership_start') and data.get('partnership_end'):
            if data['partnership_start'] >= data['partnership_end']:
                raise serializers.ValidationError("제휴 종료일은 시작일보다 늦어야 합니다.")
        
        # 제휴 이력이 있을 때 기록 정보 필수
        if data.get('partnership_record') == PartnershipRecord.TRUE:
            if not data.get('record_name'):
                raise serializers.ValidationError("제휴 이력이 있을 때는 업체명을 입력해야 합니다.")
            if not data.get('record_start') or not data.get('record_end'):
                raise serializers.ValidationError("제휴 이력이 있을 때는 제휴 기간을 입력해야 합니다.")
            if data.get('record_start') >= data.get('record_end'):
                raise serializers.ValidationError("제휴 이력의 종료일은 시작일보다 늦어야 합니다.")
        
        return data
    
    def create(self, validated_data):
        photos_data = validated_data.pop('photos_data', [])
        
        student_profile = StudentGroupProfile.objects.create(**validated_data)
        
        for photo_data in photos_data:
            StudentPhoto.objects.create(owner_profile=student_profile, **photo_data)
        
        return student_profile
    
    def update(self, instance, validated_data):
        photos_data = validated_data.pop('photos_data', [])
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        if photos_data:
            instance.photos.all().delete()
            for photo_data in photos_data:
                StudentPhoto.objects.create(owner_profile=instance, **photo_data)
        
        return instance
