import json
from datetime import timedelta
from decimal import Decimal
from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum, Count, F, Q
from pakpos_project.apps.products.models import Product, Category
from pakpos_project.apps.sales.models import Sale, SaleItem, DiningTable
from pakpos_project.apps.users.models import User
from pakpos_project.apps.expenses.models import Expense
from pakpos_project.apps.users.decorators import admin_required
from .forms import SystemSettingsForm
from .services import get_current_system_settings, save_system_settings


@admin_required
def home(request):
    """
    Executive Analytics & Command Center Dashboard View (Admin Only)
    """
    today = timezone.localdate()
    date_preset = request.GET.get('preset', 'today').strip().lower()
    date_from_str = request.GET.get('date_from', '').strip()
    date_to_str = request.GET.get('date_to', '').strip()
    cashier_id = request.GET.get('cashier', '').strip()
    order_type_filter = request.GET.get('order_type', '').strip()

    # 1. Date Presets & Range Resolution
    start_date = None
    end_date = None
    is_hourly = False
    preset_label = 'Today'

    if date_from_str or date_to_str:
        date_preset = 'custom'
        try:
            if date_from_str:
                start_date = timezone.datetime.strptime(date_from_str, '%Y-%m-%d').date()
            if date_to_str:
                end_date = timezone.datetime.strptime(date_to_str, '%Y-%m-%d').date()
        except ValueError:
            pass
        preset_label = f"{date_from_str or 'Start'} to {date_to_str or 'Now'}"
    elif date_preset == 'today':
        start_date = today
        end_date = today
        is_hourly = True
        preset_label = 'Today'
    elif date_preset == 'yesterday':
        start_date = today - timedelta(days=1)
        end_date = today - timedelta(days=1)
        is_hourly = True
        preset_label = 'Yesterday'
    elif date_preset == 'this_week':
        start_date = today - timedelta(days=today.weekday())
        end_date = today
        is_hourly = False
        preset_label = 'This Week'
    elif date_preset == 'this_month':
        start_date = today.replace(day=1)
        end_date = today
        is_hourly = False
        preset_label = 'This Month'
    elif date_preset == 'last_30_days':
        start_date = today - timedelta(days=30)
        end_date = today
        is_hourly = False
        preset_label = 'Last 30 Days'
    elif date_preset == 'this_year':
        start_date = today.replace(month=1, day=1)
        end_date = today
        is_hourly = False
        preset_label = 'This Year'
    elif date_preset == 'all_time':
        start_date = None
        end_date = None
        is_hourly = False
        preset_label = 'All Time'
    else:
        # Fallback to today
        start_date = today
        end_date = today
        is_hourly = True
        date_preset = 'today'
        preset_label = 'Today'

    # 2. Timezone-Aware DateTime Range & Base Queryset Filtering
    start_datetime = timezone.make_aware(timezone.datetime.combine(start_date, timezone.datetime.min.time())) if start_date else None
    end_datetime = timezone.make_aware(timezone.datetime.combine(end_date, timezone.datetime.max.time())) if end_date else None

    sales_qs = Sale.objects.select_related('customer', 'cashier').prefetch_related('items').all()

    if start_datetime:
        sales_qs = sales_qs.filter(created_at__gte=start_datetime)
    if end_datetime:
        sales_qs = sales_qs.filter(created_at__lte=end_datetime)
    if cashier_id and cashier_id.isdigit():
        sales_qs = sales_qs.filter(cashier_id=int(cashier_id))
    if order_type_filter:
        sales_qs = sales_qs.filter(order_type=order_type_filter)

    completed_sales = sales_qs.filter(status=Sale.Status.COMPLETED)
    refunded_sales = sales_qs.filter(status=Sale.Status.REFUNDED)

    # 3. High-Impact Financial Metrics
    total_orders_count = completed_sales.count()
    total_refunds_count = refunded_sales.count()
    
    gross_sales = completed_sales.aggregate(s=Sum('subtotal'))['s'] or Decimal('0.00')
    total_revenue = completed_sales.aggregate(s=Sum('total_amount'))['s'] or Decimal('0.00')
    total_refunds_amount = refunded_sales.aggregate(s=Sum('total_amount'))['s'] or Decimal('0.00')
    total_discounts = completed_sales.aggregate(s=Sum('discount_amount'))['s'] or Decimal('0.00')
    total_tax = completed_sales.aggregate(s=Sum('tax_amount'))['s'] or Decimal('0.00')
    total_charges = completed_sales.aggregate(s=Sum('service_charge_amount'))['s'] or Decimal('0.00')

    cash_revenue = completed_sales.filter(payment_method=Sale.PaymentMethod.CASH).aggregate(s=Sum('total_amount'))['s'] or Decimal('0.00')
    card_revenue = completed_sales.filter(payment_method=Sale.PaymentMethod.CARD).aggregate(s=Sum('total_amount'))['s'] or Decimal('0.00')
    online_revenue = completed_sales.filter(payment_method=Sale.PaymentMethod.ONLINE).aggregate(s=Sum('total_amount'))['s'] or Decimal('0.00')
    digital_revenue = card_revenue + online_revenue

    # Expenses Calculation (Proper Timezone Bounds)
    expenses_qs = Expense.objects.all()
    if start_datetime:
        expenses_qs = expenses_qs.filter(date__gte=start_datetime)
    if end_datetime:
        expenses_qs = expenses_qs.filter(date__lte=end_datetime)
    
    total_expenses = expenses_qs.aggregate(e=Sum('amount'))['e'] or Decimal('0.00')

    # COGS and Profitability (Net after item-level refunds)
    completed_items = SaleItem.objects.filter(sale__in=completed_sales)
    total_cogs = completed_items.aggregate(
        c=Sum(F('cost_price') * (F('quantity') - F('refunded_quantity')))
    )['c'] or Decimal('0.00')
    
    # Net Profit = Total Revenue - Tax (Govt) - Service/Delivery Charges - COGS (Product Cost) - Operating Expenses
    # Equivalent to: (Gross Sales - Discounts) - COGS - Expenses
    net_revenue_basis = gross_sales - total_discounts
    total_surcharges = total_tax + total_charges
    total_profit = net_revenue_basis - total_cogs - total_expenses
    profit_margin_pct = round((float(total_profit) / float(net_revenue_basis)) * 100, 1) if net_revenue_basis > 0 else 0.0
    
    avg_order_value = round(float(total_revenue) / total_orders_count, 2) if total_orders_count > 0 else 0.0
    total_items_sold = completed_items.aggregate(
        q=Sum(F('quantity') - F('refunded_quantity'))
    )['q'] or 0

    # 4. Chart 1: Revenue Timeline (Hourly or Daily)
    timeline_labels = []
    timeline_revenue = []
    timeline_orders = []

    if is_hourly:
        hourly_map = {h: {'revenue': 0.0, 'orders': 0} for h in range(24)}
        for s in completed_sales:
            local_hr = timezone.localtime(s.created_at).hour
            hourly_map[local_hr]['revenue'] += float(s.total_amount)
            hourly_map[local_hr]['orders'] += 1

        for h in range(24):
            period = 'AM' if h < 12 else 'PM'
            disp_h = h % 12
            if disp_h == 0: disp_h = 12
            timeline_labels.append(f"{disp_h} {period}")
            timeline_revenue.append(round(hourly_map[h]['revenue'], 2))
            timeline_orders.append(hourly_map[h]['orders'])
    else:
        # Group by day
        calc_start = start_date or (today - timedelta(days=30))
        calc_end = end_date or today
        
        # Limit to max 60 data points for responsive visual performance
        total_days = max(1, (calc_end - calc_start).days + 1)
        day_map = {}
        current_day = calc_start
        while current_day <= calc_end:
            day_key = current_day.strftime('%Y-%m-%d')
            day_map[day_key] = {
                'label': current_day.strftime('%d %b'),
                'revenue': 0.0,
                'orders': 0
            }
            current_day += timedelta(days=1)

        for s in completed_sales:
            sale_day = timezone.localtime(s.created_at).date().strftime('%Y-%m-%d')
            if sale_day in day_map:
                day_map[sale_day]['revenue'] += float(s.total_amount)
                day_map[sale_day]['orders'] += 1

        for k in sorted(day_map.keys()):
            timeline_labels.append(day_map[k]['label'])
            timeline_revenue.append(round(day_map[k]['revenue'], 2))
            timeline_orders.append(day_map[k]['orders'])

    # 5. Chart 2: Order Types / Channels Distribution (Includes Walk-In / Counter)
    order_type_map = {
        'walk_in': {'label': 'Walk-In / Counter', 'revenue': 0.0, 'count': 0},
        'dine_in': {'label': 'Dine-In', 'revenue': 0.0, 'count': 0},
        'takeaway': {'label': 'Takeaway', 'revenue': 0.0, 'count': 0},
        'delivery': {'label': 'Delivery', 'revenue': 0.0, 'count': 0},
    }
    for s in completed_sales:
        ot = str(s.order_type or 'walk_in').lower()
        if ot in order_type_map:
            order_type_map[ot]['revenue'] += float(s.total_amount)
            order_type_map[ot]['count'] += 1

    chart_order_type_labels = [v['label'] for v in order_type_map.values()]
    chart_order_type_revenue = [round(v['revenue'], 2) for v in order_type_map.values()]
    chart_order_type_counts = [v['count'] for v in order_type_map.values()]

    # 6. Chart 3: Payment Methods Share
    chart_payment_labels = ['Cash', 'Card', 'Online / Mobile']
    chart_payment_data = [float(cash_revenue), float(card_revenue), float(online_revenue)]

    # 7. Chart 4: Top 5 Best-Selling Products in Filtered Period (Net Units Sold)
    top_items_qs = completed_items.annotate(
        net_qty=F('quantity') - F('refunded_quantity')
    ).values('product_name').annotate(
        total_qty=Sum('net_qty'),
        total_rev=Sum('total_price')
    ).filter(total_qty__gt=0).order_by('-total_qty')[:5]

    top_products_list = []
    chart_top_prod_names = []
    chart_top_prod_qtys = []
    chart_top_prod_revs = []
    for item in top_items_qs:
        top_products_list.append({
            'name': item['product_name'],
            'qty': int(item['total_qty']),
            'revenue': float(item['total_rev']),
        })
        chart_top_prod_names.append(item['product_name'])
        chart_top_prod_qtys.append(int(item['total_qty']))
        chart_top_prod_revs.append(float(item['total_rev']))

    # 8. Chart 5: Expense Categories Breakdown
    exp_cat_qs = expenses_qs.values('category__name').annotate(
        cat_total=Sum('amount')
    ).order_by('-cat_total')

    chart_exp_cat_labels = []
    chart_exp_cat_data = []
    for ec in exp_cat_qs:
        chart_exp_cat_labels.append(ec['category__name'] or 'General')
        chart_exp_cat_data.append(float(ec['cat_total']))

    # 9. Top 3 VIP Customers & Most Returning Customer in Filtered Period
    top_cust_qs = completed_sales.filter(customer__isnull=False).values(
        'customer__id', 'customer__name', 'customer__phone'
    ).annotate(
        spend=Sum('total_amount'),
        orders_count=Count('id')
    ).order_by('-spend')[:3]

    top_3_customers = []
    medals = ['🥇', '🥈', '🥉']
    for idx, c in enumerate(top_cust_qs):
        top_3_customers.append({
            'rank': idx + 1,
            'medal': medals[idx] if idx < 3 else '👤',
            'id': c['customer__id'],
            'name': c['customer__name'],
            'phone': c['customer__phone'],
            'spend': float(c['spend']),
            'orders_count': c['orders_count'],
        })

    most_returning_cust_data = completed_sales.filter(customer__isnull=False).values(
        'customer__id', 'customer__name', 'customer__phone'
    ).annotate(
        spend=Sum('total_amount'),
        orders_count=Count('id')
    ).order_by('-orders_count', '-spend').first()

    # 10. Live Operational Activity
    recent_sales = Sale.objects.select_related('customer', 'cashier').prefetch_related('items').order_by('-created_at')[:6]

    # Inventory Health & Low Stock Alerts
    all_products = Product.objects.all()
    total_products = all_products.filter(is_active=True).count()
    variant_products_count = all_products.filter(has_variants=True).count()
    simple_products_count = all_products.filter(has_variants=False).count()

    cashiers_list = User.objects.filter(is_active=True).order_by('first_name', 'username')

    context = {
        'title': 'Executive Analytics Dashboard',
        'date_preset': date_preset,
        'preset_label': preset_label,
        'date_from': date_from_str,
        'date_to': date_to_str,
        'cashier_id': cashier_id,
        'order_type_filter': order_type_filter,
        'cashiers_list': cashiers_list,
        'order_type_choices': Sale.OrderType.choices,
        
        # Financial KPIs
        'total_revenue': total_revenue,
        'gross_sales': gross_sales,
        'total_cogs': total_cogs,
        'total_expenses': total_expenses,
        'total_profit': total_profit,
        'profit_margin_pct': profit_margin_pct,
        'total_orders_count': total_orders_count,
        'total_refunds_count': total_refunds_count,
        'total_refunds_amount': total_refunds_amount,
        'total_discounts': total_discounts,
        'total_tax': total_tax,
        'total_charges': total_charges,
        'total_surcharges': total_surcharges,
        'net_revenue_basis': net_revenue_basis,
        'avg_order_value': avg_order_value,
        'total_items_sold': total_items_sold,
        'cash_revenue': cash_revenue,
        'digital_revenue': digital_revenue,
        'card_revenue': card_revenue,
        'online_revenue': online_revenue,

        # Chart JSON Datasets
        'timeline_labels_json': json.dumps(timeline_labels),
        'timeline_revenue_json': json.dumps(timeline_revenue),
        'timeline_orders_json': json.dumps(timeline_orders),
        'order_type_labels_json': json.dumps(chart_order_type_labels),
        'order_type_revenue_json': json.dumps(chart_order_type_revenue),
        'order_type_counts_json': json.dumps(chart_order_type_counts),
        'payment_labels_json': json.dumps(chart_payment_labels),
        'payment_data_json': json.dumps(chart_payment_data),
        'top_prod_names_json': json.dumps(chart_top_prod_names),
        'top_prod_qtys_json': json.dumps(chart_top_prod_qtys),
        'top_prod_revs_json': json.dumps(chart_top_prod_revs),
        'exp_cat_labels_json': json.dumps(chart_exp_cat_labels),
        'exp_cat_data_json': json.dumps(chart_exp_cat_data),
        'top_products_list': top_products_list,
        'top_3_customers': top_3_customers,
        'most_returning_customer': most_returning_cust_data,

        # Operational Widgets
        'recent_sales': recent_sales,
        'total_products': total_products,
        'variant_products_count': variant_products_count,
        'simple_products_count': simple_products_count,
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


def payment_alert_status_api(request):
    """
    Lightweight JSON endpoint to provide live Payment Alert status to frontend client polling.
    """
    from django.http import JsonResponse
    from pakpos_project.apps.core.models import PaymentAlert
    
    alert = PaymentAlert.load()
    return JsonResponse({
        'is_active': alert.is_active,
        'is_popup_active': alert.is_popup_active,
        'is_navbar_active': alert.is_navbar_active,
        'interval_minutes': alert.interval_minutes,
        'pending_month': alert.pending_month,
        'pending_amount': alert.pending_amount,
        'account_info': alert.account_info,
        'alert_title': alert.alert_title,
        'alert_message': alert.alert_message,
        'due_date': alert.due_date,
        'contact_info': alert.contact_info,
    })


