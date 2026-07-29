from django.urls import path
from .views import (CategoryListCreateView, CategoryDetailView, CategoryTreeView,
                    ClaimListCreateView, ClaimDetailView, ClaimActionView)

urlpatterns = [
    path('categories/',              CategoryListCreateView.as_view(), name='expense-cat-list'),
    path('categories/tree/',         CategoryTreeView.as_view(),       name='expense-cat-tree'),
    path('categories/<int:pk>/',     CategoryDetailView.as_view(),     name='expense-cat-detail'),
    path('claims/',                  ClaimListCreateView.as_view(),    name='expense-claim-list'),
    path('claims/<int:pk>/',         ClaimDetailView.as_view(),        name='expense-claim-detail'),
    path('claims/<int:pk>/action/',  ClaimActionView.as_view(),        name='expense-claim-action'),
]