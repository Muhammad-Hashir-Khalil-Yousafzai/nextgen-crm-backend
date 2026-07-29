from django.urls import path, include

urlpatterns = [
    path('coa/', include('crmapp.finance.coa.urls')),
    path('ar/', include('crmapp.finance.invoicear.urls')),  # Remove 'api/finance/' prefix
    path('ap/', include('crmapp.finance.aps.urls')),
    path('cash/', include('crmapp.finance.cashbank.urls')),
    path('assets/', include('crmapp.finance.assets.urls')),
    path('payroll/', include('crmapp.finance.payroll.urls')),
    path('expense/', include('crmapp.finance.expense.urls')),
    path('ledger/', include('crmapp.finance.ledger.urls')),
]