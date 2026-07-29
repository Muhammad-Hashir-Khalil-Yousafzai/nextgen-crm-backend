from django.urls import path
from .views import (
    VendorListCreateView, 
    BillListCreateView, 
    BillDetailView, 
    BillPayView, 
    BillApproveView, 
    PurchaseOrderListView
)

urlpatterns = [
    path('vendors/',             VendorListCreateView.as_view(), name='aps-vendor-list'),
    path('bills/',               BillListCreateView.as_view(),   name='aps-bill-list'),
    path('bills/<int:pk>/',      BillDetailView.as_view(),       name='aps-bill-detail'),
    path('bills/<int:pk>/pay/',  BillPayView.as_view(),          name='aps-bill-pay'),
    
    # ✅ NEW: Approval Endpoint
    path('bills/<int:pk>/approve/', BillApproveView.as_view(),   name='aps-bill-approve'),
    
    path('purchase-orders/',     PurchaseOrderListView.as_view(),name='aps-po-list'),
]