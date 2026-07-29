# roles/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import RoleViewSet, UserRoleViewSet, TemporaryAccessViewSet, my_permissions

router = DefaultRouter()
router.register(r'roles',       RoleViewSet,            basename='roles')
router.register(r'user-roles',  UserRoleViewSet,        basename='user-roles')
router.register(r'temp-access', TemporaryAccessViewSet, basename='temp-access')

urlpatterns = [
    path('', include(router.urls)),
    path('me/permissions/', my_permissions, name='my-permissions'),
]