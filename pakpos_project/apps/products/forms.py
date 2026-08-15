from django import forms
from django.forms import inlineformset_factory
from .models import Product, ProductVariant, Category


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            'name',
            'category',
            'has_variants',
            'base_price',
            'cost_price',
            'stock_quantity',
            'track_stock',
            'description',
            'is_active',
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'e.g. Chicken Tikka Pizza, Mineral Water, Zinger Burger',
                'required': True
            }),
            'category': forms.Select(attrs={
                'class': 'form-select'
            }),
            'has_variants': forms.CheckboxInput(attrs={
                'class': 'form-checkbox',
                'id': 'id_has_variants'
            }),
            'base_price': forms.NumberInput(attrs={
                'class': 'form-input',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00'
            }),
            'cost_price': forms.NumberInput(attrs={
                'class': 'form-input',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00'
            }),
            'stock_quantity': forms.NumberInput(attrs={
                'class': 'form-input',
                'min': '0',
                'placeholder': '0'
            }),
            'track_stock': forms.CheckboxInput(attrs={
                'class': 'form-checkbox'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-textarea',
                'rows': 3,
                'placeholder': 'Optional details, ingredients or notes...'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-checkbox'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['base_price'].required = False
        self.fields['cost_price'].required = False
        self.fields['stock_quantity'].required = False

    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip()
        if not name:
            raise forms.ValidationError("Product name is required.")
        return name

    def clean(self):
        cleaned_data = super().clean()
        name = cleaned_data.get('name', '').strip()
        category = cleaned_data.get('category')
        has_variants = cleaned_data.get('has_variants', False)
        base_price = cleaned_data.get('base_price') or 0

        if name:
            # Check if product with SAME NAME and SAME CATEGORY exists
            qs = Product.objects.filter(name__iexact=name, category=category)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)

            if not has_variants:
                # Single items: base_price is required
                if base_price is None or base_price <= 0:
                    self.add_error('base_price', 'Standard Selling Price is required for products without size variations.')

                # Single items: check SAME NAME + SAME CATEGORY + SAME PRICE
                qs_dup = qs.filter(has_variants=False, base_price=base_price)
                if qs_dup.exists():
                    cat_name = category.name if category else 'General'
                    self.add_error('name', f'A product with the same name "{name}", category "{cat_name}", and price ({base_price}) already exists.')
            else:
                # Multi-size items: check SAME NAME + SAME CATEGORY
                qs_dup = qs.filter(has_variants=True)
                if qs_dup.exists():
                    cat_name = category.name if category else 'General'
                    self.add_error('name', f'A multi-size product with the name "{name}" already exists in category "{cat_name}".')

        return cleaned_data

    def clean_base_price(self):
        base_price = self.cleaned_data.get('base_price')
        if base_price is not None and base_price < 0:
            raise forms.ValidationError("Price cannot be negative.")
        return base_price or 0

    def clean_cost_price(self):
        cost_price = self.cleaned_data.get('cost_price')
        if cost_price is not None and cost_price < 0:
            raise forms.ValidationError("Cost price cannot be negative.")
        return cost_price or 0

    def clean_stock_quantity(self):
        stock_quantity = self.cleaned_data.get('stock_quantity')
        if stock_quantity is not None and stock_quantity < 0:
            raise forms.ValidationError("Stock quantity cannot be negative.")
        return stock_quantity or 0


class ProductVariantForm(forms.ModelForm):
    class Meta:
        model = ProductVariant
        fields = ['name', 'cost_price', 'selling_price', 'stock_quantity', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-input variant-name',
                'placeholder': 'e.g. Small, Medium, Large, Family'
            }),
            'cost_price': forms.NumberInput(attrs={
                'class': 'form-input',
                'step': '0.01',
                'min': '0',
                'placeholder': 'Cost (PKR)'
            }),
            'selling_price': forms.NumberInput(attrs={
                'class': 'form-input',
                'step': '0.01',
                'min': '0',
                'placeholder': 'Price (PKR)'
            }),
            'stock_quantity': forms.NumberInput(attrs={
                'class': 'form-input',
                'min': '0',
                'placeholder': '0'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-checkbox'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['cost_price'].required = False
        self.fields['stock_quantity'].required = False
        self.fields['is_active'].required = False
        if not self.instance or not self.instance.pk:
            self.fields['is_active'].initial = True

    def clean_is_active(self):
        is_active = self.cleaned_data.get('is_active')
        if is_active is None:
            return True
        return is_active

    def clean_cost_price(self):
        cost_price = self.cleaned_data.get('cost_price')
        if cost_price is not None and cost_price < 0:
            raise forms.ValidationError("Cost price cannot be negative.")
        return cost_price or 0

    def clean_stock_quantity(self):
        stock_quantity = self.cleaned_data.get('stock_quantity')
        if stock_quantity is not None and stock_quantity < 0:
            raise forms.ValidationError("Stock quantity cannot be negative.")
        return stock_quantity or 0


class BaseProductVariantFormSet(forms.BaseInlineFormSet):
    """
    Prevents duplicate sizes / variant names for the same product
    """
    def clean(self):
        super().clean()
        if any(self.errors):
            return

        variant_names = set()
        for form in self.forms:
            if form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                vname = form.cleaned_data.get('name', '').strip().lower()
                if vname:
                    if vname in variant_names:
                        raise forms.ValidationError(f'Duplicate size/variant name "{form.cleaned_data.get("name")}" is not allowed for the same product.')
                    variant_names.add(vname)


ProductVariantFormSet = inlineformset_factory(
    Product,
    ProductVariant,
    form=ProductVariantForm,
    formset=BaseProductVariantFormSet,
    extra=0,
    can_delete=True,
    min_num=0,
    validate_min=False
)


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'icon', 'description']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'e.g. Pizza, Fast Food, Beverages, Desserts',
                'required': True
            }),
            'icon': forms.TextInput(attrs={
                'class': 'form-input',
                'id': 'id_category_icon',
                'placeholder': 'e.g. 🍕, 🍔, 🥤, 📦',
                'style': 'font-size: 1.25rem; width: 120px; text-align: center;'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-textarea',
                'rows': 3,
                'placeholder': 'Optional category description...'
            }),
        }

    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip()
        if not name:
            raise forms.ValidationError("Category name is required.")

        qs = Category.objects.filter(name__iexact=name)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            raise forms.ValidationError(f'A category named "{name}" already exists. Please choose a different category name.')
        return name
