import os
import re
import csv
import io
import urllib.request
import urllib.error
from decimal import Decimal, InvalidOperation
from django.db import transaction
from .models import Category, Product, ProductVariant


def convert_google_sheet_url_to_csv_url(url):
    """
    Converts standard Google Sheets view/edit/publish URL to direct CSV export link.
    Supports:
    1. Standard edit URL: https://docs.google.com/spreadsheets/d/DOC_ID/edit#gid=0 -> /export?format=csv&gid=0
    2. Published URL: https://docs.google.com/spreadsheets/d/e/2PACX.../pubhtml -> /pub?output=csv
    """
    url = url.strip()
    
    # Published Web Link
    if '/pubhtml' in url or '/pub' in url:
        base_url = url.split('/pubhtml')[0].split('/pub')[0]
        return f"{base_url}/pub?output=csv"
        
    # Standard Google Sheets Edit/View Link
    match = re.search(r'/spreadsheets/d/([a-zA-Z0-9-_]+)', url)
    if match:
        doc_id = match.group(1)
        gid = '0'
        gid_match = re.search(r'[#&?]gid=([0-9]+)', url)
        if gid_match:
            gid = gid_match.group(1)
        return f"https://docs.google.com/spreadsheets/d/{doc_id}/export?format=csv&gid={gid}"
        
    return url


