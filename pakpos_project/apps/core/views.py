import os
import io
import sqlite3
import tempfile
import json
from datetime import timedelta
from decimal import Decimal
from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum, Count, F, Q
from django.conf import settings
from django.http import FileResponse, HttpResponse, Http404
from pakpos_project.apps.products.models import Product, Category
from pakpos_project.apps.sales.models import Sale, SaleItem, DiningTable
from pakpos_project.apps.users.models import User
from pakpos_project.apps.expenses.models import Expense
from pakpos_project.apps.users.decorators import admin_required
from pakpos_project.apps.core.models import SystemSetting
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


def get_db_entity_state():
    """
    Dynamically computes state fingerprint (total rows and max primary key) across ALL database tables.
    Covers products, categories, stock, variants, sales, sale items, customers, shifts, expenses, users, etc.
    """
    from django.apps import apps
    from django.db.models import Max
    
    state = {}
    target_apps = ['core', 'products', 'sales', 'expenses', 'users']
    for model in apps.get_models():
        if model._meta.app_label in target_apps and not model._meta.abstract:
            model_key = f"{model._meta.app_label}.{model._meta.model_name}"
            try:
                count = model.objects.count()
                max_id = 0
                fields = [f.name for f in model._meta.fields]
                if 'id' in fields:
                    max_id = model.objects.aggregate(Max('id'))['id__max'] or 0
                elif 'pk' in fields:
                    max_id = model.objects.aggregate(Max('pk'))['pk__max'] or 0
                state[model_key] = {
                    'count': count,
                    'max_id': max_id,
                }
            except Exception:
                pass
    return state


def check_rollback_eligibility():
    """
    Checks if a rollback to pre-restore backup is currently available (i.e. no new data created in any table).
    Returns (eligible: bool, backup_path: str, backup_filename: str, restore_time: str).
    """
    backup_dir = os.path.join(settings.BASE_DIR, 'backups')
    state_file = os.path.join(backup_dir, 'restore_state.json')

    if not os.path.exists(state_file):
        return False, None, None, None

    try:
        with open(state_file, 'r') as f:
            state_data = json.load(f)

        backup_filename = state_data.get('backup_file')
        if not backup_filename:
            return False, None, None, None

        backup_path = os.path.join(backup_dir, backup_filename)
        if not os.path.exists(backup_path):
            try:
                os.remove(state_file)
            except Exception:
                pass
            return False, None, None, None

        initial_state = state_data.get('state_snapshot', {})
        current_state = get_db_entity_state()

        # Check across ALL database tables: if any table has more rows or higher max_id
        has_new_data = False
        for model_key, init_data in initial_state.items():
            curr_data = current_state.get(model_key, {})
            curr_cnt = curr_data.get('count', 0)
            init_cnt = init_data.get('count', 0)
            curr_max_id = curr_data.get('max_id', 0)
            init_max_id = init_data.get('max_id', 0)

            if curr_cnt > init_cnt or curr_max_id > init_max_id:
                has_new_data = True
                break

        # Also check if any entirely new table/model has records that were 0 before
        if not has_new_data:
            for model_key, curr_data in current_state.items():
                if model_key not in initial_state and curr_data.get('count', 0) > 0:
                    has_new_data = True
                    break

        if has_new_data:
            # New data arrived in one or more tables, rollback window expired
            try:
                os.remove(state_file)
            except Exception:
                pass
            return False, None, None, None

        return True, backup_path, backup_filename, state_data.get('restore_time')
    except Exception:
        return False, None, None, None


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

    # Database file stats for backup card
    db_path = str(settings.DATABASES['default']['NAME'])
    db_size_str = "0 KB"
    db_last_modified = None
    if os.path.exists(db_path):
        size_bytes = os.path.getsize(db_path)
        if size_bytes >= 1024 * 1024:
            db_size_str = f"{size_bytes / (1024 * 1024):.2f} MB"
        else:
            db_size_str = f"{size_bytes / 1024:.1f} KB"
        mtime = os.path.getmtime(db_path)
        db_last_modified = timezone.datetime.fromtimestamp(mtime, tz=timezone.get_current_timezone())

    # Check if a pre-restore rollback is available
    can_rollback, rollback_path, rollback_file, rollback_time = check_rollback_eligibility()
    sys_settings = SystemSetting.load()

    context = {
        'title': 'System Settings',
        'form': form,
        'db_size_str': db_size_str,
        'db_last_modified': db_last_modified,
        'can_rollback': can_rollback,
        'rollback_backup_file': rollback_file,
        'rollback_restore_time': rollback_time,
        'gdrive_remote_active': getattr(sys_settings, 'gdrive_remote_active', True),
        'gdrive_last_upload_time': sys_settings.gdrive_last_upload_time,
        'gdrive_last_upload_status': sys_settings.gdrive_last_upload_status,
        'gdrive_last_file_url': sys_settings.gdrive_last_file_url,
    }
    return render(request, 'core/settings.html', context)


