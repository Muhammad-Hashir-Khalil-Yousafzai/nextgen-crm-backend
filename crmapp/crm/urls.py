from django.urls import path, include

urlpatterns = [
   path('leads/', include('crmapp.crm.leads.urls')),
   path('contacts/', include('crmapp.crm.contacts.urls')),
   path('companies/', include('crmapp.crm.companies.urls')),
   path('pipeline/',  include('crmapp.crm.pipeline.urls')),
   path('deals/', include('crmapp.crm.deals.urls')),
   path('activities/', include('crmapp.crm.activities.urls')), 
   path('followups/', include('crmapp.crm.followups.urls')),  
   path('contracts/', include('crmapp.crm.contracts.urls')),
   path('tickets/', include('crmapp.crm.tickets.urls')),
   path('feedback/', include('crmapp.crm.feedbacks.urls')),

]

