from django.urls import path
from .views import (JournalEntryListCreateView, JournalEntryDetailView,
                    PostJournalEntryView, ReverseJournalEntryView, AccountLedgerView)

urlpatterns = [
    path('entries/',                   JournalEntryListCreateView.as_view(), name='ledger-list'),
    path('entries/<int:pk>/',          JournalEntryDetailView.as_view(),     name='ledger-detail'),
    path('entries/<int:pk>/post/',     PostJournalEntryView.as_view(),       name='ledger-post'),
    path('entries/<int:pk>/reverse/',  ReverseJournalEntryView.as_view(),    name='ledger-reverse'),
    path('account/<int:account_pk>/',  AccountLedgerView.as_view(),          name='ledger-by-account'),
]