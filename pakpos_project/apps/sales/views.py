import os
import json
from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
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
                    'selling_price_display': f"PKR {v.selling_price:,.2f}",
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
        'default_discount_percent': getattr(settings, 'POS_DEFAULT_DISCOUNT_PERCENT', 0),
        'default_tax_percent': getattr(settings, 'POS_DEFAULT_TAX_PERCENT', 0),
        'default_service_charge_percent': getattr(settings, 'POS_DEFAULT_SERVICE_CHARGE_PERCENT', 0),
        'default_delivery_charges': getattr(settings, 'POS_DEFAULT_DELIVERY_CHARGES', 150),
        'pos_mode': getattr(settings, 'POS_OPERATION_MODE', 'retail'),
    }
    return render(request, 'sales/pos_terminal.html', context)


@login_required
@require_POST
@transaction.atomic
def api_create_sale(request):
    """
    High-Speed Atomic Sale Finalization & Stock Depletion API Endpoint
    Expects JSON payload with items, customer details, payment method, discounts.
    """
    import json
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON format in request.'}, status=400)

    cart_items = data.get('items', [])
    if not cart_items:
        return JsonResponse({'success': False, 'error': 'Cannot checkout with an empty cart.'}, status=400)

    # 1. Customer Resolution
    customer_phone = data.get('customer_phone')
    customer_name = data.get('customer_name', 'Walk-in Customer')
    customer_email = data.get('customer_email')
    customer_address = data.get('customer_address')
    customer_obj = None

    if customer_phone and customer_phone != 'walk_in':
        customer_obj, created = Customer.objects.get_or_create(
            phone=customer_phone,
            defaults={
                'name': customer_name or 'Valued Customer',
                'email': customer_email or None,
                'address': customer_address or None,
            }
        )
        if not created and customer_name and customer_name != 'Valued Customer' and customer_name != 'Walk-in Customer':
            customer_obj.name = customer_name
            if customer_email: customer_obj.email = customer_email
            if customer_address: customer_obj.address = customer_address
            customer_obj.save()

    # 2. Process Line Items and Calculate Totals inside Atomic Transaction
    subtotal = Decimal('0.00')
    line_items_to_create = []

    for item in cart_items:
        product_id = item.get('product_id')
        variant_id = item.get('variant_id')
        qty = Decimal(str(item.get('quantity', 1)))

        if qty <= 0:
            return JsonResponse({'success': False, 'error': 'Line item quantities must be greater than zero.'}, status=400)

        try:
            product = Product.objects.select_for_update().get(id=product_id, is_active=True)
        except Product.DoesNotExist:
            return JsonResponse({'success': False, 'error': f'Product ID {product_id} is unavailable or deleted.'}, status=404)

        variant = None
        if variant_id:
            try:
                variant = ProductVariant.objects.select_for_update().get(id=variant_id, product=product, is_active=True)
                unit_price = variant.selling_price
                cost_price = variant.cost_price
                variant_name = variant.name
                variant.stock_quantity -= int(qty)
                variant.save()
            except ProductVariant.DoesNotExist:
                return JsonResponse({'success': False, 'error': f'Variant ID {variant_id} is unavailable.'}, status=404)
        else:
            unit_price = product.base_price
            cost_price = product.cost_price
            variant_name = ''
            if product.track_stock:
                product.stock_quantity -= int(qty)
                product.save()

        line_subtotal = (unit_price * qty).quantize(Decimal('0.01'))
        subtotal += line_subtotal

        line_items_to_create.append({
            'product': product,
            'variant': variant,
            'product_name': product.name,
            'variant_name': variant_name,
            'unit_price': unit_price,
            'cost_price': cost_price,
            'quantity': qty,
            'discount_amount': Decimal('0.00'),
            'total_price': line_subtotal,
        })

    # 1. Tax Calculation (calculated on Subtotal)
    tax_rate = Decimal(str(data.get('tax_rate', getattr(settings, 'POS_DEFAULT_TAX_PERCENT', 0)) or 0))
    tax_amount = (subtotal * (tax_rate / Decimal('100'))).quantize(Decimal('0.01')) if tax_rate > 0 else Decimal('0.00')

    # 2. Order Type & Service / Delivery Charge Calculation (calculated on Subtotal)
    order_type = data.get('order_type', Sale.OrderType.WALK_IN)
    
    if order_type in [Sale.OrderType.TAKEAWAY, Sale.OrderType.WALK_IN]:
        service_charge_rate = Decimal('0.00')
        service_charge_amount = Decimal('0.00')
    elif order_type == Sale.OrderType.DELIVERY:
        service_charge_rate = Decimal('0.00')
        if 'service_charge_amount' in data and data.get('service_charge_amount') is not None:
            service_charge_amount = Decimal(str(data.get('service_charge_amount') or 0)).quantize(Decimal('0.01'))
        else:
            service_charge_amount = Decimal(str(getattr(settings, 'POS_DEFAULT_DELIVERY_CHARGES', 150))).quantize(Decimal('0.01'))
    else: # Dine-In
        service_charge_rate = Decimal(str(data.get('service_charge_rate', getattr(settings, 'POS_DEFAULT_SERVICE_CHARGE_PERCENT', 0)) or 0))
        if 'service_charge_amount' in data and data.get('service_charge_amount') is not None:
            service_charge_amount = Decimal(str(data.get('service_charge_amount') or 0)).quantize(Decimal('0.01'))
        else:
            service_charge_amount = (subtotal * (service_charge_rate / Decimal('100'))).quantize(Decimal('0.01')) if service_charge_rate > 0 else Decimal('0.00')

    # 3. Gross Total before Discount
    gross_total = subtotal + tax_amount + service_charge_amount

    # 4. Discount Calculation (Subtracted from Total: Subtotal + Tax + Service Charges)
    discount_type = data.get('discount_type', Sale.DiscountType.NONE)
    discount_val = Decimal(str(data.get('discount_value', 0) or 0))
    discount_amount = Decimal('0.00')

    if discount_type == Sale.DiscountType.FIXED:
        discount_amount = min(discount_val, gross_total)
    elif discount_type == Sale.DiscountType.PERCENTAGE:
        discount_amount = (subtotal * (min(Decimal('100.00'), discount_val) / Decimal('100'))).quantize(Decimal('0.01'))

    # 5. Final Net Payable Amount
    total_amount = max(Decimal('0.00'), (gross_total - discount_amount)).quantize(Decimal('0.01'))

    # Payment details
    payment_method = data.get('payment_method', Sale.PaymentMethod.CASH)
    amount_tendered = Decimal(str(data.get('amount_tendered', total_amount) or total_amount))
    change_returned = max(Decimal('0.00'), amount_tendered - total_amount) if payment_method == Sale.PaymentMethod.CASH else Decimal('0.00')

    # 3. Create Sale Record
    sale = Sale.objects.create(
        customer=customer_obj,
        cashier=request.user,
        status=Sale.Status.COMPLETED,
        order_type=order_type,
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
    digital_revenue = completed_sales.filter(payment_method__in=[Sale.PaymentMethod.CARD, Sale.PaymentMethod.ONLINE]).aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0.00')

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


@login_required
@transaction.atomic
def sale_refund_view(request, pk):
    """
    Process Full Refund / Return with Automatic Inventory Restock Rollback.
    Accessible to Cashiers, Managers, and Admins.
    """
    def _redirect_back():
        referer = request.META.get('HTTP_REFERER')
        if referer and ('shift' in referer or 'history' in referer or 'ledger' in referer):
            return redirect(referer)
        if request.user.role == 'cashier':
            return redirect('sales:shift_summary')
        return redirect('sales:ledger')

    if request.method != 'POST':
        messages.error(request, 'Invalid request method for refund.')
        return _redirect_back()

    sale = get_object_or_404(Sale.objects.select_for_update().prefetch_related('items'), pk=pk)

    if sale.status == Sale.Status.REFUNDED:
        messages.warning(request, f"Invoice {sale.invoice_number} is already marked as Refunded.")
        return _redirect_back()

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
    return _redirect_back()


def _get_shift_context(request):
    """
    Internal helper to build full daily shift summary data.
    """
    today = timezone.localdate()
    sales_today = Sale.objects.filter(created_at__date=today).select_related('cashier')

    # Aggregations by payment method
    completed_today = sales_today.filter(status=Sale.Status.COMPLETED)
    cash_sales = completed_today.filter(payment_method=Sale.PaymentMethod.CASH).aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0.00')
    card_sales = completed_today.filter(payment_method=Sale.PaymentMethod.CARD).aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0.00')
    online_sales = completed_today.filter(payment_method=Sale.PaymentMethod.ONLINE).aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0.00')
    total_sales = completed_today.aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0.00')
    
    refunds_today = sales_today.filter(status=Sale.Status.REFUNDED).aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0.00')
    net_sales = max(Decimal('0.00'), total_sales - refunds_today)

    # Cashier breakdown with full name
    cashier_breakdown_raw = sales_today.filter(status=Sale.Status.COMPLETED).values(
        'cashier__id', 'cashier__username', 'cashier__first_name', 'cashier__last_name'
    ).annotate(
        orders_count=Count('id'),
        total_revenue=Sum('total_amount')
    ).order_by('-total_revenue')

    cashier_breakdown = []
    for item in cashier_breakdown_raw:
        fname = (item['cashier__first_name'] or '').strip()
        lname = (item['cashier__last_name'] or '').strip()
        full_name = f"{fname} {lname}".strip()
        cashier_breakdown.append({
            'username': item['cashier__username'],
            'full_name': full_name if full_name else item['cashier__username'],
            'orders_count': item['orders_count'],
            'total_revenue': item['total_revenue'] or Decimal('0.00'),
        })

    # Payment Methods split percentages
    tot_sales_float = float(total_sales) if total_sales > 0 else 1.0
    cash_pct = round((float(cash_sales) / tot_sales_float) * 100, 1) if total_sales > 0 else 0.0
    card_pct = round((float(card_sales) / tot_sales_float) * 100, 1) if total_sales > 0 else 0.0
    online_pct = round((float(online_sales) / tot_sales_float) * 100, 1) if total_sales > 0 else 0.0

    # Order Types split & percentages
    order_type_data = completed_today.values('order_type').annotate(
        orders_count=Count('id'),
        total_revenue=Sum('total_amount')
    ).order_by('-total_revenue')
    
    order_types_summary = []
    order_type_labels = {
        'walk_in': '🛍️ Walk-in',
        'dine_in': '🍽️ Dine-in',
        'takeaway': '📦 Takeaway',
        'delivery': '🛵 Delivery'
    }
    for ot in order_type_data:
        code = ot['order_type']
        rev = ot['total_revenue'] or Decimal('0.00')
        cnt = ot['orders_count']
        pct = round((float(rev) / tot_sales_float) * 100, 1) if total_sales > 0 else 0.0
        order_types_summary.append({
            'code': code,
            'label': order_type_labels.get(code, code.title()),
            'revenue': rev,
            'orders_count': cnt,
            'pct': pct,
        })

    # Profit today (Managers/Admins only)
    completed_items_today = SaleItem.objects.filter(sale__in=completed_today)
    total_cogs_today = completed_items_today.aggregate(
        cogs=Sum(F('cost_price') * F('quantity'))
    )['cogs'] or Decimal('0.00')

    net_rev_today = completed_today.aggregate(
        net_rev=Sum(F('subtotal') - F('discount_amount'))
    )['net_rev'] or Decimal('0.00')

    today_profit = max(Decimal('0.00'), net_rev_today - total_cogs_today)
    today_margin = round((today_profit / net_rev_today) * 100, 1) if net_rev_today > 0 else 0.0

    # Hourly sales progression for today (dynamic timing from .env)
    from dotenv import load_dotenv
    load_dotenv(settings.BASE_DIR / '.env', override=True)
    
    start_hour = int(os.getenv('POS_SHIFT_START_HOUR', getattr(settings, 'POS_SHIFT_START_HOUR', 9)))
    end_hour = int(os.getenv('POS_SHIFT_END_HOUR', getattr(settings, 'POS_SHIFT_END_HOUR', 23)))

    hourly_dict = {}
    for sale in completed_today:
        sale_local_hour = timezone.localtime(sale.created_at).hour
        if sale_local_hour not in hourly_dict:
            hourly_dict[sale_local_hour] = {'revenue': Decimal('0.00'), 'orders': 0}
        hourly_dict[sale_local_hour]['revenue'] += sale.total_amount
        hourly_dict[sale_local_hour]['orders'] += 1

    hourly_sales = []
    peak_hour_label = "None"
    peak_hour_rev = Decimal('0.00')

    if start_hour <= end_hour:
        shift_hours = list(range(start_hour, end_hour + 1))
    else:
        shift_hours = list(range(start_hour, 24)) + list(range(0, end_hour + 1))

    start_str = f"{start_hour % 12 or 12}:00 {'AM' if start_hour < 12 or start_hour == 24 else 'PM'}"
    end_str = f"{end_hour % 12 or 12}:00 {'AM' if end_hour < 12 or end_hour == 24 else 'PM'}"
    shift_timing_label = f"{start_str} – {end_str}"

    for h in shift_hours:
        h_label = f"{h % 12 or 12} {'AM' if h < 12 or h == 24 else 'PM'}"
        data = hourly_dict.get(h, {'revenue': Decimal('0.00'), 'orders': 0})
        rev = data['revenue'] or Decimal('0.00')
        if rev > peak_hour_rev:
            peak_hour_rev = rev
            peak_hour_label = h_label
        hourly_sales.append({
            'hour': h,
            'label': h_label,
            'revenue': float(rev),
            'orders': data['orders']
        })

    max_rev = max([h['revenue'] for h in hourly_sales] + [1.0])
    for item in hourly_sales:
        item['pct'] = round((item['revenue'] / max_rev) * 100) if max_rev > 0 else 0

    orders_count_today = completed_today.count()
    avg_order_value = round(float(total_sales) / orders_count_today, 2) if orders_count_today > 0 else 0.0

    return {
        'title': 'Daily Shift & Cash Drawer Reconciliation',
        'today': today,
        'shift_timing_label': shift_timing_label,
        'total_orders': orders_count_today,
        'cash_sales': cash_sales,
        'card_sales': card_sales,
        'online_sales': online_sales,
        'total_sales': total_sales,
        'cash_pct': cash_pct,
        'card_pct': card_pct,
        'online_pct': online_pct,
        'order_types_summary': order_types_summary,
        'refunds_today': refunds_today,
        'net_sales': net_sales,
        'today_profit': today_profit,
        'today_margin': today_margin,
        'avg_order_value': avg_order_value,
        'peak_hour_label': peak_hour_label,
        'peak_hour_rev': peak_hour_rev,
        'hourly_sales': hourly_sales,
        'cashier_breakdown': cashier_breakdown,
        'recent_sales': list(sales_today.order_by('-created_at')),
    }


@login_required
def daily_shift_summary_view(request):
    """
    Daily Sales Shift & Cash Drawer Reconciliation Report (Screen View)
    """
    context = _get_shift_context(request)
    return render(request, 'sales/shift_summary.html', context)


@login_required
def shift_print_view(request):
    """
    Dedicated Clean Standalone Print/PDF View for Shift Reconciliation Report
    """
    context = _get_shift_context(request)
    context['printed_at'] = timezone.now()
    return render(request, 'sales/shift_print.html', context)
