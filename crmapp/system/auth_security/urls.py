# auth_security/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    login_view, logout_view,
    LoginLogViewSet, MFAUserViewSet, APITokenViewSet,
    SSOProviderViewSet, SecurityPolicyView, BlockedIPViewSet,
)

router = DefaultRouter()
router.register(r'login-logs',  LoginLogViewSet,    basename='login-logs')
router.register(r'mfa',         MFAUserViewSet,     basename='mfa')
router.register(r'tokens',      APITokenViewSet,    basename='tokens')
router.register(r'sso',         SSOProviderViewSet, basename='sso')
router.register(r'blocked-ips', BlockedIPViewSet,   basename='blocked-ips')

urlpatterns = [
    path('login/',   login_view,                   name='auth-login'),
    path('logout/',  logout_view,                  name='auth-logout'),
    path('policy/',  SecurityPolicyView.as_view(), name='security-policy'),
    path('',         include(router.urls)),
]

# All mounted at /api/system/auth/ :
# POST   /api/system/auth/login/
# POST   /api/system/auth/logout/
# GET    /api/system/auth/login-logs/
# GET    /api/system/auth/mfa/
# POST   /api/system/auth/mfa/{id}/enable/
# POST   /api/system/auth/mfa/{id}/disable/
# POST   /api/system/auth/mfa/{id}/regen-codes/
# GET    /api/system/auth/tokens/
# POST   /api/system/auth/tokens/
# DELETE /api/system/auth/tokens/{id}/
# GET    /api/system/auth/sso/
# POST   /api/system/auth/sso/
# POST   /api/system/auth/sso/{id}/toggle/
# GET    /api/system/auth/policy/
# PATCH  /api/system/auth/policy/
# GET    /api/system/auth/blocked-ips/
# POST   /api/system/auth/blocked-ips/
# DELETE /api/system/auth/blocked-ips/{id}/