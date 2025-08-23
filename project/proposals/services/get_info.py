from profiles.models import OwnerProfile, StudentGroupProfile
from profiles.serializers import OwnerProfileForAISerializer, StudentGroupProfileForAISerializer

# 사장님 프로필 스냅샷 가져오기
def get_owner_profile_snapshot_by_user_id(owner_user_id: int) -> dict:
    """
    사장님(User.pk = owner_user_id)의 OwnerProfile을 읽어 AI용 dict로 반환
    """
    profile = OwnerProfile.objects.select_related("user").filter(user_id=owner_user_id).first()
    if not profile:
        raise OwnerProfile.DoesNotExist("해당 유저의 사장님 프로필이 없습니다.")
    return OwnerProfileForAISerializer(profile).data

# 학생회 프로필 스냅샷 가져오기
def get_student_group_profile_snapshot_by_user_id(student_user_id: int, request=None) -> dict:
    """
    학생회(User.pk = student_user_id)의 StudentGroupProfile을 AI용 dict로 반환
    """
    profile = (
        StudentGroupProfile.objects
        .select_related("user")
        .filter(user_id=student_user_id)
        .first()
    )
    if not profile:
        raise StudentGroupProfile.DoesNotExist("해당 유저의 학생회 프로필이 없습니다.")
    ctx = {"request": request} if request is not None else {}
    return StudentGroupProfileForAISerializer(profile, context=ctx).data