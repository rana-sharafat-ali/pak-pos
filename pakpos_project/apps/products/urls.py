from django.urls import path
from . import views

app_name = 'products'

urlpatterns = [
    # Product CRUD & Bulk Actions
    path('', views.product_list, name='product_list'),
    path('create/', views.product_create, name='product_create'),
    path('bulk-delete/', views.product_bulk_delete, name='product_bulk_delete'),
    path('<int:pk>/', views.product_detail, name='product_detail'),
    path('<int:pk>/edit/', views.product_update, name='product_update'),
    path('<int:pk>/delete/', views.product_delete, name='product_delete'),

    # Category CRUD & Bulk Actions
    path('categories/', views.category_list, name='category_list'),
    path('categories/create/', views.category_create, name='category_create'),
    path('categories/bulk-delete/', views.category_bulk_delete, name='category_bulk_delete'),
    path('categories/<int:pk>/edit/', views.category_update, name='category_update'),
    path('categories/<int:pk>/delete/', views.category_delete, name='category_delete'),
]
