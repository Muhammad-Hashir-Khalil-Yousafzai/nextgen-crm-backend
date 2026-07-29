from django.urls import path, include

urlpatterns = [
   path('workflows/', include('crmapp.automation.workflows.urls')),
]

