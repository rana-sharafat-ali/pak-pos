from django.conf import settings
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db.models import Q, Count
from django.core.paginator import Paginator
from .models import Product, ProductVariant, Category
from .forms import ProductForm, ProductVariantFormSet, CategoryForm
from .services import fetch_google_sheets_csv, parse_and_import_products
from pakpos_project.apps.users.decorators import manager_or_admin_required


@manager_or_admin_required
def product_list(request):
    """
    List products matching the RetailOS SaaS table layout with 10 entries per page pagination
    """
    query = request.GET.get('q', '').strip()
    category_id = request.GET.get('category', '').strip()
    status = request.GET.get('status', '').strip()
    product_type = request.GET.get('type', '').strip()

    products = Product.objects.select_related('category').prefetch_related('variants').all()

    # Search filter (name, description, category, variant, ID, and barcode scan)
    if query:
        search_filter = (
            Q(name__icontains=query) |
            Q(description__icontains=query) |
            Q(category__name__icontains=query) |
            Q(variants__name__icontains=query)
        )

        # Check if query is Barcode format (e.g., 80000101, 80001202, 80000100)
        if query.startswith('800') and query.isdigit():
            try:
                # 800 + [ProductID (3+ digits)] + [VariantID (2 digits)]
                if len(query) >= 6:
                    prod_id = int(query[3:-2])
                    search_filter |= Q(id=prod_id)
                else:
                    prod_id = int(query[3:])
                    search_filter |= Q(id=prod_id)
            except ValueError:
                pass

        # Check if raw number matches Product ID or Variant ID
        if query.isdigit():
            try:
                num = int(query)
                search_filter |= Q(id=num) | Q(variants__id=num)
            except ValueError:
                pass

        products = products.filter(search_filter)

    # Category filter
    if category_id:
        products = products.filter(category_id=category_id)

    # Status filter
    if status == 'in_stock':
        products = products.filter(Q(stock_quantity__gt=5) | Q(variants__stock_quantity__gt=5)).distinct()
    elif status == 'low_stock':
        products = products.filter(
            (Q(stock_quantity__gt=0) & Q(stock_quantity__lte=5)) |
            (Q(variants__stock_quantity__gt=0) & Q(variants__stock_quantity__lte=5))
        ).distinct()
    elif status == 'out_of_stock':
        products = products.filter(
            (Q(has_variants=False) & Q(stock_quantity=0)) |
            (Q(has_variants=True) & ~Q(variants__stock_quantity__gt=0))
        ).distinct()

    # Product Type filter
    if product_type in ['single', 'simple']:
        products = products.filter(has_variants=False)
    elif product_type in ['variant', 'variants']:
        products = products.filter(has_variants=True)

    # Metric counts
    total_products_count = Product.objects.count()
    low_stock_count = Product.objects.filter(
        (Q(stock_quantity__gt=0) & Q(stock_quantity__lte=5)) |
        (Q(variants__stock_quantity__gt=0) & Q(variants__stock_quantity__lte=5))
    ).distinct().count()
    active_categories_count = Category.objects.filter(products__isnull=False).distinct().count()

    categories = Category.objects.annotate(product_count=Count('products')).all()

    # Pagination: 50 items per page by default, configurable
    per_page = getattr(settings, 'PRODUCTS_PER_PAGE', 50)
    paginator = Paginator(products, per_page)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    context = {
        'products': page_obj,
        'page_obj': page_obj,
        'paginator': paginator,
        'filtered_total': products.count(),
        'categories': categories,
        'selected_category': category_id,
        'selected_status': status,
        'query': query,
        'total_products_count': total_products_count,
        'low_stock_count': low_stock_count,
        'active_categories_count': active_categories_count,
    }
    return render(request, 'products/product_list.html', context)


@manager_or_admin_required
def product_detail(request, pk):
    """
    View single product details and all its size variations
    """
    product = get_object_or_404(
        Product.objects.select_related('category').prefetch_related('variants'), 
        pk=pk
    )
    variants = product.variants.all()
    context = {
        'product': product,
        'variants': variants,
    }
    return render(request, 'products/product_detail.html', context)


