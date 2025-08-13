from django.contrib import admin
from django.urls import path, re_path, include
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView
from accounts.views import LoginView, RegisterView

schema_view = get_schema_view(
    openapi.Info(
        title="멋사 해커톤 API",
        default_version='v1',
        description="accounts, profiles, proposals API 문서",
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)
    
urlpatterns = [
    path('admin/', admin.site.urls),

    # 앱 라우트(버전/도메인별로 래핑)
    #path("api/profiles/", include("profiles.urls")),
    path('api/accounts/', include('accounts.urls')),

    # JWT 인증 URL (전역)
    path('auth/register/', RegisterView.as_view(), name='auth_register'),
    path('auth/login/', LoginView.as_view(), name='token_obtain_pair'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/verify/', TokenVerifyView.as_view(), name='token_verify'),

    # Swagger, Open API UI
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
]
