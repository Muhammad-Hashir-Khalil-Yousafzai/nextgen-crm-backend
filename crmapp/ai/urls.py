from django.urls import path, include

urlpatterns = [
    path('emotion_detection/', include('crmapp.ai.emotion_detection.urls')),
    path('xai/', include('crmapp.ai.xai.urls')),
    path('recommendation/', include('crmapp.ai.recommendation.urls')),

]