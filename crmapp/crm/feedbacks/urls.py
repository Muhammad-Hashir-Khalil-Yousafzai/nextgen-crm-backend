from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_nested import routers as nested_routers
from .views import SurveyViewSet, SurveyResponseViewSet

# Top-level router
router = DefaultRouter()
router.register(r'surveys',   SurveyViewSet,         basename='survey')
router.register(r'responses', SurveyResponseViewSet, basename='response')

# Nested: /surveys/{survey_pk}/responses/
surveys_router = nested_routers.NestedDefaultRouter(router, r'surveys', lookup='survey')
surveys_router.register(r'responses', SurveyResponseViewSet, basename='survey-responses')

urlpatterns = [
    path('', include(router.urls)),
    path('', include(surveys_router.urls)),
]