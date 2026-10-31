from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('catalog/', include('catalog.urls')),
    path('subscriptions/', include('subscriptions.urls')),
    path('billing/', include('billing.urls')),
    path('dashboard/', include('dashboard.urls')),
    path('', lambda request: redirect('accounts:login_redirect'), name='home'),
]
