from django.urls import path
from .views import CustomerListCreateView, CustomerDetailView, InvoiceListCreateView, InvoiceDetailView, RecordPaymentView

urlpatterns = [
    path('customers/',             CustomerListCreateView.as_view(), name='ar-customer-list'),
    path('customers/<int:pk>/',    CustomerDetailView.as_view(),     name='ar-customer-detail'),
    path('invoices/',              InvoiceListCreateView.as_view(),  name='ar-invoice-list'),
    path('invoices/<int:pk>/',     InvoiceDetailView.as_view(),      name='ar-invoice-detail'),
    path('invoices/<int:pk>/pay/', RecordPaymentView.as_view(),      name='ar-pay'),
]