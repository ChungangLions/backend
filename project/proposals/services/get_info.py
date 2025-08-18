from profiles.models import OwnerProfile
from profiles.serializers import OwnerProfileForAISerializer

def get_owner_profile_snapshot_by_user_id(owner_user_id: int) -> dict:
    """
    사장님(User.pk = owner_user_id)의 OwnerProfile을 읽어 AI용 dict로 반환
    """
    profile = OwnerProfile.objects.select_related("user").filter(user_id=owner_user_id).first()
    if not profile:
        raise OwnerProfile.DoesNotExist("해당 유저의 사장님 프로필이 없습니다.")
    return OwnerProfileForAISerializer(profile).data