from django.contrib.auth.decorators import login_required


@login_required
def download_db_backup_view(request):
    """
    Generate and stream an exact, consistent SQLite database snapshot (.sqlite3).
    Available to both Admin and Cashiers for 1-Click fast data safeguarding.
    """
    timestamp = timezone.now().strftime('%Y-%m-%d_%H-%M-%S')
    filename = f"pakpos_db_backup_{timestamp}.sqlite3"

    temp_dir = tempfile.gettempdir()
    temp_backup_path = os.path.join(temp_dir, filename)

    try:
        db_path = str(settings.DATABASES['default']['NAME'])
        dest_conn = sqlite3.connect(temp_backup_path)

        if os.path.exists(db_path):
            src_conn = sqlite3.connect(f"file:{os.path.abspath(db_path)}?mode=ro", uri=True)
            with dest_conn:
                src_conn.backup(dest_conn)
            src_conn.close()
        else:
            from django.db import connection
            connection.ensure_connection()
            with dest_conn:
                connection.connection.backup(dest_conn)

        dest_conn.close()

        response = FileResponse(open(temp_backup_path, 'rb'), content_type='application/x-sqlite3')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        response['Content-Length'] = os.path.getsize(temp_backup_path)
        return response
    except Exception as e:
        messages.error(request, f"Database backup creation failed: {str(e)}")
        return redirect('core:home' if request.user.role == 'admin' else 'sales:pos')



@admin_required
def restore_db_view(request):
    """
    Safely restores the database from an uploaded .sqlite3 or .json backup file.
    Always takes an automatic safety backup of current data into backups/ before replacing.
    Restricted strictly to Admin users.
    """
    import shutil
    from django.contrib.auth import logout
    from django.core.management import call_command
    from django.db import connections

    if request.method != 'POST':
        return redirect('core:system_settings')

    uploaded_file = request.FILES.get('backup_file')
    if not uploaded_file:
        messages.error(request, "No backup file selected. Please choose a .sqlite3 or .db file.")
        return redirect('core:system_settings')

    filename = uploaded_file.name.lower()
    if not (filename.endswith('.sqlite3') or filename.endswith('.db')):
        messages.error(request, "Invalid file format. Please upload a valid .sqlite3 or .db file.")
        return redirect('core:system_settings')

    # 1. Take automated pre-restore safety snapshot of the active database
    timestamp = timezone.now().strftime('%Y-%m-%d_%H-%M-%S')
    backup_dir = os.path.join(settings.BASE_DIR, 'backups')
    os.makedirs(backup_dir, exist_ok=True)
    safety_backup_name = f"pre_restore_{timestamp}.sqlite3"
    safety_backup_path = os.path.join(backup_dir, safety_backup_name)

    db_path = str(settings.DATABASES['default']['NAME'])
    try:
        if os.path.exists(db_path):
            src_conn = sqlite3.connect(f"file:{os.path.abspath(db_path)}?mode=ro", uri=True)
            dest_conn = sqlite3.connect(safety_backup_path)
            with dest_conn:
                src_conn.backup(dest_conn)
            src_conn.close()
            dest_conn.close()
        else:
            from django.db import connection
            connection.ensure_connection()
            dest_conn = sqlite3.connect(safety_backup_path)
            with dest_conn:
                connection.connection.backup(dest_conn)
            dest_conn.close()

        # Automatic Cleanup: Keep strictly 1 latest backup and delete all older backups
        for item in os.listdir(backup_dir):
            item_path = os.path.join(backup_dir, item)
            if item_path != safety_backup_path and os.path.isfile(item_path):
                try:
                    os.remove(item_path)
                except Exception:
                    pass

    except Exception as e:
        messages.error(request, f"Could not create safety pre-restore backup: {str(e)}. Restore aborted.")
        return redirect('core:system_settings')

    # 2. Process Restore based on file type
    temp_dir = tempfile.gettempdir()
    temp_uploaded_path = os.path.join(temp_dir, f"uploaded_{timestamp}_{uploaded_file.name}")

    try:
        # Write uploaded file to temp disk
        with open(temp_uploaded_path, 'wb+') as destination:
            for chunk in uploaded_file.chunks():
                destination.write(chunk)

        if filename.endswith('.sqlite3') or filename.endswith('.db'):
            # Close all active database connections before replacing binary file
            connections.close_all()

            # Verify valid sqlite3 header
            with open(temp_uploaded_path, 'rb') as f:
                header = f.read(16)
                if not header.startswith(b'SQLite format 3'):
                    raise ValueError("The uploaded file is not a valid SQLite 3 database.")

            # Replace active db.sqlite3 file
            shutil.copyfile(temp_uploaded_path, db_path)

            # Re-open and apply any pending migrations
            call_command('migrate', interactive=False)

        # Clean up temp file
        if os.path.exists(temp_uploaded_path):
            os.remove(temp_uploaded_path)

        # Record post-restore state in restore_state.json for Rollback capability
        state_file = os.path.join(backup_dir, 'restore_state.json')
        with open(state_file, 'w') as f:
            json.dump({
                'restore_time': timezone.now().strftime('%b %d, %Y %I:%M %p'),
                'backup_file': safety_backup_name,
                'state_snapshot': get_db_entity_state()
            }, f, indent=2)

        # 3. Successful restoration: logout session and redirect to login page
        logout(request)
        messages.success(
            request,
            f"Database restored successfully from '{uploaded_file.name}'! "
            f"A safety snapshot was saved as '{safety_backup_name}'. Please log in with your credentials."
        )
        return redirect('users:login')

    except Exception as e:
        # Clean up temp file
        if os.path.exists(temp_uploaded_path):
            os.remove(temp_uploaded_path)
        messages.error(request, f"Database restoration failed: {str(e)}. Your previous database remains intact.")
        return redirect('core:system_settings')


