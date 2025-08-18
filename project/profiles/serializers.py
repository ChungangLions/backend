from rest_framework import serializers
from .models import (
    OwnerProfile, OwnerPhoto, Menu,
    StudentGroupProfile, StudentPhoto,
    PartnershipGoal, Service,
    StudentProfile
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

# --- 업체 프로필 조회용 --- 
class OwnerProfileSerializer(serializers.ModelSerializer):

    photos = OwnerPhotoSerializer(many=True, required=False)
    menus = MenuSerializer(many=True, required=False)

    class Meta:
        model = OwnerProfile
        fields = [
            'id', 'user', 'campus_name',
            'business_type', 'profile_name', 'business_day',
            'partnership_goal', 'partnership_goal_other',
            'average_sales', 'margin_rate',
            'peak_time', 'off_peak_time',
            'available_service', 'available_service_other',
            'created_at', 'modified_at',
            'photos', 'menus', 'comment', 'contact'
        ]
        read_only_fields = ['id', 'user', 'created_at', 'modified_at']
    
# --- 업체 프로필 생성/수정용 ---
class OwnerProfileCreateSerializer(serializers.ModelSerializer):
    
    photos = OwnerPhotoSerializer(many=True, required=False)
    menus = MenuSerializer(many=True, required=False)

    class Meta:
        model = OwnerProfile
        fields = [
            'user', 'business_type', 'profile_name', 'business_day',
            'partnership_goal', 'partnership_goal_other', 'campus_name',
            'average_sales', 'margin_rate',
            'peak_time', 'off_peak_time',
            'available_service', 'available_service_other',
            'photos', 'menus', 'comment', 'contact'
        ]
        read_only_fields = ['user']
        
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
        
        owner_profile = OwnerProfile.objects.create(**validated_data)
        
        return owner_profile
    
    def update(self, instance, validated_data):
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
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
            'id', 'user', 'council_name', 'department',
            'position', 'student_size',
            'term_start', 'term_end',
            'partnership_start', 'partnership_end',
            'partnership_count',
            'photos', 'university_name', 'contact'
        ]
        read_only_fields = ['id', 'user']

# --- 학생단체 프로필 생성/수정용 ---
class StudentGroupProfileCreateSerializer(serializers.ModelSerializer):
    
    photos = StudentPhotoSerializer(many=True, required=False)
    
    class Meta:
        model = StudentGroupProfile
        fields = [
            'user', 'position', 'student_size', 'council_name', 'department',
            'term_start', 'term_end',
            'partnership_start', 'partnership_end',
            'photos', 'university_name', 'contact'
        ]
        read_only_fields = ['user']

    def validate(self, data):
        # 임기 날짜 검증
        if data.get('term_start') and data.get('term_end'):
            if data['term_start'] >= data['term_end']:
                raise serializers.ValidationError("임기 종료일은 시작일보다 늦어야 합니다.")
        
        # 제휴 기간 날짜 검증
        if data.get('partnership_start') and data.get('partnership_end'):
            if data['partnership_start'] >= data['partnership_end']:
                raise serializers.ValidationError("제휴 종료일은 시작일보다 늦어야 합니다.")
        
        return data
    
    def create(self, validated_data):
        student_profile = StudentGroupProfile.objects.create(**validated_data)

        return student_profile
    
    def update(self, instance, validated_data):
       
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        return instance

# ------ 학생 프로필 관련 Serializers ------

# --- 학생 프로필 조회용 ---
class StudentProfileSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = StudentProfile
        fields = [
            'id', 'user', 'name',
            'university_name', 'image'
        ]
        read_only_fields = ['id', 'user']

# --- 학생 프로필 생성/수정용 ---
class StudentProfileCreateSerializer(serializers.ModelSerializer):

    class Meta:
        model = StudentProfile
        fields = [
            'image', 'name', 'university_name'
        ]
    
    def validate_image(self, value):
        """이미지 파일 검증"""
        if value:
            # 파일 형식 검증
            valid_extensions = ['.jpg', '.jpeg', '.png', '.gif']
            if not any(value.name.lower().endswith(ext) for ext in valid_extensions):
                raise serializers.ValidationError("지원되지 않는 이미지 형식입니다.")
        
        return value