def get_form_first_error(form, formset=None):
    """
    Extract the most specific, human-readable error message with field name for clear flash alerts
    """
    field_labels = {
        'name': 'Product Name',
        'base_price': 'Standard Selling Price',
        'cost_price': 'Cost Price',
        'category': 'Category',
        'stock_quantity': 'Stock Quantity',
    }
    for field, errors in form.errors.items():
        label = field_labels.get(field, field.replace('_', ' ').capitalize())
        for error in errors:
            if error.lower() == 'this field is required.':
                return f'"{label}" is required. Please fill this field.'
            if error.startswith('A product with the same name') or error.startswith('A multi-size product'):
                return error
            return f'{label}: {error}'
    if formset:
        for f in formset.forms:
            for field, errors in f.errors.items():
                vlabel = 'Size/Variant ' + field.replace('_', ' ').capitalize()
                for error in errors:
                    if error.lower() == 'this field is required.':
                        return f'"{vlabel}" is required in sizes table.'
                    return f'{vlabel}: {error}'
        for error in formset.non_form_errors():
            return error
    return 'Please check the highlighted fields and correct the errors below.'


@manager_or_admin_required
def product_create(request):
    """
    Create a new Product with optional size variants
    """
    if request.method == 'POST':
        form = ProductForm(request.POST)
        formset = ProductVariantFormSet(request.POST)
        if form.is_valid():
            if form.cleaned_data.get('has_variants'):
                product = form.save()
                formset = ProductVariantFormSet(request.POST, instance=product)
                if formset.is_valid():
                    formset.save()
                    messages.success(request, f'Product "{product.name}" created successfully!')
                    return redirect('products:product_list')
                else:
                    # Clean up unsaved/invalid product on formset error
                    product.delete()
                    messages.error(request, get_form_first_error(form, formset))
            else:
                product = form.save()
                messages.success(request, f'Product "{product.name}" created successfully!')
                return redirect('products:product_list')
        else:
            messages.error(request, get_form_first_error(form, formset))
    else:
        form = ProductForm()
        formset = ProductVariantFormSet()

    categories = Category.objects.all()
    context = {
        'form': form,
        'formset': formset,
        'title': 'Add New Product',
        'is_edit': False,
        'categories': categories,
    }
    return render(request, 'products/product_form.html', context)


@manager_or_admin_required
def product_update(request, pk):
    """
    Update a Product and its size variants
    """
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        form = ProductForm(request.POST, instance=product)
        formset = ProductVariantFormSet(request.POST, instance=product)
        if form.is_valid():
            if form.cleaned_data.get('has_variants'):
                if formset.is_valid():
                    product = form.save()
                    formset.save()
                    messages.success(request, f'Product "{product.name}" updated successfully!')
                    return redirect('products:product_list')
                else:
                    messages.error(request, get_form_first_error(form, formset))
            else:
                product = form.save()
                product.variants.all().delete()
                messages.success(request, f'Product "{product.name}" updated successfully!')
                return redirect('products:product_list')
        else:
            messages.error(request, get_form_first_error(form, formset))
    else:
        form = ProductForm(instance=product)
        formset = ProductVariantFormSet(instance=product)

    context = {
        'form': form,
        'formset': formset,
        'product': product,
        'title': f'Edit Product: {product.name}',
        'is_edit': True,
    }
    return render(request, 'products/product_form.html', context)


@manager_or_admin_required
def product_delete(request, pk):
    """
    Delete a Product
    """
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        name = product.name
        product.delete()
        messages.success(request, f'Product "{name}" deleted successfully.')
        return redirect('products:product_list')

    context = {
        'product': product,
    }
    return render(request, 'products/product_confirm_delete.html', context)


# ================= CATEGORY CRUD VIEWS =================

@manager_or_admin_required
def category_list(request):
    """
    List all categories with product counts and search
    """
    query = request.GET.get('q', '').strip()
    categories = Category.objects.annotate(product_count=Count('products')).all()

    if query:
        categories = categories.filter(
            Q(name__icontains=query) | Q(description__icontains=query)
        )

    context = {
        'categories': categories,
        'query': query,
        'total_count': Category.objects.count(),
    }
    return render(request, 'products/category_list.html', context)


@manager_or_admin_required
def category_create(request):
    """
    Create a new category with interactive emoji picker
    """
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            category = form.save()
            messages.success(request, f'Category "{category.name}" created successfully!')
            return redirect('products:category_list')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = CategoryForm(initial={'icon': '🍕'})

    context = {
        'form': form,
        'title': 'Add New Category',
        'is_edit': False,
    }
    return render(request, 'products/category_form.html', context)


