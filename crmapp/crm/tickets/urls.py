from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TicketViewSet, TicketReplyViewSet

router = DefaultRouter()
router.register(r'',       TicketViewSet,      basename='ticket')
router.register(r'replies', TicketReplyViewSet, basename='ticket-reply')

urlpatterns = [
    path('', include(router.urls)),
]
