from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from accounts.models import User
from accounts.serializers import MiniUserSerializer
from .models import Proposal, ProposalStatus


# --- 제안서 상태 관련 시리얼라이저 ---
class ProposalStatusSerializer(serializers.ModelSerializer):
    """
    제안서 상태 히스토리 조회용 시리얼라이저
    """
    changed_by = MiniUserSerializer(read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = ProposalStatus
        fields = (
            'id', 'status', 'status_display', 'changed_by', 
            'changed_at', 'comment'
        )
        read_only_fields = ('id', 'changed_at')


class ProposalStatusWriteSerializer(serializers.ModelSerializer):
    """
    제안서 상태 변경용 시리얼라이저
    """
    class Meta:
        model = ProposalStatus
        fields = ('status', 'comment')
    
    def validate(self, attrs):
        """
        상태 변경 권한 및 규칙 검증
        """
        request = self.context.get('request')
        proposal = self.context.get('proposal')
        
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError(_("인증이 필요합니다."))
        
        if not proposal:
            raise serializers.ValidationError(_("제안서 정보가 필요합니다."))
        
        user = request.user
        new_status = attrs['status']
        current_status = proposal.current_status
        
        # 권한 검증
        if new_status == ProposalStatus.Status.READ:
            # 열람은 OWNER만 가능
            if user.user_role != User.Role.OWNER:
                raise serializers.ValidationError(_("업체 사장님만 제안서를 열람할 수 있습니다."))
        
        elif new_status in [ProposalStatus.Status.PARTNERSHIP, ProposalStatus.Status.REJECTED]:
            # 제휴체결/거절은 OWNER만 가능
            if user.user_role != User.Role.OWNER:
                raise serializers.ValidationError(_("업체 사장님만 제휴 결정을 할 수 있습니다."))
        
        elif new_status == ProposalStatus.Status.UNREAD:
            # 재제출은 STUDENT_GROUP만 가능 (거절 상태에서만)
            if user.user_role != User.Role.STUDENT_GROUP:
                raise serializers.ValidationError(_("학생단체만 제안서를 재제출할 수 있습니다."))
            if current_status != ProposalStatus.Status.REJECTED:
                raise serializers.ValidationError(_("거절된 제안서만 재제출할 수 있습니다."))
        
        return attrs
    
    def save(self, **kwargs):
        proposal = self.context['proposal']
        request = self.context['request']
        
        return ProposalStatus.objects.create(
            proposal=proposal,
            status=self.validated_data['status'],
            comment=self.validated_data.get('comment', ''),
            changed_by=request.user
        )


# --- 제안서 관련 시리얼라이저 ---
class ProposalListSerializer(serializers.ModelSerializer):
    """
    제안서 목록용 경량 시리얼라이저
    """
    author = MiniUserSerializer(read_only=True)
    author_type = serializers.SerializerMethodField()
    current_status = serializers.CharField(read_only=True)
    current_status_display = serializers.SerializerMethodField()
    
    class Meta:
        model = Proposal
        fields = (
            'id', 'author', 'author_type', 'sender', 'recipient',
            'current_status', 'current_status_display',
            'created_at', 'modified_at'
        )
    
    def get_author_type(self, obj):
        """작성자 유형 반환"""
        return "학생단체" if obj.author.user_role == User.Role.STUDENT_GROUP else "사장님"
    
    def get_current_status_display(self, obj):
        """현재 상태의 한글 표시명 반환"""
        status_dict = dict(ProposalStatus.Status.choices)
        return status_dict.get(obj.current_status, obj.current_status)


class ProposalDetailSerializer(serializers.ModelSerializer):
    """
    제안서 상세 조회용 시리얼라이저
    """
    author = MiniUserSerializer(read_only=True)
    author_type = serializers.SerializerMethodField()
    current_status = serializers.CharField(read_only=True)
    current_status_display = serializers.SerializerMethodField()
    status_history = ProposalStatusSerializer(many=True, read_only=True)
    is_editable = serializers.ReadOnlyField()
    is_partnership_made = serializers.ReadOnlyField()
    
    class Meta:
        model = Proposal
        fields = (
            'id', 'author', 'author_type', 'contents', 'partnership_purpose',
            'expected_effects', 'contact_info', 'sender', 'recipient',
            'is_ai_generated', 'ai_prompt', 'current_status',
            'current_status_display', 'status_history', 'is_editable',
            'is_partnership_made', 'created_at', 'modified_at'
        )
    
    def get_author_type(self, obj):
        """작성자 유형 반환"""
        return "학생단체" if obj.author.user_role == User.Role.STUDENT_GROUP else "사장님"
    
    def get_current_status_display(self, obj):
        """현재 상태의 한글 표시명 반환"""
        status_dict = dict(ProposalStatus.Status.choices)
        return status_dict.get(obj.current_status, obj.current_status)


class ProposalWriteSerializer(serializers.ModelSerializer):
    """
    제안서 생성/수정용 시리얼라이저
    - 학생단체와 사장님 모두 작성 가능
    - AI 생성 제안서 수정 지원
    """
    author = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(user_role__in=[User.Role.STUDENT_GROUP, User.Role.OWNER]),
        required=False,
        write_only=True
    )
    
    class Meta:
        model = Proposal
        fields = (
            'id', 'author', 'contents', 'partnership_purpose',
            'expected_effects', 'contact_info', 'sender', 'recipient',
            'is_ai_generated', 'ai_prompt'
        )
        read_only_fields = ('id',)
    
    def validate(self, attrs):
        """
        제안서 작성 권한 검증
        """
        request = self.context.get('request')
        
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError(_("인증이 필요합니다."))
        
        # student_group 자동 설정
        if 'student_group' not in attrs:
            if request.user.user_role == User.Role.STUDENT_GROUP:
                attrs['student_group'] = request.user
            else:
                raise serializers.ValidationError(_("학생단체만 제안서를 작성할 수 있습니다."))
        
        # 권한 검증
        student_group = attrs['student_group']
        if request.user != student_group:
            raise serializers.ValidationError(_("자신의 단체로만 제안서를 작성할 수 있습니다."))
        
        # 프로필 기반 기본값 설정 (선택사항)
        if not attrs.get('sender') and not self.instance:
            # 새 제안서 작성 시 프로필에서 발신인 정보 가져오기
            try:
                # todo: profiles 앱 개발 후 활성화
                # profile = request.user.profile
                # attrs['sender'] = profile.organization_name
                # if not attrs.get('contact_info'):
                #     attrs['contact_info'] = profile.contact_info
                attrs['sender'] = request.user.username  # 임시
            except AttributeError:
                attrs['sender'] = request.user.username
        
        return attrs
    
    def create(self, validated_data):
        """
        제안서 생성 (자동으로 UNREAD 상태 생성됨)
        """
        return Proposal.objects.create(**validated_data)
    
    def update(self, instance, validated_data):
        """
        제안서 수정 (수정 가능한 상태에서만)
        """
        if not instance.is_editable:
            raise serializers.ValidationError(_("현재 상태에서는 제안서를 수정할 수 없습니다."))
        
        # student_group은 수정 불가
        validated_data.pop('student_group', None)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        return instance


