# usermanage/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UserViewSet, DepartmentViewSet, UserSessionViewSet, UserActivityLogViewSet

router = DefaultRouter()
router.register(r'users',          UserViewSet,            basename='users')
router.register(r'departments',    DepartmentViewSet,      basename='departments')
router.register(r'sessions',       UserSessionViewSet,     basename='sessions')
router.register(r'activity-logs',  UserActivityLogViewSet, basename='activity-logs')

urlpatterns = [path('', include(router.urls))]