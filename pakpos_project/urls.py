"""
URL configuration for pakpos_project project.
"""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('pakpos_project.apps.core.urls')),
    path('products/', include('pakpos_project.apps.products.urls')),
]