@admin_required
def rollback_db_view(request):
    """
    Rolls back the database to the pre-restore safety backup as long as no new transactions/records have arrived.
    """
    import shutil
    from django.contrib.auth import logout
    from django.core.management import call_command
    from django.db import connections

    if request.method != 'POST':
        return redirect('core:system_settings')

    eligible, backup_path, backup_filename, restore_time = check_rollback_eligibility()
    if not eligible or not backup_path or not os.path.exists(backup_path):
        messages.error(request, "Rollback is no longer available because new transactions/records have been added since the restore.")
        return redirect('core:system_settings')

    try:
        db_path = str(settings.DATABASES['default']['NAME'])
        connections.close_all()

        # Copy pre-restore backup back to active database
        shutil.copyfile(backup_path, db_path)

        # Run migrations if any
        call_command('migrate', interactive=False)

        # Remove state file and backup file since rollback is complete
        backup_dir = os.path.join(settings.BASE_DIR, 'backups')
        state_file = os.path.join(backup_dir, 'restore_state.json')
        if os.path.exists(state_file):
            os.remove(state_file)
        if os.path.exists(backup_path):
            os.remove(backup_path)

        logout(request)
        messages.success(
            request,
            "Database successfully rolled back to your pre-restore version! Please log in with your credentials."
        )
        return redirect('users:login')

    except Exception as e:
        messages.error(request, f"Rollback failed: {str(e)}")
        return redirect('core:system_settings')


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


def extract_gdrive_folder_id(link_or_id):
    """
    Extracts folder ID whether user provides full Google Drive URL or raw folder ID.
    e.g. 'https://drive.google.com/drive/folders/1aBcDeFgHiJk...' -> '1aBcDeFgHiJk...'
    """
    if not link_or_id:
        return ""
    val = str(link_or_id).strip()
    if '/folders/' in val:
        part = val.split('/folders/')[1]
        folder_id = part.split('?')[0].split('/')[0]
        return folder_id.strip()
    return val


