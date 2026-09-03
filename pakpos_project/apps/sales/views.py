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
from .models import Customer, Sale, SaleItem, CashDrawerShift, DiningTable
from .forms import DiningTableForm, CustomerForm
from pakpos_project.apps.users.decorators import manager_or_admin_required
from pakpos_project.apps.core.services import get_current_system_settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags

def queue_sales_alert(sale, template_name, subject):
    from pakpos_project.apps.core.models import EmailQueue
    try:
        settings = get_current_system_settings()
        emails = [settings.get(f'owner_email_{i}') for i in range(1, 4) if settings.get(f'owner_email_{i}')]
        if not emails:
            return
            
        app_name = settings.get('app_name', 'PakPOS')
        context = {
            'sale': sale,
            'app_name': app_name,
            'currency': settings.get('app_currency', 'PKR')
        }
        html_content = render_to_string(template_name, context)
        text_content = strip_tags(html_content)
        
        email_job = EmailQueue(
            subject=subject.format(app_name=app_name, invoice=sale.invoice_number),
            text_content=text_content,
            html_content=html_content
        )
        email_job.set_emails(emails)
        email_job.save()
    except Exception as e:
        print(f"Error queueing sales alert: {e}")


@login_required
def pos_terminal_view(request):
    """
    Main Modern POS Terminal Screen:
    Provides category filter pills, fast visual product tiles with variant sizes,
    live barcode search, real-time multi-tab cart engine, and cash tender assistant.
    """
    categories = Category.objects.all().order_by('name')
    products = Product.objects.filter(is_active=True).select_related('category').prefetch_related('variants').order_by('name')[:200]
    dining_tables = DiningTable.objects.filter(is_active=True).order_by('floor_section', 'name')
    
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
                    'cost_price': float(v.cost_price or 0),
                    'selling_price_display': f"PKR {v.selling_price:,.2f}",
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
            'cost_price': float(p.cost_price or 0) if not p.has_variants else 0,
            'price_display': p.price_display,
            'barcode': prod_barcode,
            'variants': variants_data,
        })

    sys_settings = get_current_system_settings()
    
    context = {
        'title': 'Point of Sale (POS)',
        'categories': categories,
        'products_json': json.dumps(product_catalog_json),
        'dining_tables': dining_tables,
        'default_discount_percent': sys_settings.get('pos_default_discount_percent', 0),
        'pos_auto_apply_discount': sys_settings.get('pos_auto_apply_discount', False),
        'default_tax_percent': sys_settings.get('pos_default_tax_percent', 0),
        'default_service_charge_percent': sys_settings.get('pos_default_service_charge_percent', 0),
        'default_delivery_charges': sys_settings.get('pos_default_delivery_charges', 150),
        'pos_mode': sys_settings.get('pos_operation_mode', 'retail'),
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
    customer_id = data.get('customer_id')
    customer_phone = str(data.get('customer_phone') or '').strip()
    customer_name = str(data.get('customer_name') or 'Walk-in Customer').strip()
    customer_email = str(data.get('customer_email') or '').strip() or None
    customer_address = str(data.get('customer_address') or '').strip() or None
    customer_obj = None

    if customer_id:
        try:
            customer_obj = Customer.objects.get(id=customer_id)
            if customer_name and customer_name not in ['Valued Customer', 'Walk-in Customer']:
                customer_obj.name = customer_name
            if customer_phone and customer_phone != 'walk_in':
                customer_obj.phone = customer_phone
            if customer_email: customer_obj.email = customer_email
            if customer_address: customer_obj.address = customer_address
            customer_obj.save()
        except Customer.DoesNotExist:
            customer_obj = None

    if not customer_obj:
        if customer_phone and customer_phone != 'walk_in':
            customer_obj, created = Customer.objects.get_or_create(
                phone=customer_phone,
                defaults={
                    'name': customer_name if customer_name not in ['Walk-in Customer', ''] else 'Valued Customer',
                    'email': customer_email,
                    'address': customer_address,
                }
            )
            if not created and customer_name and customer_name not in ['Valued Customer', 'Walk-in Customer']:
                customer_obj.name = customer_name
                if customer_email: customer_obj.email = customer_email
                if customer_address: customer_obj.address = customer_address
                customer_obj.save()
        elif customer_name and customer_name not in ['Walk-in Customer', 'Walk-in', '']:
            customer_obj = Customer.objects.filter(name__iexact=customer_name).first()
            if not customer_obj:
                fallback_phone = f"CUST-{timezone.now().strftime('%m%d%H%M%S')}"
                customer_obj = Customer.objects.create(
                    name=customer_name,
                    phone=fallback_phone,
                    email=customer_email,
                    address=customer_address,
                )

    # 2. Process Line Items and Calculate Totals inside Atomic Transaction
    subtotal = Decimal('0.00')
    total_cogs = Decimal('0.00')
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
                
                variant.stock_quantity -= qty
                variant.save(update_fields=['stock_quantity'])
            except ProductVariant.DoesNotExist:
                return JsonResponse({'success': False, 'error': f'Variant ID {variant_id} is unavailable.'}, status=404)
        else:
            unit_price = product.base_price
            cost_price = product.cost_price
            variant_name = ''
            
            if product.track_stock:
                product.stock_quantity -= qty
                product.save(update_fields=['stock_quantity'])

        line_subtotal = (unit_price * qty).quantize(Decimal('0.01'))
        subtotal += line_subtotal
        if cost_price and cost_price > 0:
            total_cogs += (cost_price * qty).quantize(Decimal('0.01'))

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

    sys_settings = get_current_system_settings()

    # 1. Tax Calculation (calculated on Subtotal)
    tax_rate = Decimal(str(data.get('tax_rate', sys_settings.get('pos_default_tax_percent', 0)) or 0))
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
            service_charge_amount = Decimal(str(sys_settings.get('pos_default_delivery_charges', 150))).quantize(Decimal('0.01'))
    else: # Dine-In
        service_charge_rate = Decimal(str(data.get('service_charge_rate', sys_settings.get('pos_default_service_charge_percent', 0)) or 0))
        if 'service_charge_amount' in data and data.get('service_charge_amount') is not None:
            service_charge_amount = Decimal(str(data.get('service_charge_amount') or 0)).quantize(Decimal('0.01'))
        else:
            service_charge_amount = (subtotal * (service_charge_rate / Decimal('100'))).quantize(Decimal('0.01')) if service_charge_rate > 0 else Decimal('0.00')

    # 3. Gross Total before Discount
    gross_total = subtotal + tax_amount + service_charge_amount

    # 4. Discount Calculation (Discount cannot exceed the Gross Profit Margin: Subtotal - Cost Price)
    # If cost price is 0 (unspecified), maximum discount allowed is subtotal.
    max_allowable_discount = max(Decimal('0.00'), subtotal - total_cogs) if total_cogs > 0 else subtotal

    discount_type = data.get('discount_type', Sale.DiscountType.NONE)
    discount_val = Decimal(str(data.get('discount_value', 0) or 0))
    discount_amount = Decimal('0.00')

    if discount_type == Sale.DiscountType.FIXED:
        discount_amount = min(max(Decimal('0.00'), discount_val), max_allowable_discount)
    elif discount_type == Sale.DiscountType.PERCENTAGE:
        max_pct = round((float(max_allowable_discount) / float(subtotal)) * 100, 2) if subtotal > 0 else 0.0
        discount_pct = min(Decimal(str(max_pct)), max(Decimal('0.00'), discount_val))
        discount_amount = (subtotal * (discount_pct / Decimal('100'))).quantize(Decimal('0.01'))

    # 5. Final Net Payable Amount
    total_amount = max(Decimal('0.00'), (gross_total - discount_amount)).quantize(Decimal('0.01'))

    # Payment details
    payment_method = data.get('payment_method', Sale.PaymentMethod.CASH)
    amount_tendered = Decimal(str(data.get('amount_tendered', total_amount) or total_amount))
    change_returned = max(Decimal('0.00'), amount_tendered - total_amount) if payment_method == Sale.PaymentMethod.CASH else Decimal('0.00')
    
    # Fetch current active shift for this cashier
    active_shift = CashDrawerShift.objects.filter(
        cashier=request.user,
        status=CashDrawerShift.Status.OPEN
    ).first()

    # 3. Create Sale Record
    sale = Sale.objects.create(
        customer=customer_obj,
        cashier=request.user,
        shift=active_shift,
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

    if sale.total_amount >= 10000:
        queue_sales_alert(
            sale, 
            'emails/large_order_alert.html', 
            '[{app_name}] High Value Order Alert: {invoice}'
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
    Autocomplete Customer search by Phone, Name, or Address
    If q is empty, returns recent customers.
    """
    q = request.GET.get('q', '').strip()
    if not q:
        customers = Customer.objects.all().order_by('-created_at')[:10]
    else:
        customers = Customer.objects.filter(
            Q(phone__icontains=q) | Q(name__icontains=q) | Q(email__icontains=q) | Q(address__icontains=q)
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

    return JsonResponse({'customers': results, 'results': results, 'success': True})


@login_required
@require_POST
def api_create_customer(request):
    """
    Instant Customer Creation & Fast Association Endpoint from POS
    """
    import json
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON format.'}, status=400)

    name = str(data.get('name') or '').strip()
    phone = str(data.get('phone') or '').strip()
    email = str(data.get('email') or '').strip() or None
    address = str(data.get('address') or '').strip() or None

    if not name and not phone:
        return JsonResponse({'success': False, 'error': 'Customer Name or Phone Number is required.'}, status=400)

    if not name:
        name = f"Customer {phone}"
    if not phone:
        phone = f"CUST-{timezone.now().strftime('%m%d%H%M%S')}"

    customer, created = Customer.objects.get_or_create(
        phone=phone,
        defaults={
            'name': name,
            'email': email,
            'address': address,
        }
    )
    if not created:
        if name and name not in ['Valued Customer', 'Walk-in Customer']:
            customer.name = name
        if email:
            customer.email = email
        if address:
            customer.address = address
        customer.save()

    return JsonResponse({
        'success': True,
        'customer': {
            'id': customer.id,
            'name': customer.name,
            'phone': customer.phone,
            'email': customer.email or '',
            'address': customer.address or '',
            'total_orders': customer.total_orders_count,
        }
    })


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
        try:
            d_from = timezone.datetime.strptime(date_from, '%Y-%m-%d').date()
            dt_from = timezone.make_aware(timezone.datetime.combine(d_from, timezone.datetime.min.time()))
            sales_qs = sales_qs.filter(created_at__gte=dt_from)
        except ValueError:
            pass

    if date_to:
        try:
            d_to = timezone.datetime.strptime(date_to, '%Y-%m-%d').date()
            dt_to = timezone.make_aware(timezone.datetime.combine(d_to, timezone.datetime.max.time()))
            sales_qs = sales_qs.filter(created_at__lte=dt_to)
        except ValueError:
            pass

    # Calculate Ledger KPIs
    total_sales_count = sales_qs.count()
    completed_sales = sales_qs.filter(status=Sale.Status.COMPLETED)
    total_revenue = completed_sales.aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0.00')
    total_refunds = sales_qs.filter(status=Sale.Status.REFUNDED).aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0.00')
    cash_revenue = completed_sales.filter(payment_method=Sale.PaymentMethod.CASH).aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0.00')
    digital_revenue = completed_sales.filter(payment_method__in=[Sale.PaymentMethod.CARD, Sale.PaymentMethod.ONLINE]).aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0.00')

    # Calculate Total Profit & Margin (Net after item-level refunds)
    completed_items = SaleItem.objects.filter(sale__in=completed_sales)
    total_cogs = completed_items.aggregate(
        cogs=Sum(F('cost_price') * (F('quantity') - F('refunded_quantity')))
    )['cogs'] or Decimal('0.00')

    total_profit = max(Decimal('0.00'), total_revenue - total_cogs)
    profit_margin_avg = round((total_profit / total_revenue) * 100, 1) if total_revenue > 0 else 0.0

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

    # 1. Update items
    for item in sale.items.all():
        item.is_refunded = True
        item.refunded_quantity = item.quantity
        item.save()
        
        if item.variant:
            item.variant.stock_quantity += item.quantity
            item.variant.save(update_fields=['stock_quantity'])
        elif item.product and item.product.track_stock:
            item.product.stock_quantity += item.quantity
            item.product.save(update_fields=['stock_quantity'])

    # 2. Update Sale Status
    sale.status = Sale.Status.REFUNDED
    sale.refund_reason = reason
    sale.refunded_at = timezone.now()
    sale.refunded_by = request.user
    sale.save()

    queue_sales_alert(
        sale, 
        'emails/refund_alert.html', 
        '[{app_name}] Refund Alert: {invoice}'
    )

    messages.success(request, f"Invoice {sale.invoice_number} successfully refunded. Inventory restored ({sale.total_items_count} items restocked).")
    return _redirect_back()


def _get_shift_context(request):
    """
    Internal helper to build full daily shift summary data with accurate drawer reconciliation.
    """
    today = timezone.localdate()
    start_of_day = timezone.make_aware(timezone.datetime.combine(today, timezone.datetime.min.time()))
    end_of_day = timezone.make_aware(timezone.datetime.combine(today, timezone.datetime.max.time()))
    
    sales_today = Sale.objects.filter(created_at__gte=start_of_day, created_at__lte=end_of_day).select_related('cashier')

    # Aggregations by payment method
    completed_today = sales_today.filter(status=Sale.Status.COMPLETED)
    cash_sales = completed_today.filter(payment_method=Sale.PaymentMethod.CASH).aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0.00')
    card_sales = completed_today.filter(payment_method=Sale.PaymentMethod.CARD).aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0.00')
    online_sales = completed_today.filter(payment_method=Sale.PaymentMethod.ONLINE).aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0.00')
    total_sales = completed_today.aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0.00')
    
    refunds_today = sales_today.filter(status=Sale.Status.REFUNDED).aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0.00')
    net_sales = max(Decimal('0.00'), total_sales - refunds_today)

    # Fetch today's shift expenses & calculate physical cash in drawer
    from pakpos_project.apps.expenses.models import Expense
    shift_expenses_qs = Expense.objects.filter(
        Q(date__gte=start_of_day, date__lte=end_of_day) |
        Q(created_at__gte=start_of_day, created_at__lte=end_of_day)
    ).distinct().select_related('category', 'logged_by').order_by('-date')
    
    shift_expenses_total = shift_expenses_qs.aggregate(s=Sum('amount'))['s'] or Decimal('0.00')
    shift_expenses_list = list(shift_expenses_qs)
    
    # Calculate total opening cash from today's shifts
    from pakpos_project.apps.sales.models import CashDrawerShift
    shifts_today = CashDrawerShift.objects.filter(opening_time__gte=start_of_day, opening_time__lte=end_of_day)
    total_opening_cash = shifts_today.aggregate(s=Sum('opening_cash'))['s'] or Decimal('0.00')

    net_cash_in_drawer = total_opening_cash + cash_sales - shift_expenses_total

    # Cashier breakdown with full name & payment channels
    cashier_map = {}
    for sale in completed_today:
        c = sale.cashier
        cid = c.id if c else 0
        uname = c.username if c else 'admin'
        fname = (c.first_name if c else '').strip()
        lname = (c.last_name if c else '').strip()
        full_name = f"{fname} {lname}".strip() or uname

        if cid not in cashier_map:
            cashier_map[cid] = {
                'username': uname,
                'full_name': full_name,
                'orders_count': 0,
                'cash_collected': Decimal('0.00'),
                'card_collected': Decimal('0.00'),
                'online_collected': Decimal('0.00'),
                'total_revenue': Decimal('0.00'),
            }

        cashier_map[cid]['orders_count'] += 1
        cashier_map[cid]['total_revenue'] += sale.total_amount
        if sale.payment_method == Sale.PaymentMethod.CASH:
            cashier_map[cid]['cash_collected'] += sale.total_amount
        elif sale.payment_method == Sale.PaymentMethod.CARD:
            cashier_map[cid]['card_collected'] += sale.total_amount
        elif sale.payment_method == Sale.PaymentMethod.ONLINE:
            cashier_map[cid]['online_collected'] += sale.total_amount

    cashier_breakdown = sorted(cashier_map.values(), key=lambda x: x['total_revenue'], reverse=True)

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
        code = ot['order_type'] or 'walk_in'
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
    total_tax_today = completed_today.aggregate(t=Sum('tax_amount'))['t'] or Decimal('0.00')
    total_charges_today = completed_today.aggregate(sc=Sum('service_charge_amount'))['sc'] or Decimal('0.00')
    total_discounts_today = completed_today.aggregate(d=Sum('discount_amount'))['d'] or Decimal('0.00')
    gross_sales_today = completed_today.aggregate(g=Sum('subtotal'))['g'] or Decimal('0.00')

    completed_items_today = SaleItem.objects.filter(sale__in=completed_today)
    total_cogs_today = completed_items_today.aggregate(
        cogs=Sum(F('cost_price') * (F('quantity') - F('refunded_quantity')))
    )['cogs'] or Decimal('0.00')

    net_rev_basis_today = gross_sales_today - total_discounts_today
    today_profit = max(Decimal('0.00'), net_rev_basis_today - total_cogs_today - shift_expenses_total)
    today_margin = round((today_profit / net_rev_basis_today) * 100, 1) if net_rev_basis_today > 0 else 0.0

    # Hourly sales progression for today (dynamic timing from .env)
    from pakpos_project.apps.core.services import get_current_system_settings
    sys_settings = get_current_system_settings()
    
    start_hour = sys_settings.get('pos_shift_start_hour', 9)
    end_hour = sys_settings.get('pos_shift_end_hour', 23)

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
        'total_opening_cash': total_opening_cash,
        'shift_expenses_total': shift_expenses_total,
        'shift_expenses': shift_expenses_list,
        'total_tax_today': total_tax_today,
        'total_charges_today': total_charges_today,
        'net_cash_in_drawer': net_cash_in_drawer,
        'expected_cash_drawer': net_cash_in_drawer,
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


# ==============================================================================
# RESTAURANT DINING TABLES CRUD (ADMIN & MANAGER)
# ==============================================================================

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
def table_list_view(request):
    """
    Dining Tables Management List & Grid View for Admin / Manager.
    Supports live searching, section filter, and dual List/Grid cards view.
    """
    tables = DiningTable.objects.all()

    query = request.GET.get('q', '').strip()
    if query:
        tables = tables.filter(
            Q(name__icontains=query) | Q(floor_section__icontains=query) | Q(notes__icontains=query)
        )

    section_filter = request.GET.get('section', '').strip()
    if section_filter:
        tables = tables.filter(floor_section=section_filter)

    all_sections = DiningTable.objects.values_list('floor_section', flat=True).distinct().order_by('floor_section')

    total_count = DiningTable.objects.count()
    active_count = DiningTable.objects.filter(is_active=True).count()
    total_capacity = DiningTable.objects.filter(is_active=True).aggregate(Sum('capacity'))['capacity__sum'] or 0

    context = {
        'title': 'Dining Tables',
        'tables': tables,
        'query': query,
        'selected_section': section_filter,
        'all_sections': all_sections,
        'total_count': total_count,
        'active_count': active_count,
        'total_capacity': total_capacity,
    }
    return render(request, 'sales/table_list.html', context)


@manager_or_admin_required
def table_create_view(request):
    """
    Create a new Dining Table
    """
    if request.method == 'POST':
        form = DiningTableForm(request.POST)
        if form.is_valid():
            table = form.save()
            messages.success(request, f'Dining Table "{table.name}" created successfully!')
            return redirect('sales:table_list')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = DiningTableForm(initial={'floor_section': 'Main Hall', 'capacity': 4, 'is_active': True})

    context = {
        'form': form,
        'title': 'Add New Dining Table',
        'is_edit': False,
    }
    return render(request, 'sales/table_form.html', context)


@manager_or_admin_required
def table_update_view(request, pk):
    """
    Update an existing Dining Table
    """
    table = get_object_or_404(DiningTable, pk=pk)
    if request.method == 'POST':
        form = DiningTableForm(request.POST, instance=table)
        if form.is_valid():
            table = form.save()
            messages.success(request, f'Dining Table "{table.name}" updated successfully!')
            return redirect('sales:table_list')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = DiningTableForm(instance=table)

    context = {
        'form': form,
        'table': table,
        'title': f'Edit Dining Table: {table.name}',
        'is_edit': True,
    }
    return render(request, 'sales/table_form.html', context)


@manager_or_admin_required
def table_delete_view(request, pk):
    """
    Delete a Dining Table
    """
    table = get_object_or_404(DiningTable, pk=pk)
    if request.method == 'POST':
        name = table.name
        table.delete()
        messages.success(request, f'Dining Table "{name}" deleted successfully.')
        return redirect('sales:table_list')

    context = {
        'table': table,
        'title': f'Delete Table: {table.name}',
    }
    return render(request, 'sales/table_confirm_delete.html', context)


@manager_or_admin_required
def table_bulk_delete_view(request):
    """
    Bulk delete selected dining tables
    """
    if request.method == 'POST':
        ids_list = extract_selected_ids(request)
        if ids_list:
            count = DiningTable.objects.filter(id__in=ids_list).count()
            DiningTable.objects.filter(id__in=ids_list).delete()
            messages.success(request, f'Successfully deleted {count} dining tables.')
        else:
            messages.error(request, 'No dining tables were selected for deletion.')

    return redirect('sales:table_list')


# ==============================================================================
# CUSTOMER DIRECTORY & RELATIONSHIP MANAGEMENT (CRM)
# ==============================================================================

@manager_or_admin_required
def customer_list_view(request):
    """
    Comprehensive Customer Directory List View for Admin / Manager.
    Displays KPIs, live search, and paginated customer profiles.
    """
    customers_qs = Customer.objects.all()

    query = request.GET.get('q', '').strip()
    if query:
        customers_qs = customers_qs.filter(
            Q(name__icontains=query) |
            Q(phone__icontains=query) |
            Q(email__icontains=query) |
            Q(address__icontains=query)
        )

    # Calculate High-Level CRM Metrics
    total_customers = Customer.objects.count()
    active_buyers = Customer.objects.filter(sales__status=Sale.Status.COMPLETED).distinct().count()
    
    total_customer_spend = Sale.objects.filter(
        customer__isnull=False, 
        status=Sale.Status.COMPLETED
    ).aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0.00')
    
    avg_spend_per_customer = (total_customer_spend / active_buyers) if active_buyers > 0 else Decimal('0.00')

    # Annotate total orders and total spend for sorting
    customers_qs = customers_qs.annotate(
        completed_orders=Count('sales', filter=Q(sales__status=Sale.Status.COMPLETED)),
        lifetime_spend=Sum('sales__total_amount', filter=Q(sales__status=Sale.Status.COMPLETED))
    ).order_by('-created_at')

    # Pagination
    paginator = Paginator(customers_qs, 25)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    # 1. Top 5 VIP Customers by Lifetime Spend (for Chart & Spotlight)
    top_5_vips_qs = Customer.objects.annotate(
        completed_orders=Count('sales', filter=Q(sales__status=Sale.Status.COMPLETED)),
        lifetime_spend=Sum('sales__total_amount', filter=Q(sales__status=Sale.Status.COMPLETED))
    ).filter(lifetime_spend__gt=0).order_by('-lifetime_spend')[:5]

    top_vips_list = []
    top_cust_labels = []
    top_cust_spends = []
    top_cust_orders = []
    medals = ['🥇', '🥈', '🥉', '⭐', '✨']
    for idx, c in enumerate(top_5_vips_qs):
        spend_val = float(c.lifetime_spend or 0)
        top_cust_labels.append(c.name)
        top_cust_spends.append(spend_val)
        top_cust_orders.append(c.completed_orders)
        top_vips_list.append({
            'rank': idx + 1,
            'medal': medals[idx] if idx < len(medals) else '👤',
            'id': c.id,
            'name': c.name,
            'phone': c.phone,
            'completed_orders': c.completed_orders,
            'lifetime_spend': spend_val,
        })

    # 2. Customer Loyalty & Frequency Segments
    vip_count = Customer.objects.annotate(cnt=Count('sales', filter=Q(sales__status=Sale.Status.COMPLETED))).filter(cnt__gte=5).count()
    repeat_count = Customer.objects.annotate(cnt=Count('sales', filter=Q(sales__status=Sale.Status.COMPLETED))).filter(cnt__gte=2, cnt__lt=5).count()
    first_time_count = Customer.objects.annotate(cnt=Count('sales', filter=Q(sales__status=Sale.Status.COMPLETED))).filter(cnt=1).count()
    new_count = Customer.objects.annotate(cnt=Count('sales', filter=Q(sales__status=Sale.Status.COMPLETED))).filter(cnt=0).count()

    segment_labels = ['VIP (5+ Visits)', 'Repeat (2-4 Visits)', 'First-Time (1 Visit)', 'New (0 Visits)']
    segment_data = [vip_count, repeat_count, first_time_count, new_count]

    # 3. Most Returning / Loyal Customer
    most_loyal_customer = Customer.objects.annotate(
        completed_orders=Count('sales', filter=Q(sales__status=Sale.Status.COMPLETED)),
        lifetime_spend=Sum('sales__total_amount', filter=Q(sales__status=Sale.Status.COMPLETED))
    ).filter(completed_orders__gt=0).order_by('-completed_orders', '-lifetime_spend').first()

    # Retention Rate %
    retention_rate = round((float(repeat_count + vip_count) / float(active_buyers)) * 100, 1) if active_buyers > 0 else 0.0

    context = {
        'title': 'Customer Directory',
        'customers': page_obj,
        'page_obj': page_obj,
        'query': query,
        'total_customers': total_customers,
        'active_buyers': active_buyers,
        'total_customer_spend': total_customer_spend,
        'avg_spend_per_customer': avg_spend_per_customer,
        'retention_rate': retention_rate,
        'top_vips': top_vips_list,
        'most_loyal_customer': most_loyal_customer,
        'chart_top_cust_labels_json': json.dumps(top_cust_labels),
        'chart_top_cust_spends_json': json.dumps(top_cust_spends),
        'chart_top_cust_orders_json': json.dumps(top_cust_orders),
        'chart_segments_labels_json': json.dumps(segment_labels),
        'chart_segments_data_json': json.dumps(segment_data),
    }
    return render(request, 'sales/customer_list.html', context)


@manager_or_admin_required
def customer_create_view(request):
    """
    Create a new customer from the admin dashboard
    """
    if request.method == 'POST':
        form = CustomerForm(request.POST)
        if form.is_valid():
            customer = form.save()
            messages.success(request, f'Customer "{customer.name}" ({customer.phone}) registered successfully!')
            return redirect('sales:customer_detail', pk=customer.pk)
        else:
            messages.error(request, 'Please fix the errors indicated below.')
    else:
        form = CustomerForm()

    context = {
        'form': form,
        'title': 'Add New Customer',
        'is_edit': False,
    }
    return render(request, 'sales/customer_form.html', context)


@manager_or_admin_required
def customer_update_view(request, pk):
    """
    Update an existing customer profile
    """
    customer = get_object_or_404(Customer, pk=pk)
    if request.method == 'POST':
        form = CustomerForm(request.POST, instance=customer)
        if form.is_valid():
            customer = form.save()
            messages.success(request, f'Customer profile for "{customer.name}" updated successfully!')
            return redirect('sales:customer_detail', pk=customer.pk)
        else:
            messages.error(request, 'Please fix the errors indicated below.')
    else:
        form = CustomerForm(instance=customer)

    context = {
        'form': form,
        'customer': customer,
        'title': f'Edit Customer: {customer.name}',
        'is_edit': True,
    }
    return render(request, 'sales/customer_form.html', context)


@manager_or_admin_required
def customer_detail_view(request, pk):
    """
    Detailed Customer View showing CRM metrics, contact info, and lifetime sales invoices.
    """
    customer = get_object_or_404(Customer, pk=pk)
    sales = customer.sales.all().prefetch_related('items').order_by('-created_at')

    completed_sales = sales.filter(status=Sale.Status.COMPLETED)
    total_spent = completed_sales.aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0.00')
    total_orders = completed_sales.count()
    avg_order_value = (total_spent / total_orders) if total_orders > 0 else Decimal('0.00')
    last_sale = completed_sales.first()

    context = {
        'title': f'Customer: {customer.name}',
        'customer': customer,
        'sales': sales,
        'total_spent': total_spent,
        'total_orders': total_orders,
        'avg_order_value': avg_order_value,
        'last_sale': last_sale,
    }
    return render(request, 'sales/customer_detail.html', context)


@manager_or_admin_required
def customer_delete_view(request, pk):
    """
    Delete a customer
    """
    customer = get_object_or_404(Customer, pk=pk)
    if request.method == 'POST':
        name = customer.name
        customer.delete()
        messages.success(request, f'Customer "{name}" removed successfully.')
        return redirect('sales:customer_list')

    context = {
        'customer': customer,
        'title': f'Delete Customer: {customer.name}',
    }
    return render(request, 'sales/customer_confirm_delete.html', context)


@manager_or_admin_required
def customer_bulk_delete_view(request):
    """
    Bulk delete selected customers
    """
    if request.method == 'POST':
        ids_list = extract_selected_ids(request)
        if ids_list:
            count = Customer.objects.filter(id__in=ids_list).count()
            Customer.objects.filter(id__in=ids_list).delete()
            messages.success(request, f'Successfully deleted {count} customers.')
        else:
            messages.error(request, 'No customers were selected for deletion.')

    return redirect('sales:customer_list')


from django.http import JsonResponse
from django.db.models import Q

@login_required
def api_search_products(request):
    """
    AJAX endpoint for POS terminal to fetch products dynamically.
    """
    query = request.GET.get('q', '').strip()
    if not query:
        return JsonResponse({'products': []})

    if query.startswith('800') and len(query) >= 5 and query.isdigit():
        try:
            prod_id = int(query[3:6])
            products = Product.objects.filter(id=prod_id, is_active=True).select_related('category').prefetch_related('variants')
        except ValueError:
            products = Product.objects.none()
    else:
        products = Product.objects.filter(name__icontains=query, is_active=True).select_related('category').prefetch_related('variants')[:200]

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
                    'cost_price': float(v.cost_price or 0),
                    'selling_price_display': f"PKR {v.selling_price:,.2f}",
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
            'cost_price': float(p.cost_price or 0) if not p.has_variants else 0,
            'price_display': p.price_display,
            'barcode': prod_barcode,
            'variants': variants_data,
        })
    
    return JsonResponse({'products': product_catalog_json})

from django.views.decorators.http import require_http_methods

@login_required
@require_http_methods(["GET"])
def api_shift_current(request):
    """
    Check if the user has an open shift for TODAY.
    If they have an open shift from yesterday, auto-close it.
    """
    from datetime import date
    from django.db.models import Sum
    from django.utils import timezone
    from pakpos_project.apps.expenses.models import Expense

    today = timezone.localdate()
    active_shifts = CashDrawerShift.objects.filter(cashier=request.user, status=CashDrawerShift.Status.OPEN)

    current_shift = None
    for shift in active_shifts:
        if timezone.localtime(shift.opening_time).date() < today:
            # Shift is from a previous day. Auto-close it.
            # Calculate sales, refunds, expenses
            sales = Sale.objects.filter(shift=shift, status=Sale.Status.COMPLETED)
            total_cash = sales.filter(payment_method=Sale.PaymentMethod.CASH).aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0.00')
            total_card = sales.exclude(payment_method=Sale.PaymentMethod.CASH).aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0.00')
            
            refunds = Sale.objects.filter(shift=shift, status=Sale.Status.REFUNDED).aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0.00')
            expenses = Expense.objects.filter(shift=shift).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')

            shift.total_cash_sales = total_cash
            shift.total_card_sales = total_card
            shift.total_refunds = refunds
            
            # Auto calculate closing cash: Opening + Cash Sales - Refunds - Expenses
            expected_cash = max(Decimal('0.00'), shift.opening_cash + total_cash - refunds - expenses)
            
            shift.closing_cash = expected_cash
            shift.closing_time = timezone.now()
            shift.status = CashDrawerShift.Status.CLOSED
            shift.notes = (shift.notes or "") + "\n[System Auto-Closed on Day Change. Cash Not Counted.]"
            shift.save()
        else:
            current_shift = shift

    if current_shift:
        return JsonResponse({
            'has_open_shift': True,
            'shift_id': current_shift.id,
            'opening_cash': float(current_shift.opening_cash),
            'opening_time': current_shift.opening_time.isoformat()
        })
    else:
        return JsonResponse({'has_open_shift': False})

@login_required
@require_http_methods(["POST"])
def api_shift_open(request):
    """
    Open a new shift for today.
    """
    import json
    try:
        data = json.loads(request.body)
        opening_cash = Decimal(str(data.get('opening_cash', 0)))
    except (ValueError, TypeError, json.JSONDecodeError):
        return JsonResponse({'success': False, 'error': 'Invalid opening cash value.'}, status=400)

    # Check if one already exists
    existing_shift = CashDrawerShift.objects.filter(cashier=request.user, status=CashDrawerShift.Status.OPEN).first()
    if existing_shift:
        return JsonResponse({'success': False, 'error': 'You already have an open shift.'}, status=400)

    shift = CashDrawerShift.objects.create(
        cashier=request.user,
        opening_cash=opening_cash,
        status=CashDrawerShift.Status.OPEN
    )

    return JsonResponse({'success': True, 'shift_id': shift.id})

@manager_or_admin_required
def shift_history_view(request):
    """
    Dedicated view for Admins to see all daily shifts, their opening balances, 
    calculated closing balances, total sales, and expenses.
    """
    shifts = CashDrawerShift.objects.select_related('cashier').order_by('-opening_time')
    
    paginator = Paginator(shifts, 25)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    context = {
        'title': 'Daily Shift Ledger',
        'shifts': page_obj,
        'page_obj': page_obj,
        'paginator': paginator,
    }
    return render(request, 'sales/shift_history.html', context)
