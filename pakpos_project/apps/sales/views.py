import json
from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.db import transaction
from django.db.models import Q, Sum, Count, Avg, F
from django.utils import timezone
from django.conf import settings
from django.core.paginator import Paginator

from pakpos_project.apps.products.models import Product, ProductVariant, Category
from .models import Customer, Sale, SaleItem, CashDrawerShift
from pakpos_project.apps.users.decorators import manager_or_admin_required



@login_required
def pos_terminal_view(request):
    """
    Main Modern POS Terminal Screen:
    Provides category filter pills, fast visual product tiles with variant sizes,
    live barcode search, real-time multi-tab cart engine, and cash tender assistant.
    """
    categories = Category.objects.all().order_by('name')
    products = Product.objects.filter(is_active=True).prefetch_related('variants', 'category').order_by('name')
    
    # Pass initial serialized products for fast instantaneous client-side searching & scanning
    product_catalog_json = []
    for p in products:
        variants_data = []
        if p.has_variants:
            for v in p.variants.filter(is_active=True):
                var_barcode = f"800{p.id:03d}{v.id:02d}"
                variants_data.append({
                    'id': v.id,
                    'name': v.name,
                    'selling_price': float(v.selling_price),
                    'stock_quantity': v.stock_quantity,
                    'barcode': var_barcode,
                })
        
        prod_barcode = f"800{p.id:03d}00"
        product_catalog_json.append({
            'id': p.id,
            'name': p.name,
            'category_id': p.category_id if p.category else 0,
            'category_name': p.category.name if p.category else 'General',
            'category_icon': p.category.icon if p.category and p.category.icon else '📦',
            'has_variants': p.has_variants,
            'base_price': float(p.base_price) if not p.has_variants else 0,
            'price_display': p.price_display,
            'stock_quantity': p.stock_quantity if not p.has_variants else sum(v['stock_quantity'] for v in variants_data),
            'track_stock': p.track_stock,
            'barcode': prod_barcode,
            'variants': variants_data,
        })

    context = {
        'title': 'Point of Sale (POS)',
        'categories': categories,
        'products_json': json.dumps(product_catalog_json),
        'default_tax_percent': getattr(settings, 'POS_DEFAULT_TAX_PERCENT', 0),
        'default_service_charge_percent': getattr(settings, 'POS_DEFAULT_SERVICE_CHARGE_PERCENT', 0),
        'pos_mode': getattr(settings, 'POS_OPERATION_MODE', 'retail'),
    }
    return render(request, 'sales/pos_terminal.html', context)


