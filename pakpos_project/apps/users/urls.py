from django.urls import path
from . import views

app_name = 'users'

urlpatterns = [
    # Auth & Sessions
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('change-password/', views.change_own_password, name='change_own_password'),

    # Admin User Management
    path('', views.user_list, name='user_list'),
    path('create/', views.user_create, name='user_create'),
    path('<int:pk>/edit/', views.user_update, name='user_update'),
    path('<int:pk>/reset-password/', views.user_reset_password, name='user_reset_password'),
    path('<int:pk>/toggle/', views.user_toggle_status, name='user_toggle_status'),
    path('<int:pk>/delete/', views.user_delete, name='user_delete'),
]
