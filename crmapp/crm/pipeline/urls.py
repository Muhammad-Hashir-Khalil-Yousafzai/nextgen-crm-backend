from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PipelineViewSet

router = DefaultRouter()
router.register(r'', PipelineViewSet, basename='pipeline')

urlpatterns = [
    path('', include(router.urls)),
]
