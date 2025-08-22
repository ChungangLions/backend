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
            'business_type', 'business_type_other', 'profile_name', 'business_day',
            'average_sales', 'margin_rate',
            'peak_time', 'off_peak_time',
            'created_at', 'modified_at',
            'photos', 'menus', 'comment', 'contact',
            "service_drink", "service_side_menu", 
            "service_other", "service_other_detail",
            "goal_new_customers", "goal_revisit",
            "goal_clear_stock", "goal_spread_peak",
            "goal_sns_marketing", "goal_collect_reviews",
            "goal_other", "goal_other_detail"
        ]
        read_only_fields = ['id', 'user', 'created_at', 'modified_at']
    
# --- 업체 프로필 생성/수정용 ---
class OwnerProfileCreateSerializer(serializers.ModelSerializer):

    class Meta:
        model = OwnerProfile
        fields = [
            'user', 'business_type', 'business_type_other', 'profile_name', 'business_day',
            'campus_name', 'average_sales', 'margin_rate',
            'peak_time', 'off_peak_time', 
            'comment', 'contact',
            "service_drink", "service_side_menu", 
            "service_other", "service_other_detail",
            "goal_new_customers", "goal_revisit",
            "goal_clear_stock", "goal_spread_peak",
            "goal_sns_marketing", "goal_collect_reviews",
            "goal_other", "goal_other_detail"
        ]
        read_only_fields = ['user']
        
    def validate_margin_rate(self, value):
        if value < 0 or value > 100:
            raise serializers.ValidationError("마진율은 0과 100 사이여야 합니다.")
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

# GPT한테 넘길 사장님의 프로필 Serializer -> 최신 필드 추가하기 (2025/08/20)
class OwnerProfileForAISerializer(serializers.ModelSerializer):
    class Meta:
        model = OwnerProfile
        fields = (
            'user', # 사장님 ID
            'campus_name', # 주변 대학교 이름
            'business_type', # 업종 ex) 카페, 주점
            'business_type_other', # 기타 업종 상세
            'profile_name', # 가게 이름
            'business_day', # 영업일 예: {"월": ["09:00-15:00"], "수": ["18:00-24:00"]}
            # 제휴 목표 7가지 (goal_other == True일 시 goal_other_detail을 무조건 작성해야함)
            'goal_new_customers',
            'goal_revisit',
            'goal_clear_stock',
            'goal_spread_peak',
            'goal_sns_marketing',
            'goal_collect_reviews',
            'goal_other',
            'goal_other_detail',
            'average_sales', # 인당 평균 매출
            'margin_rate', # 마진율
            'peak_time', # 피크 타임
            'off_peak_time', # 한산 시간대
            # 제공 가능 서비스 종류 3가지 (service_other_detail == True일 시 service_other_detail를 무조건 작성해야함)
            'service_drink',
            'service_side_menu',
            'service_other',
            'service_other_detail',
            'comment', # 한줄 소개
        )
        read_only_fields = fields
