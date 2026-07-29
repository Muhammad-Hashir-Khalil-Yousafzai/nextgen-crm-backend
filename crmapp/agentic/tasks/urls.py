from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'tasks', views.TaskViewSet, basename='task')
router.register(r'goals', views.GoalViewSet, basename='goal')
router.register(r'templates', views.GoalTemplateViewSet, basename='template')
router.register(r'dependencies', views.TaskDependencyViewSet, basename='dependency')
router.register(r'resources', views.ResourceViewSet, basename='resource')
router.register(r'history', views.ExecutionHistoryViewSet, basename='history')
router.register(r'alerts', views.BottleneckAlertViewSet, basename='alert')
router.register(r'performance', views.MonthlyPerformanceViewSet, basename='performance')

urlpatterns = [
    path('', include(router.urls)),
]