@manager_or_admin_required
def category_update(request, pk):
    """
    Update an existing category and its emoji
    """
    category = get_object_or_404(Category, pk=pk)
    if request.method == 'POST':
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            category = form.save()
            messages.success(request, f'Category "{category.name}" updated successfully!')
            return redirect('products:category_list')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = CategoryForm(instance=category)

    context = {
        'form': form,
        'category': category,
        'title': f'Edit Category: {category.name}',
        'is_edit': True,
    }
    return render(request, 'products/category_form.html', context)


@manager_or_admin_required
def category_delete(request, pk):
    """
    Delete a category
    """
    category = get_object_or_404(Category.objects.annotate(product_count=Count('products')), pk=pk)
    if request.method == 'POST':
        name = category.name
        category.delete()
        messages.success(request, f'Category "{name}" deleted successfully.')
        return redirect('products:category_list')

    context = {
        'category': category,
    }
    return render(request, 'products/category_confirm_delete.html', context)


def extract_selected_ids(request):
    """
    Safely extract integer IDs from either comma-separated string or list in request.POST
    """
    raw_list = request.POST.getlist('selected_ids')
    parsed_ids = []
    for item in raw_list:
        if isinstance(item, str) and ',' in item:
            for sub in item.split(','):
                if sub.strip().isdigit():
                    parsed_ids.append(int(sub.strip()))
        elif str(item).strip().isdigit():
            parsed_ids.append(int(str(item).strip()))
    return list(set(parsed_ids))


@manager_or_admin_required
def product_bulk_delete(request):
    """
    Bulk delete selected products
    """
    if request.method == 'POST':
        ids_list = extract_selected_ids(request)
        if ids_list:
            count = Product.objects.filter(id__in=ids_list).count()
            Product.objects.filter(id__in=ids_list).delete()
            messages.success(request, f'Successfully deleted {count} products.')
        else:
            messages.error(request, 'No products were selected for deletion.')
            
    return redirect('products:product_list')


@manager_or_admin_required
def category_bulk_delete(request):
    """
    Bulk delete selected categories
    """
    if request.method == 'POST':
        ids_list = extract_selected_ids(request)
        if ids_list:
            count = Category.objects.filter(id__in=ids_list).count()
            Category.objects.filter(id__in=ids_list).delete()
            messages.success(request, f'Successfully deleted {count} categories.')
        else:
            messages.error(request, 'No categories were selected for deletion.')
            
    return redirect('products:category_list')


@manager_or_admin_required
def product_bulk_import(request):
    """
    Import products & categories from Google Sheets Link or CSV File Upload.
    Guarantees zero-disk footprint (temporary files immediately deleted).
    """
    if request.method == 'POST':
        import_type = request.POST.get('import_type', 'sheet')
        sheet_url = request.POST.get('sheet_url', '').strip()
        csv_file = request.FILES.get('csv_file')

        csv_content = None
        error_msg = None

        try:
            if import_type == 'sheet' and sheet_url:
                csv_content, error_msg = fetch_google_sheets_csv(sheet_url)
            elif csv_file:
                try:
                    csv_content = csv_file.read().decode('utf-8-sig', errors='replace')
                except Exception as e:
                    error_msg = f"Failed to read CSV file: {str(e)}"
            else:
                error_msg = "Please provide a valid Google Sheets URL or select a CSV file."

            if error_msg:
                messages.error(request, error_msg)
            elif csv_content:
                count, cats_count, errs = parse_and_import_products(csv_content)
                if errs:
                    messages.error(request, " ".join(errs))
                elif count > 0 or cats_count > 0:
                    msg = f"Successfully imported {count} products!"
                    if cats_count > 0:
                        msg += f" Automatically created {cats_count} new categories."
                    messages.success(request, msg)
                    return redirect('products:product_list')
                else:
                    messages.info(request, "No new products were imported (products may already exist).")
        finally:
            # Explicit RAM / Disk memory cleanup
            csv_content = None

    context = {
        'title': 'Bulk Import Products & Categories',
    }
    return render(request, 'products/product_bulk_import.html', context)
