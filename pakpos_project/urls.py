"""
URL configuration for pakpos_project project.
"""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('', include('pakpos_project.apps.core.urls')),
    path('products/', include('pakpos_project.apps.products.urls')),
    path('users/', include('pakpos_project.apps.users.urls')),
    path('sales/', include('pakpos_project.apps.sales.urls')),
]
