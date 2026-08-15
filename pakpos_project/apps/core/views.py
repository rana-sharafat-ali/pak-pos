from django.shortcuts import render
from pakpos_project.apps.products.models import Product, Category


def home(request):
    """
    Main Landing / Dashboard View (Core App)
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