# --- ChatGPT 관련 시리얼라이저 ---
class ProposalAIGenerateSerializer(serializers.Serializer):
    """
    프로필 기반 ChatGPT 제안서 생성용 시리얼라이저
    학생회와 사장님의 프로필 정보를 바탕으로 맞춤형 제안서 생성
    """
    recipient = serializers.CharField(
        max_length=100,
        help_text="제휴 대상 (학생단체명 또는 업체명)"
    )
    partnership_type = serializers.CharField(
        max_length=200,
        help_text="원하는 제휴 유형 (예: 할인 혜택, 이벤트 협력, 공간 대여 등)"
    )
    specific_requests = serializers.CharField(
        max_length=500,
        required=False,
        allow_blank=True,
        help_text="구체적인 제휴 요청사항이나 특별한 조건"
    )
    target_audience = serializers.CharField(
        max_length=200,
        required=False,
        allow_blank=True,
        help_text="대상 고객층 (예: 대학생, 20대 등)"
    )
    
    def validate(self, attrs):
        """
        AI 생성 권한 및 프로필 존재 검증
        """
        request = self.context.get('request')
        
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError(_("인증이 필요합니다."))
        
        if request.user.user_role not in [User.Role.STUDENT_GROUP, User.Role.OWNER]:
            raise serializers.ValidationError(_("학생단체 또는 사장님만 AI 제안서 생성을 사용할 수 있습니다."))
        
        # 프로필 존재 여부 확인 (profiles 앱 개발 후 활성화)
        # try:
        #     if request.user.user_role == User.Role.STUDENT_GROUP:
        #         profile = request.user.student_profile
        #     else:  # OWNER
        #         profile = request.user.business_profile
        #     
        #     if not profile:
        #         raise serializers.ValidationError(_("프로필을 먼저 작성해주세요."))
        # except AttributeError:
        #     raise serializers.ValidationError(_("프로필을 먼저 작성해주세요."))
        
        return attrs
    
    def get_profile_context(self):
        """
        현재 사용자의 프로필 정보를 ChatGPT 프롬프트용으로 구성
        """
        request = self.context.get('request')
        user = request.user
        
        # TODO: profiles 앱 개발 후 실제 프로필 데이터 사용
        if user.user_role == User.Role.STUDENT_GROUP:
            # try:
            #     profile = user.student_profile
            #     return {
            #         'type': '학생단체',
            #         'organization_name': profile.organization_name,
            #         'organization_type': profile.organization_type,
            #         'description': profile.description,
            #         'activities': profile.activities,
            #         'member_count': profile.member_count,
            #         'achievements': profile.achievements,
            #         'contact_person': profile.contact_person,
            #         'contact_info': profile.contact_info,
            #     }
            # except AttributeError:
            #     pass
            
            # 임시 기본값 (학생단체)
            return {
                'type': '학생단체',
                'organization_name': user.username,
                'organization_type': '학생단체',
                'description': '열정적인 대학생 단체',
                'activities': '다양한 활동',
                'member_count': '20명',
                'achievements': '여러 성과',
                'contact_person': user.username,
                'contact_info': user.email or '연락처 미등록',
            }
        else:  # OWNER
            # try:
            #     profile = user.business_profile
            #     return {
            #         'type': '업체',
            #         'business_name': profile.business_name,
            #         'business_type': profile.business_type,
            #         'description': profile.description,
            #         'location': profile.location,
            #         'services': profile.services,
            #         'target_customers': profile.target_customers,
            #         'contact_person': profile.contact_person,
            #         'contact_info': profile.contact_info,
            #     }
            # except AttributeError:
            #     pass
            
            # 임시 기본값 (사장님)
            return {
                'type': '업체',
                'business_name': user.username,
                'business_type': '일반 업체',
                'description': '고객 만족을 추구하는 업체',
                'location': '서울시',
                'services': '다양한 서비스',
                'target_customers': '대학생, 일반인',
                'contact_person': user.username,
                'contact_info': user.email or '연락처 미등록',
            }
    
    def generate_chatgpt_prompt(self):
        """
        프로필 정보와 요청사항을 바탕으로 ChatGPT 프롬프트 생성
        """
        profile_context = self.get_profile_context()
        validated_data = self.validated_data
        
        if profile_context['type'] == '학생단체':
            prompt = f"""
다음 학생단체의 프로필 정보를 바탕으로 제휴 제안서를 작성해주세요.

**학생단체 정보:**
- 단체명: {profile_context['organization_name']}
- 단체 유형: {profile_context['organization_type']}
- 단체 소개: {profile_context['description']}
- 주요 활동: {profile_context['activities']}
- 구성원 수: {profile_context['member_count']}
- 주요 성과: {profile_context['achievements']}
- 담당자: {profile_context['contact_person']}
- 연락처: {profile_context['contact_info']}

**제휴 요청 정보:**
- 제휴 대상: {validated_data['recipient']}
- 제휴 유형: {validated_data['partnership_type']}
- 특별 요청사항: {validated_data.get('specific_requests', '없음')}
- 대상 고객층: {validated_data.get('target_audience', '대학생')}
"""
        else:  # 업체
            prompt = f"""
다음 업체의 프로필 정보를 바탕으로 제휴 제안서를 작성해주세요.

**업체 정보:**
- 업체명: {profile_context['business_name']}
- 업체 유형: {profile_context['business_type']}
- 업체 소개: {profile_context['description']}
- 위치: {profile_context['location']}
- 제공 서비스: {profile_context['services']}
- 주요 고객층: {profile_context['target_customers']}
- 담당자: {profile_context['contact_person']}
- 연락처: {profile_context['contact_info']}

**제휴 요청 정보:**
- 제휴 대상: {validated_data['recipient']}
- 제휴 유형: {validated_data['partnership_type']}
- 특별 요청사항: {validated_data.get('specific_requests', '없음')}
- 대상 고객층: {validated_data.get('target_audience', '학생단체 구성원')}
"""
        
        prompt += """
다음 형식으로 제안서를 작성해주세요:

**요청 개요:**
(제휴 요청의 전반적인 개요)

**제휴 목적:**
(이번 제휴를 통해 달성하고자 하는 목적)

**기대 효과:**
(제휴를 통해 기대되는 효과나 결과)

각 항목은 구체적이고 전문적으로 작성하되, 양측의 이익을 모두 고려해서 작성해주세요.
"""
        return prompt.strip()


