from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView   # ← yeh line uncomment/add karen

from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),

    path('api/auth/', include('rest_framework.urls')),
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),        # ← add karen
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),        # ← add karen

    path('api/system/', include('crmapp.system.urls')),
    path('api/finance/', include('crmapp.finance.urls')),
    path('api/crm/', include('crmapp.crm.urls')),
    path('api/analytics/', include('crmapp.analytics.urls')),
    path('api/dashboards/', include('crmapp.dashboards.urls')),
    path('api/', include('crmapp.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)