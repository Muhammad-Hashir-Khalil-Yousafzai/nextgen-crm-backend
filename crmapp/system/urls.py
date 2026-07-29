# crmapp/system/urls.py
from django.urls import path, include

urlpatterns = [
    path('users/',    include('crmapp.system.usermanage.urls')),
    path('roles/',    include('crmapp.system.roles.urls')),
    path('auth/',     include('crmapp.system.auth_security.urls')),
    path('audit/',    include('crmapp.system.audit.urls')),
    path('settings/', include('crmapp.system.settings_config.urls')),
]