class ProposalAIEditSerializer(serializers.Serializer):
    """
    AI 생성된 제안서 수정용 시리얼라이저
    학생회와 사장님이 AI 생성 내용을 확인하고 수정할 수 있도록 지원
    """
    contents = serializers.CharField(
        help_text="AI가 생성한 요청 개요 (수정 가능)"
    )
    partnership_purpose = serializers.CharField(
        help_text="AI가 생성한 제휴 목적 (수정 가능)"
    )
    expected_effects = serializers.CharField(
        help_text="AI가 생성한 기대 효과 (수정 가능)"
    )
    contact_info = serializers.CharField(
        max_length=200,
        help_text="연락처 (수정 가능)"
    )
    sender = serializers.CharField(
        max_length=100,
        help_text="발신인 (수정 가능)"
    )
    recipient = serializers.CharField(
        max_length=100,
        help_text="수신인 (수정 가능)"
    )
    
    def validate(self, attrs):
        """
        수정 권한 검증
        """
        request = self.context.get('request')
        
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError(_("인증이 필요합니다."))
        
        if request.user.user_role not in [User.Role.STUDENT_GROUP, User.Role.OWNER]:
            raise serializers.ValidationError(_("학생단체 또는 사장님만 제안서를 수정할 수 있습니다."))
        
        return attrs
    
    def save(self):
        """
        수정된 내용으로 실제 제안서 생성
        """
        request = self.context.get('request')
        validated_data = self.validated_data
        
        # 프로필 정보로 기본값 설정
        ai_generate_serializer = ProposalAIGenerateSerializer(context={'request': request})
        profile_context = ai_generate_serializer.get_profile_context()
        
        proposal_data = {
            'author': request.user,
            'contents': validated_data['contents'],
            'partnership_purpose': validated_data['partnership_purpose'],
            'expected_effects': validated_data['expected_effects'],
            'contact_info': validated_data['contact_info'],
            'sender': validated_data['sender'],
            'recipient': validated_data['recipient'],
            'is_ai_generated': True,
            'ai_prompt': ai_generate_serializer.generate_chatgpt_prompt()
        }
        
        return Proposal.objects.create(**proposal_data)


# --- 통계 관련 시리얼라이저 ---
class ProposalStatsSerializer(serializers.Serializer):
    """
    제안서 통계 조회용 시리얼라이저
    """
    total_proposals = serializers.IntegerField()
    unread_count = serializers.IntegerField()
    read_count = serializers.IntegerField()
    partnership_count = serializers.IntegerField()
    rejected_count = serializers.IntegerField()
    partnership_rate = serializers.FloatField()