def parse_and_import_products(csv_content):
    """
    Parses CSV content string and creates Products, Categories, and Variants.
    Guarantees zero-disk footprint (RAM string parsing).
    Returns (imported_count, created_categories_count, errors_list)
    """
    if isinstance(csv_content, bytes):
        csv_content = csv_content.decode('utf-8-sig', errors='replace')

    stream = io.StringIO(csv_content)
    reader = csv.reader(stream)
    
    rows = list(reader)
    if not rows:
        return 0, 0, ["The CSV file / sheet is completely empty."]

    # Find header row
    header_idx = -1
    for idx, row in enumerate(rows[:10]):
        row_str = " ".join([str(cell).lower() for cell in row])
        if "name" in row_str or "product" in row_str or "price" in row_str:
            header_idx = idx
            break

    if header_idx == -1:
        header_idx = 0

    headers = [str(h).strip().lower() for h in rows[header_idx]]
    data_rows = rows[header_idx + 1:]

    # Map column positions
    col_map = {
        'name': -1,
        'category': -1,
        'price': -1,
        'cost_price': -1,
        'stock': -1,
        'description': -1,
        'variants': -1,
    }

    for i, h in enumerate(headers):
        if any(k in h for k in ['product name', 'product', 'item name', 'item']) and col_map['name'] == -1:
            col_map['name'] = i
        elif 'name' in h and col_map['name'] == -1:
            col_map['name'] = i
        elif any(k in h for k in ['category', 'cat']) and col_map['category'] == -1:
            col_map['category'] = i
        elif any(k in h for k in ['selling price', 'base price', 'price', 'rate']) and col_map['price'] == -1:
            col_map['price'] = i
        elif any(k in h for k in ['cost price', 'cost']) and col_map['cost_price'] == -1:
            col_map['cost_price'] = i
        elif any(k in h for k in ['stock quantity', 'stock', 'qty', 'quantity']) and col_map['stock'] == -1:
            col_map['stock'] = i
        elif any(k in h for k in ['description', 'desc', 'notes']) and col_map['description'] == -1:
            col_map['description'] = i
        elif any(k in h for k in ['variant', 'size', 'sizes', 'options']) and col_map['variants'] == -1:
            col_map['variants'] = i

    if col_map['name'] == -1:
        return 0, 0, ["Could not find 'Product Name' column in header."]

    imported_count = 0
    categories_created_count = 0
    errors = []

    existing_categories = {c.name.lower(): c for c in Category.objects.all()}

    with transaction.atomic():
        for line_num, row in enumerate(data_rows, start=header_idx + 2):
            if not row or not any(str(cell).strip() for cell in row):
                continue

            name = str(row[col_map['name']]).strip() if col_map['name'] < len(row) else ''
            if not name:
                continue

            # Category resolution & auto-creation
            cat_name = str(row[col_map['category']]).strip() if col_map['category'] != -1 and col_map['category'] < len(row) else ''
            category_obj = None

            if cat_name:
                cat_key = cat_name.lower()
                if cat_key in existing_categories:
                    category_obj = existing_categories[cat_key]
                else:
                    category_obj = Category.objects.create(
                        name=cat_name,
                        icon='📦',
                        description='Auto-created via Bulk Import'
                    )
                    existing_categories[cat_key] = category_obj
                    categories_created_count += 1

            # Base Price & Cost Price
            price_val = Decimal('0.00')
            if col_map['price'] != -1 and col_map['price'] < len(row):
                raw_p = str(row[col_map['price']]).replace('PKR', '').replace('$', '').replace(',', '').strip()
                try:
                    if raw_p:
                        price_val = Decimal(raw_p)
                except InvalidOperation:
                    price_val = Decimal('0.00')

            cost_val = Decimal('0.00')
            if col_map['cost_price'] != -1 and col_map['cost_price'] < len(row):
                raw_c = str(row[col_map['cost_price']]).replace('PKR', '').replace('$', '').replace(',', '').strip()
                try:
                    if raw_c:
                        cost_val = Decimal(raw_c)
                except InvalidOperation:
                    cost_val = Decimal('0.00')

            # Stock
            stock_val = 0
            if col_map['stock'] != -1 and col_map['stock'] < len(row):
                raw_s = str(row[col_map['stock']]).strip()
                if raw_s.isdigit():
                    stock_val = int(raw_s)

            # Description
            desc_val = str(row[col_map['description']]).strip() if col_map['description'] != -1 and col_map['description'] < len(row) else ''

            # Variants
            variants_raw = str(row[col_map['variants']]).strip() if col_map['variants'] != -1 and col_map['variants'] < len(row) else ''

            # Duplicate Check: exact name + category + price
            if Product.objects.filter(name__iexact=name, category=category_obj, base_price=price_val).exists():
                continue

            has_variants = False
            parsed_variants = []

            if variants_raw:
                # Format: Small:600, Medium:1200 or Small:600|Medium:1200 or Small=600, Large=1800
                chunks = re.split(r'[,|;]', variants_raw)
                for chunk in chunks:
                    if ':' in chunk or '=' in chunk:
                        parts = re.split(r'[:=]', chunk)
                        v_name = parts[0].strip()
                        v_price_str = parts[1].replace('PKR', '').replace('$', '').replace(',', '').strip()
                        try:
                            v_price = Decimal(v_price_str)
                            parsed_variants.append((v_name, v_price))
                        except InvalidOperation:
                            pass

                if parsed_variants:
                    has_variants = True

            # Create Product
            product = Product.objects.create(
                name=name,
                category=category_obj,
                has_variants=has_variants,
                base_price=price_val,
                cost_price=cost_val,
                stock_quantity=stock_val,
                description=desc_val,
                is_active=True
            )
            imported_count += 1

            # Create Child Variants
            if has_variants:
                for v_name, v_price in parsed_variants:
                    ProductVariant.objects.create(
                        product=product,
                        name=v_name,
                        selling_price=v_price,
                        cost_price=cost_val,
                        stock_quantity=stock_val or 50,
                        is_active=True
                    )

    return imported_count, categories_created_count, errors


def fetch_google_sheets_csv(url):
    """
    Downloads Google Sheets CSV data directly into memory via urllib request.
    """
    csv_url = convert_google_sheet_url_to_csv_url(url)
    req = urllib.request.Request(
        csv_url,
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            content = response.read().decode('utf-8-sig', errors='replace')
            return content, None
    except urllib.error.HTTPError as e:
        return None, f"HTTP Error {e.code}: Could not fetch Google Sheet. Make sure link access is set to 'Anyone with the link can view'."
    except urllib.error.URLError as e:
        return None, f"Network Error: {e.reason}"
    except Exception as e:
        return None, f"Failed to fetch Google Sheet: {str(e)}"
