from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UserViewSet, LikeViewSet

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')
router.register(r'likes', LikeViewSet, basename='like')

urlpatterns = [
    # /api/accounts/users/..., /api/accounts/likes/...
    path('', include(router.urls)),
]

"""
# 유저 목록(검색/정렬)
GET /api/users/?search=alice&ordering=-likes_received_count

# 특정 유저 상세
GET /api/users/5/

# 특정 유저 찜 생성(정석)
POST /api/users/5/like/             Authorization: Bearer <token>

# 특정 유저 찜 삭제(정석, 멱등)
DELETE /api/users/5/like/           Authorization: Bearer <token>

# 특정 유저 찜 토글(UX용)
POST /api/users/5/like-toggle/      Authorization: Bearer <token>

# 내가 누른 찜 목록
GET /api/likes/                     Authorization: Bearer <token>

# 내가 받은 찜 목록
GET /api/likes/?mode=received       Authorization: Bearer <token>

# 찜 생성 (리소스형)
POST /api/likes/                    Authorization: Bearer <token>
{ "target": 5 }

# 찜 삭제 (리소스형)
DELETE /api/likes/12/               Authorization: Bearer <token>

"""