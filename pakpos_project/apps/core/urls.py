from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.home, name='home'),
    path('settings/', views.system_settings_view, name='system_settings'),
    path('api/payment-alert/', views.payment_alert_status_api, name='payment_alert_status'),
]

