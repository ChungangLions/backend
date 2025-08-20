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

    # JSONField를 명시적으로 정의
    available_service = serializers.ListField(
        child=serializers.CharField(),
        required=True,
        allow_empty=False
    )
    partnership_goal = serializers.ListField(
        child=serializers.CharField(),
        required=True,
        allow_empty=False
    )

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
    
    def validate_partnership_goal(self, value):
        """제휴 목표 JSONField 유효성 검사"""
        # 문자열로 온 경우 JSON 파싱 시도
        if isinstance(value, str):
            try:
                import json
                value = json.loads(value)
            except json.JSONDecodeError:
                raise serializers.ValidationError("제휴 목표는 유효한 JSON 리스트 형태여야 합니다.")
        
        if not isinstance(value, list):
            raise serializers.ValidationError("제휴 목표는 리스트 형태여야 합니다.")
        
        if not value:
            raise serializers.ValidationError("최소 하나 이상의 제휴 목표를 선택해야 합니다.")
        
        valid_choices = [choice[0] for choice in PartnershipGoal.choices]
        for goal in value:
            if goal not in valid_choices:
                raise serializers.ValidationError(f"유효하지 않은 제휴 목표입니다: {goal}")
        
        return value
    
    def validate_available_service(self, value):
        """제공 서비스 JSONField 유효성 검사"""
        # # 문자열로 온 경우 JSON 파싱 시도
        # if isinstance(value, str):
        #     try:
        #         import json
        #         value = json.loads(value)
        #     except json.JSONDecodeError:
        #         raise serializers.ValidationError("제공 서비스는 유효한 JSON 리스트 형태여야 합니다.")
        
        if not isinstance(value, list):
            raise serializers.ValidationError("제공 서비스는 리스트 형태여야 합니다.")
        
        if not value:
            raise serializers.ValidationError("최소 하나 이상의 제공 서비스를 선택해야 합니다.")
        
        valid_choices = [choice[0] for choice in Service.choices]
        for service in value:
            if service not in valid_choices:
                raise serializers.ValidationError(f"유효하지 않은 제공 서비스입니다: {service}")
        
        return value
    
    def validate_partnership_goal_other(self, value):
        partnership_goals = self.initial_data.get('partnership_goal', [])
        
        # 문자열로 온 경우 JSON 파싱
        if isinstance(partnership_goals, str):
            try:
                import json
                partnership_goals = json.loads(partnership_goals)
            except json.JSONDecodeError:
                partnership_goals = []
                
        if PartnershipGoal.OTHER in partnership_goals and not value:
            raise serializers.ValidationError("제휴 목표에 '기타'가 포함될 때는 상세 내용을 입력해야 합니다.")
        return value
    
    def validate_available_service_other(self, value):
        available_services = self.initial_data.get('available_service', [])
        
        # 문자열로 온 경우 JSON 파싱
        if isinstance(available_services, str):
            try:
                import json
                available_services = json.loads(available_services)
            except json.JSONDecodeError:
                available_services = []
                
        if Service.OTHER in available_services and not value:
            raise serializers.ValidationError("제공 서비스에 '기타'가 포함될 때는 상세 내용을 입력해야 합니다.")
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
            'profile_name', # 가게 이름
            'business_day', # 영업일 예: {"월": ["09:00-15:00"], "수": ["18:00-24:00"]}
            'partnership_goal', # 제휴 목표 -> JSON 필드로 입력 받기
            'partnership_goal_other', # 제휴 목표 (기타), 없으면 빈 문자열
            'average_sales', # 인당 평균 매출
            'margin_rate', # 마진율
            'peak_time', # 피크 타임
            'off_peak_time', # 한산 시간대
            'available_service', # 제공 서비스 -> JSON 필드로 입력 받기
            'available_service_other', # 제공 서비스 (기타), 없으면 빈 문자열
            'comment', # 한줄 소개
        )
        read_only_fields = fields