def perform_gdrive_backup(settings_obj=None):
    """
    Takes a clean, non-blocking SQLite database snapshot, base64-encodes it,
    and uploads it to Google Drive via Google Apps Script Webhook.
    Returns (success: bool, result_dict: dict, error_msg: str).
    """
    import base64
    import requests
    from pakpos_project.apps.core.logger import log_system_error

    if not settings_obj:
        settings_obj = SystemSetting.load()

    # Check if remote action allows backup
    if not getattr(settings_obj, 'gdrive_remote_active', True):
        return False, {}, "Cloud Backup is currently Not Allowed."

    webhook_url = settings_obj.gdrive_webhook_url or os.environ.get('GOOGLE_SHEETS_WEBHOOK_URL') or "https://script.google.com/macros/s/AKfycbxiTjw3CU_dFFOfEZ0xizJHt-_Cd1Y2vogkB-1E9DdD4tlsGhaqdDjBFj-NFDzu070N/exec"
    folder_id = extract_gdrive_folder_id(settings_obj.gdrive_folder_id_or_link)
    max_files = settings_obj.gdrive_max_files or 3

    timestamp = timezone.now().strftime('%Y-%m-%d_%H-%M-%S')
    filename = f"pakpos_backup_{timestamp}.sqlite3"

    temp_dir = tempfile.gettempdir()
    temp_backup_path = os.path.join(temp_dir, filename)

    try:
        db_path = str(settings.DATABASES['default']['NAME'])
        dest_conn = sqlite3.connect(temp_backup_path)

        if os.path.exists(db_path):
            src_conn = sqlite3.connect(f"file:{os.path.abspath(db_path)}?mode=ro", uri=True)
            with dest_conn:
                src_conn.backup(dest_conn)
            src_conn.close()
        else:
            from django.db import connection
            connection.ensure_connection()
            with dest_conn:
                connection.connection.backup(dest_conn)

        dest_conn.close()

        # Read binary file and base64 encode
        with open(temp_backup_path, 'rb') as f:
            file_base64 = base64.b64encode(f.read()).decode('utf-8')

        if os.path.exists(temp_backup_path):
            os.remove(temp_backup_path)

        payload = {
            'action': 'upload_backup',
            'filename': filename,
            'folder_id': folder_id,
            'max_files': max_files,
            'file_data': file_base64
        }

        resp = requests.post(webhook_url, json=payload, headers={'User-Agent': 'PakPOS/1.0'}, timeout=50)
        if resp.status_code == 200:
            res_json = resp.json()
            if res_json.get('success'):
                file_url = res_json.get('file_url', '')
                settings_obj.gdrive_last_upload_time = timezone.now()
                settings_obj.gdrive_last_upload_status = f"Success: {filename} uploaded"
                settings_obj.gdrive_last_file_url = file_url
                settings_obj.save(update_fields=['gdrive_last_upload_time', 'gdrive_last_upload_status', 'gdrive_last_file_url'])
                log_system_error("GDriveBackup", f"Successfully uploaded {filename} to Google Drive. Retained: {res_json.get('retained_count')}, Deleted: {res_json.get('deleted_count')}")
                return True, res_json, ""
            else:
                err = res_json.get('error', 'Google Drive script returned error.')
                settings_obj.gdrive_last_upload_status = f"Failed: {err}"
                settings_obj.save(update_fields=['gdrive_last_upload_status'])
                return False, res_json, err
        else:
            err = f"HTTP Error {resp.status_code}"
            settings_obj.gdrive_last_upload_status = f"Failed: {err}"
            settings_obj.save(update_fields=['gdrive_last_upload_status'])
            return False, {}, err

    except Exception as e:
        if os.path.exists(temp_backup_path):
            try:
                os.remove(temp_backup_path)
            except Exception:
                pass
        err_msg = str(e)
        settings_obj.gdrive_last_upload_status = f"Failed: {err_msg}"
        settings_obj.save(update_fields=['gdrive_last_upload_status'])
        log_system_error("GDriveBackup", f"Upload exception: {err_msg}")
        return False, {}, err_msg


@login_required
def upload_gdrive_backup_api(request):
    """
    On-demand AJAX endpoint to trigger manual online cloud backup with live progress feedback.
    Accessible to both Admin and Cashiers.
    """
    from django.http import JsonResponse
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST method required.'}, status=405)

    sys_settings = SystemSetting.load()
    if not getattr(sys_settings, 'gdrive_remote_active', True):
        return JsonResponse({'success': False, 'error': 'Backup is currently not allowed.'}, status=403)

    success, res_data, err_msg = perform_gdrive_backup(sys_settings)
    if success:
        return JsonResponse({
            'success': True,
            'message': 'Online backup completed successfully!',
            'file_name': res_data.get('file_name', ''),
            'file_url': res_data.get('file_url', ''),
            'retained_count': res_data.get('retained_count', 1),
            'deleted_count': res_data.get('deleted_count', 0),
            'last_upload_time': timezone.localtime(timezone.now()).strftime('%b %d, %Y %I:%M %p')
        })
    else:
        err_lower = (err_msg or '').lower()
        if 'permission' in err_lower or 'driveapp' in err_lower or 'authorization' in err_lower:
            user_error = 'Google Drive permission required. Please authorize Apps Script on Google.'
        elif 'folder' in err_lower:
            user_error = 'Invalid Google Drive folder link or permission denied.'
        elif 'not allowed' in err_lower:
            user_error = 'Backup is currently not allowed.'
        else:
            user_error = 'Backup failed. Please check internet connection.'

        return JsonResponse({
            'success': False,
            'error': user_error
        }, status=400)


