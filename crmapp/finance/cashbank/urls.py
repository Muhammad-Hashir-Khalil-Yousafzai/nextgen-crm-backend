from django.urls import path
from .views import (BankAccountListCreateView, BankAccountDetailView, TransactionListCreateView,
                    ChequeListCreateView, ChequeStatusUpdateView, ReconciliationListView, CashAccountListView)

urlpatterns = [
    path('banks/',                   BankAccountListCreateView.as_view(), name='cb-bank-list'),
    path('banks/<int:pk>/',          BankAccountDetailView.as_view(),     name='cb-bank-detail'),
    path('transactions/',            TransactionListCreateView.as_view(), name='cb-tx-list'),
    path('cheques/',                 ChequeListCreateView.as_view(),      name='cb-cheque-list'),
    path('cheques/<int:pk>/status/', ChequeStatusUpdateView.as_view(),    name='cb-cheque-status'),
    path('reconciliations/',         ReconciliationListView.as_view(),    name='cb-recon-list'),
    path('cash/',                    CashAccountListView.as_view(),       name='cb-cash-list'),
]