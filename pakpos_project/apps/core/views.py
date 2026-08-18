from django.shortcuts import render, redirect
from django.contrib import messages
from pakpos_project.apps.products.models import Product, Category
from pakpos_project.apps.users.decorators import manager_or_admin_required, admin_required
from .forms import SystemSettingsForm
from .services import get_current_system_settings, save_system_settings


@manager_or_admin_required
def home(request):
    """
    Main Landing / Dashboard View (Core App - Manager & Admin Only)
    """
    all_products = Product.objects.all()
    total_products = all_products.filter(is_active=True).count()
    variant_products_count = all_products.filter(has_variants=True).count()
    simple_products_count = all_products.filter(has_variants=False).count()
    recent_products = Product.objects.select_related('category').prefetch_related('variants').order_by('-created_at')[:5]

    context = {
        'total_products': total_products,
        'variant_products_count': variant_products_count,
        'simple_products_count': simple_products_count,
        'recent_products': recent_products,
    }
    return render(request, 'core/index.html', context)


@admin_required
def system_settings_view(request):
    """
    System & POS Configuration Management View (Admin Only).
    Allows live modification and persistence of .env configurations.
    """
    if request.method == 'POST':
        form = SystemSettingsForm(request.POST)
        if form.is_valid():
            save_system_settings(form.cleaned_data)
            messages.success(request, 'System & POS settings updated successfully!')
            return redirect('core:system_settings')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        current_data = get_current_system_settings()
        form = SystemSettingsForm(initial=current_data)

    context = {
        'title': 'System Settings',
        'form': form,
    }
    return render(request, 'core/settings.html', context)