@login_required
@transaction.atomic
def api_create_sale(request):
    """
    AJAX Endpoint: Process and complete a POS checkout order atomically with stock deduction.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

    try:
        data = json.loads(request.body.decode('utf-8'))
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Invalid JSON payload: {str(e)}'}, status=400)

    cart_items = data.get('items', [])
    if not cart_items:
        return JsonResponse({'success': False, 'error': 'Cart is empty. Please add items to checkout.'}, status=400)

    # 1. Customer Resolution
    customer_obj = None
    customer_phone = (data.get('customer_phone') or '').strip()
    customer_name = (data.get('customer_name') or '').strip()
    customer_email = (data.get('customer_email') or '').strip().lower()
    customer_address = (data.get('customer_address') or '').strip()

    if customer_phone and customer_phone != 'walk_in':
        customer_obj, created = Customer.objects.get_or_create(
            phone=customer_phone,
            defaults={
                'name': customer_name or 'Valued Customer',
                'email': customer_email or None,
                'address': customer_address or None,
            }
        )
        if not created and customer_name and customer_obj.name != customer_name:
            customer_obj.name = customer_name
            if customer_email:
                customer_obj.email = customer_email
            if customer_address:
                customer_obj.address = customer_address
            customer_obj.save()

    # 2. Financial Calculations
    subtotal = Decimal('0.00')
    line_items_to_create = []

    # Atomically lock and verify inventory
    for item in cart_items:
        product_id = item.get('product_id')
        variant_id = item.get('variant_id')
        qty = int(item.get('quantity', 1))
        if qty <= 0:
            continue

        product = Product.objects.select_for_update().filter(id=product_id).first()
        if not product:
            return JsonResponse({'success': False, 'error': f"Product ID {product_id} not found."}, status=400)

        variant = None
        if variant_id:
            variant = ProductVariant.objects.select_for_update().filter(id=variant_id, product=product).first()
            if not variant:
                return JsonResponse({'success': False, 'error': f"Variant ID {variant_id} for {product.name} not found."}, status=400)
            unit_price = variant.selling_price
            cost_price = variant.cost_price
            # Deduct variant stock
            variant.stock_quantity -= qty
            variant.save()
        else:
            unit_price = product.base_price
            cost_price = product.cost_price
            # Deduct product stock if stock tracking is enabled
            if product.track_stock:
                product.stock_quantity -= qty
                product.save()

        line_total = unit_price * qty
        subtotal += line_total

        line_items_to_create.append({
            'product': product,
            'variant': variant,
            'product_name': product.name,
            'variant_name': variant.name if variant else '',
            'unit_price': unit_price,
            'cost_price': cost_price,
            'quantity': qty,
            'discount_amount': Decimal('0.00'),
            'total_price': line_total,
        })

    # Discount Calculation
    discount_type = data.get('discount_type', 'none')
    discount_val = Decimal(str(data.get('discount_value', 0) or 0))
    discount_amount = Decimal('0.00')

    if discount_type == 'fixed':
        discount_amount = min(discount_val, subtotal)
    elif discount_type == 'percentage':
        pct = max(Decimal('0'), min(Decimal('100'), discount_val))
        discount_amount = (subtotal * (pct / Decimal('100'))).quantize(Decimal('0.01'))

    net_after_discount = max(Decimal('0.00'), subtotal - discount_amount)

    # Tax Calculation
    tax_rate = Decimal(str(data.get('tax_rate', getattr(settings, 'POS_DEFAULT_TAX_PERCENT', 0)) or 0))
    tax_amount = (net_after_discount * (tax_rate / Decimal('100'))).quantize(Decimal('0.01')) if tax_rate > 0 else Decimal('0.00')

    # Service Charge Calculation
    service_charge_rate = Decimal(str(data.get('service_charge_rate', getattr(settings, 'POS_DEFAULT_SERVICE_CHARGE_PERCENT', 0)) or 0))
    service_charge_amount = (net_after_discount * (service_charge_rate / Decimal('100'))).quantize(Decimal('0.01')) if service_charge_rate > 0 else Decimal('0.00')

    total_amount = (net_after_discount + tax_amount + service_charge_amount).quantize(Decimal('0.01'))

    # Payment details
    payment_method = data.get('payment_method', Sale.PaymentMethod.CASH)
    amount_tendered = Decimal(str(data.get('amount_tendered', total_amount) or total_amount))
    change_returned = max(Decimal('0.00'), amount_tendered - total_amount) if payment_method == Sale.PaymentMethod.CASH else Decimal('0.00')

    # 3. Create Sale Record
    sale = Sale.objects.create(
        customer=customer_obj,
        cashier=request.user,
        status=Sale.Status.COMPLETED,
        order_type=data.get('order_type', Sale.OrderType.WALK_IN),
        subtotal=subtotal,
        discount_type=discount_type,
        discount_value=discount_val,
        discount_amount=discount_amount,
        tax_rate=tax_rate,
        tax_amount=tax_amount,
        service_charge_rate=service_charge_rate,
        service_charge_amount=service_charge_amount,
        total_amount=total_amount,
        payment_method=payment_method,
        amount_tendered=amount_tendered,
        change_returned=change_returned,
        coupon_code=data.get('coupon_code') or None,
        notes=data.get('notes') or None,
    )

    # 4. Create Sale Line Items
    for item_data in line_items_to_create:
        SaleItem.objects.create(
            sale=sale,
            product=item_data['product'],
            variant=item_data['variant'],
            product_name=item_data['product_name'],
            variant_name=item_data['variant_name'],
            unit_price=item_data['unit_price'],
            cost_price=item_data['cost_price'],
            quantity=item_data['quantity'],
            discount_amount=item_data['discount_amount'],
            total_price=item_data['total_price'],
        )

    return JsonResponse({
        'success': True,
        'sale_id': sale.id,
        'invoice_number': sale.invoice_number,
        'total_amount': float(sale.total_amount),
        'change_returned': float(sale.change_returned),
        'receipt_url': reverse('sales:receipt', kwargs={'pk': sale.id}),
        'invoice_a4_url': reverse('sales:invoice_a4', kwargs={'pk': sale.id}),
    })


@login_required
def api_search_customers(request):
    """
    Autocomplete Customer search by Phone or Name
    """
    q = request.GET.get('q', '').strip()
    if not q:
        return JsonResponse({'customers': []})

    customers = Customer.objects.filter(
        Q(phone__icontains=q) | Q(name__icontains=q)
    )[:10]

    results = []
    for c in customers:
        results.append({
            'id': c.id,
            'name': c.name,
            'phone': c.phone,
            'email': c.email or '',
            'address': c.address or '',
            'total_orders': c.total_orders_count,
        })

    return JsonResponse({'customers': results})


@login_required
def receipt_view(request, pk):
    """
    Renders 80mm / 58mm POS thermal receipt format with instant print script
    """
    sale = get_object_or_404(Sale.objects.select_related('customer', 'cashier').prefetch_related('items'), pk=pk)
    context = {
        'sale': sale,
        'items': sale.items.all(),
        'paper_width': request.GET.get('size', '80mm'),
    }
    return render(request, 'sales/receipt_thermal.html', context)


@login_required
def invoice_a4_view(request, pk):
    """
    Renders clean A4 Corporate Tax Invoice format
    """
    sale = get_object_or_404(Sale.objects.select_related('customer', 'cashier').prefetch_related('items'), pk=pk)
    context = {
        'sale': sale,
        'items': sale.items.all(),
    }
    return render(request, 'sales/invoice_a4.html', context)


@manager_or_admin_required
def sales_ledger_view(request):
    """
    Sales History & Invoices Ledger (Manager & Admin Only):
    List past invoices with filters by invoice number, date range, payment method, cashier, and status.
    """
    query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '').strip()
    payment_filter = request.GET.get('payment', '').strip()
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()

    sales_qs = Sale.objects.select_related('customer', 'cashier').prefetch_related('items').order_by('-created_at')

    if query:
        sales_qs = sales_qs.filter(
            Q(invoice_number__icontains=query) |
            Q(customer__name__icontains=query) |
            Q(customer__phone__icontains=query) |
            Q(cashier__username__icontains=query)
        )

    if status_filter:
        sales_qs = sales_qs.filter(status=status_filter)

    if payment_filter:
        sales_qs = sales_qs.filter(payment_method=payment_filter)

    if date_from:
        sales_qs = sales_qs.filter(created_at__date__gte=date_from)

    if date_to:
        sales_qs = sales_qs.filter(created_at__date__lte=date_to)

    # Calculate Ledger KPIs
    total_sales_count = sales_qs.count()
    completed_sales = sales_qs.filter(status=Sale.Status.COMPLETED)
    total_revenue = completed_sales.aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0.00')
    total_refunds = sales_qs.filter(status=Sale.Status.REFUNDED).aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0.00')
    cash_revenue = completed_sales.filter(payment_method=Sale.PaymentMethod.CASH).aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0.00')
    digital_revenue = completed_sales.filter(payment_method__in=[Sale.PaymentMethod.CARD, Sale.PaymentMethod.WALLET]).aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0.00')

    # Calculate Total Profit & Margin
    completed_items = SaleItem.objects.filter(sale__in=completed_sales)
    total_cogs = completed_items.aggregate(
        cogs=Sum(F('cost_price') * F('quantity'))
    )['cogs'] or Decimal('0.00')

    net_revenue_sum = completed_sales.aggregate(
        net_rev=Sum(F('subtotal') - F('discount_amount'))
    )['net_rev'] or Decimal('0.00')

    total_profit = max(Decimal('0.00'), net_revenue_sum - total_cogs)
    profit_margin_avg = round((total_profit / net_revenue_sum) * 100, 1) if net_revenue_sum > 0 else 0.0

    # Pagination
    paginator = Paginator(sales_qs, 25)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    context = {
        'title': 'Sales Invoices & Order History',
        'sales': page_obj,
        'page_obj': page_obj,
        'paginator': paginator,
        'query': query,
        'status_filter': status_filter,
        'payment_filter': payment_filter,
        'date_from': date_from,
        'date_to': date_to,
        'status_choices': Sale.Status.choices,
        'payment_choices': Sale.PaymentMethod.choices,
        'total_sales_count': total_sales_count,
        'total_revenue': total_revenue,
        'total_refunds': total_refunds,
        'total_profit': total_profit,
        'total_cogs': total_cogs,
        'profit_margin_avg': profit_margin_avg,
        'cash_revenue': cash_revenue,
        'digital_revenue': digital_revenue,
    }
    return render(request, 'sales/sales_ledger.html', context)


@manager_or_admin_required
@transaction.atomic
def sale_refund_view(request, pk):
    """
    Process Full Refund / Return with Automatic Inventory Restock Rollback
    """
    if request.method != 'POST':
        messages.error(request, 'Invalid request method for refund.')
        return redirect('sales:ledger')

    sale = get_object_or_404(Sale.objects.select_for_update().prefetch_related('items'), pk=pk)

    if sale.status == Sale.Status.REFUNDED:
        messages.warning(request, f"Invoice {sale.invoice_number} is already marked as Refunded.")
        return redirect('sales:ledger')

    reason = request.POST.get('refund_reason', 'Customer Return / Cancellation').strip()

    # 1. Restock Inventory Atomically
    for item in sale.items.all():
        if item.variant:
            variant = ProductVariant.objects.select_for_update().filter(id=item.variant.id).first()
            if variant:
                variant.stock_quantity += item.quantity
                variant.save()
        elif item.product:
            product = Product.objects.select_for_update().filter(id=item.product.id).first()
            if product and product.track_stock:
                product.stock_quantity += item.quantity
                product.save()

        item.is_refunded = True
        item.refunded_quantity = item.quantity
        item.save()

    # 2. Update Sale Status
    sale.status = Sale.Status.REFUNDED
    sale.refund_reason = reason
    sale.refunded_at = timezone.now()
    sale.refunded_by = request.user
    sale.save()

    messages.success(request, f"Invoice {sale.invoice_number} successfully refunded. Inventory restored ({sale.total_items_count} items restocked).")
    return redirect('sales:ledger')


@login_required
def daily_shift_summary_view(request):
    """
    Daily Sales Shift & Cash Drawer Reconciliation Report
    """
    today = timezone.localdate()
    sales_today = Sale.objects.filter(created_at__date=today).select_related('cashier')

    # Aggregations by payment method
    completed_today = sales_today.filter(status=Sale.Status.COMPLETED)
    cash_sales = completed_today.filter(payment_method=Sale.PaymentMethod.CASH).aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0.00')
    card_sales = completed_today.filter(payment_method=Sale.PaymentMethod.CARD).aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0.00')
    wallet_sales = completed_today.filter(payment_method=Sale.PaymentMethod.WALLET).aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0.00')
    credit_sales = completed_today.filter(payment_method=Sale.PaymentMethod.CREDIT).aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0.00')
    total_sales = completed_today.aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0.00')
    
    refunds_today = sales_today.filter(status=Sale.Status.REFUNDED).aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0.00')
    net_sales = max(Decimal('0.00'), total_sales - refunds_today)

    # Cashier breakdown
    cashier_breakdown = sales_today.filter(status=Sale.Status.COMPLETED).values('cashier__username').annotate(
        orders_count=Count('id'),
        total_revenue=Sum('total_amount')
    ).order_by('-total_revenue')

    # Profit today
    completed_items_today = SaleItem.objects.filter(sale__in=completed_today)
    total_cogs_today = completed_items_today.aggregate(
        cogs=Sum(F('cost_price') * F('quantity'))
    )['cogs'] or Decimal('0.00')

    net_rev_today = completed_today.aggregate(
        net_rev=Sum(F('subtotal') - F('discount_amount'))
    )['net_rev'] or Decimal('0.00')

    today_profit = max(Decimal('0.00'), net_rev_today - total_cogs_today)
    today_margin = round((today_profit / net_rev_today) * 100, 1) if net_rev_today > 0 else 0.0

    context = {
        'title': 'Daily Shift & Cash Drawer Reconciliation',
        'today': today,
        'total_orders': completed_today.count(),
        'cash_sales': cash_sales,
        'card_sales': card_sales,
        'wallet_sales': wallet_sales,
        'credit_sales': credit_sales,
        'total_sales': total_sales,
        'refunds_today': refunds_today,
        'net_sales': net_sales,
        'today_profit': today_profit,
        'today_margin': today_margin,
        'cashier_breakdown': cashier_breakdown,
        'recent_sales': sales_today.order_by('-created_at')[:10],
    }
    return render(request, 'sales/shift_summary.html', context)
