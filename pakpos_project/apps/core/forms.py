from django import forms


class SystemSettingsForm(forms.Form):
    """
    Settings Form allowing Admins to configure all .env application,
    branding, and POS settings directly from the management portal.
    """
    # 1. Branding & Store Identity
    app_name = forms.CharField(
        label="Store / Business Name",
        max_length=60,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. PakPOS, Bistro 99'})
    )
    app_subtitle = forms.CharField(
        label="Subtitle / Slogan",
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Management Portal'})
    )
    app_currency = forms.CharField(
        label="Currency Symbol / Code",
        max_length=10,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. PKR, Rs., $, AED'})
    )
    app_footer_text = forms.CharField(
        label="Receipt & Invoice Footer Message",
        max_length=250,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. PakPOS — Thank you for your visit!'})
    )
    time_zone = forms.ChoiceField(
        label="System Timezone",
        choices=[
            ('Asia/Karachi', 'Asia/Karachi (PKT +05:00)'),
            ('Asia/Dubai', 'Asia/Dubai (GST +04:00)'),
            ('Asia/Riyadh', 'Asia/Riyadh (AST +03:00)'),
            ('Asia/Dhaka', 'Asia/Dhaka (BST +06:00)'),
            ('Asia/Kolkata', 'Asia/Kolkata (IST +05:30)'),
            ('Europe/London', 'Europe/London (GMT/BST)'),
            ('America/New_York', 'America/New_York (EST/EDT)'),
            ('UTC', 'UTC (Coordinated Universal Time)'),
        ],
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    # 2. Point of Sale (POS) & Operational Mode
    pos_operation_mode = forms.ChoiceField(
        label="POS Operating Mode",
        choices=[
            ('restaurant', '🍽️ Restaurant / Dine-In (Table Management & Dine-In / Takeaway / Delivery)'),
            ('retail', '🛍️ Retail Supermarket (Fast Barcode Scanner Checkout)'),
            ('cafe', '☕ Cafe & Bakery (Table Selection & Drink Bar)'),
            ('fast_food', '🍔 Fast Food (Counter Ordering & Takeaway)'),
        ],
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    pos_default_tax_percent = forms.DecimalField(
        label="Default Sales Tax (%)",
        max_digits=5,
        decimal_places=2,
        min_value=0,
        max_value=100,
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-input', 'step': '0.01', 'placeholder': '0.00'})
    )
    pos_default_service_charge_percent = forms.DecimalField(
        label="Default Dine-In Service Charge (%)",
        max_digits=5,
        decimal_places=2,
        min_value=0,
        max_value=100,
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-input', 'step': '0.01', 'placeholder': '0.00'})
    )
    pos_default_discount_percent = forms.DecimalField(
        label="Default Order Discount (%)",
        max_digits=5,
        decimal_places=2,
        min_value=0,
        max_value=100,
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-input', 'step': '0.01', 'placeholder': '0.00'})
    )
    pos_auto_apply_discount = forms.BooleanField(
        label="Auto-Apply Default Discount to All Orders",
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-checkbox'})
    )
    pos_default_delivery_charges = forms.DecimalField(
        label="Default Delivery Flat Rate (Amount)",
        max_digits=8,
        decimal_places=2,
        min_value=0,
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-input', 'step': '1.00', 'placeholder': '150.00'})
    )

    # 3. Operations & Timings
    pos_shift_start_hour = forms.IntegerField(
        label="Daily Shift Start Hour (0-23)",
        min_value=0,
        max_value=23,
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-input', 'placeholder': '9'})
    )
    pos_shift_end_hour = forms.IntegerField(
        label="Daily Shift End Hour (0-23)",
        min_value=0,
        max_value=23,
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-input', 'placeholder': '23'})
    )
    products_per_page = forms.IntegerField(
        label="Products Per Page (Pagination)",
        min_value=10,
        max_value=200,
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-input', 'placeholder': '50'})
    )
    session_cookie_age_days = forms.IntegerField(
        label="User Session Login Duration (Days)",
        min_value=1,
        max_value=365,
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-input', 'placeholder': '30'})
    )
    
    # 4. Email Notifications
    owner_email_1 = forms.EmailField(
        label="Owner Email 1 (Primary)",
        required=False,
        widget=forms.EmailInput(attrs={'class': 'form-input', 'placeholder': 'owner1@example.com'})
    )
    owner_email_2 = forms.EmailField(
        label="Owner Email 2",
        required=False,
        widget=forms.EmailInput(attrs={'class': 'form-input', 'placeholder': 'owner2@example.com'})
    )
    owner_email_3 = forms.EmailField(
        label="Owner Email 3",
        required=False,
        widget=forms.EmailInput(attrs={'class': 'form-input', 'placeholder': 'owner3@example.com'})
    )
