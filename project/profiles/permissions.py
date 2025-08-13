from rest_framework.permissions import BasePermission, SAFE_METHODS

class IsOwnerOrReadOnly(BasePermission):
    message = '본인의 리소스만 수정/삭제할 수 있습니다.'

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True

        # 1. 모델에 user 필드가 있는 경우
        if hasattr(obj, 'user'):
            return obj.user == request.user

        # 2. OwnerPhoto, Menu → owner_profile.user
        if hasattr(obj, 'owner_profile'):
            return getattr(obj.owner_profile, 'user', None) == request.user

        # 3. StudentPhoto → student_group_profile.user
        if hasattr(obj, 'student_group_profile'):
            return getattr(obj.student_group_profile, 'user', None) == request.user

        return False
