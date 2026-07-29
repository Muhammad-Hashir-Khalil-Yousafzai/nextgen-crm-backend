from django.urls import path
from .views import AssetListCreateView, AssetDetailView, AssetAssignView, AssetReturnView, AssetMaintenanceView

urlpatterns = [
    path('',                      AssetListCreateView.as_view(), name='asset-list'),
    path('<int:pk>/',             AssetDetailView.as_view(),     name='asset-detail'),
    path('<int:pk>/assign/',      AssetAssignView.as_view(),     name='asset-assign'),
    path('<int:pk>/return/',      AssetReturnView.as_view(),     name='asset-return'),
    path('<int:pk>/maintenance/', AssetMaintenanceView.as_view(),name='asset-maintenance'),
]