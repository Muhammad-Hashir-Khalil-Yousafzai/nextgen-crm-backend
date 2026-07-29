from django.urls import path
from .views import AccountListCreateView, AccountDetailView, AccountToggleStatusView, AccountTreeView, AuditLogListView

urlpatterns = [
    path('accounts/',                        AccountListCreateView.as_view(),  name='coa-list'),
    path('accounts/tree/',                   AccountTreeView.as_view(),        name='coa-tree'),
    path('accounts/<int:pk>/',               AccountDetailView.as_view(),      name='coa-detail'),
    path('accounts/<int:pk>/toggle-status/', AccountToggleStatusView.as_view(),name='coa-toggle'),
    path('audit/',                           AuditLogListView.as_view(),       name='coa-audit'),
]