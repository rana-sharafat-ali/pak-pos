from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.home, name='home'),
    path('settings/', views.system_settings_view, name='system_settings'),
    path('settings/backup/sqlite/', views.download_db_backup_view, name='download_db_backup'),
    path('settings/restore/', views.restore_db_view, name='restore_db'),
    path('settings/rollback/', views.rollback_db_view, name='rollback_db'),
    path('settings/backup/gdrive-upload/', views.upload_gdrive_backup_api, name='gdrive_backup_upload'),
    path('core/gdrive/start/', views.gdrive_oauth_start, name='gdrive_oauth_start'),
    path('core/gdrive/callback/', views.gdrive_oauth_callback, name='gdrive_oauth_callback'),
    path('api/payment-alert/', views.payment_alert_status_api, name='payment_alert_status'),
]

