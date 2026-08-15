from django.shortcuts import render


def product_list(request):
    """
    Product Catalog View (Products App)
    """
    return render(request, 'products/product_list.html')
