from decimal import Decimal
from django import forms
from django.utils import timezone
from .models import (
    BusinessSettings,
    Sale,
    Delivery,
    Expense,
    InventoryAdjustment,
)


class SaleForm(forms.ModelForm):
    sale_date = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
        initial=timezone.now
    )

    class Meta:
        model = Sale
        fields = ['customer_name', 'quantity', 'sale_date', 'notes']
        widgets = {
            'customer_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Walk-in Customer / Hotel / Retailer (optional)'
            }),
            'quantity': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'placeholder': 'Number of eggs'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Additional notes (e.g. cash, M-Pesa, delivery note)'
            }),
        }

    def clean_quantity(self):
        quantity = self.cleaned_data.get('quantity')
        if not quantity or quantity <= 0:
            raise forms.ValidationError("Please enter a valid egg quantity of at least 1.")
        return quantity


class DeliveryForm(forms.ModelForm):
    delivery_date = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
        initial=timezone.now
    )

    class Meta:
        model = Delivery
        fields = [
            'supplier_name', 'trays_received', 'purchase_price_per_tray',
            'delivery_date', 'receipt_image', 'notes'
        ]
        widgets = {
            'supplier_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Supplier or Farm name (e.g., Wangige Farm)'
            }),
            'trays_received': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'placeholder': 'Number of trays received'
            }),
            'purchase_price_per_tray': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': 'Purchase price per tray (e.g., 400.00)'
            }),
            'receipt_image': forms.ClearableFileInput(attrs={
                'class': 'form-control-file'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Delivery notes / Invoice number'
            }),
        }

    def clean_trays_received(self):
        trays = self.cleaned_data.get('trays_received')
        if not trays or trays <= 0:
            raise forms.ValidationError("Must receive at least 1 full tray.")
        return trays

    def clean_purchase_price_per_tray(self):
        price = self.cleaned_data.get('purchase_price_per_tray')
        if price is None or price <= Decimal('0.00'):
            raise forms.ValidationError("Purchase price per tray must be greater than zero.")
        return price


class ExpenseForm(forms.ModelForm):
    expense_date = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
        initial=timezone.now
    )

    class Meta:
        model = Expense
        fields = ['category', 'description', 'amount', 'expense_date', 'notes']
        widgets = {
            'category': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Brief description (e.g. Fuel for delivery motorbike)'
            }),
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': 'Amount in KSh'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Additional notes / Receipt details'
            }),
        }

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount is None or amount <= Decimal('0.00'):
            raise forms.ValidationError("Expense amount must be greater than zero.")
        return amount


class InventoryAdjustmentForm(forms.ModelForm):
    adjustment_date = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
        initial=timezone.now
    )

    class Meta:
        model = InventoryAdjustment
        fields = ['adjustment_type', 'quantity', 'reason', 'adjustment_date', 'notes']
        widgets = {
            'adjustment_type': forms.Select(attrs={'class': 'form-control'}),
            'quantity': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'placeholder': 'Number of loose eggs'
            }),
            'reason': forms.Select(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Incident explanation or count log notes'
            }),
        }

    def clean_quantity(self):
        qty = self.cleaned_data.get('quantity')
        if not qty or qty <= 0:
            raise forms.ValidationError("Adjustment quantity must be at least 1 egg.")
        return qty


class RestockingCalculatorForm(forms.Form):
    target_trays = forms.IntegerField(
        min_value=1,
        initial=30,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Target stock in full trays (e.g. 30)'
        }),
        help_text="Target inventory in full trays"
    )
    purchase_cost_per_tray = forms.DecimalField(
        min_value=Decimal('0.01'),
        decimal_places=2,
        initial=Decimal('400.00'),
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'placeholder': 'Purchase price per tray (e.g. 400.00)'
        }),
        help_text="Expected purchase price per 30-egg tray"
    )


class BusinessSettingsForm(forms.ModelForm):
    class Meta:
        model = BusinessSettings
        fields = [
            'business_name', 'owner_name', 'contact_phone', 'contact_email',
            'single_egg_price', 'two_egg_price', 'three_egg_price',
            'half_tray_price', 'full_tray_price',
            'default_purchase_cost_per_tray', 'low_stock_threshold', 'logo'
        ]
        widgets = {
            'business_name': forms.TextInput(attrs={'class': 'form-control'}),
            'owner_name': forms.TextInput(attrs={'class': 'form-control'}),
            'contact_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'contact_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'single_egg_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'two_egg_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'three_egg_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'half_tray_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'full_tray_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'default_purchase_cost_per_tray': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'low_stock_threshold': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'logo': forms.ClearableFileInput(attrs={'class': 'form-control-file'}),
        }


class OpeningStockForm(forms.Form):
    initial_trays = forms.IntegerField(
        min_value=1,
        initial=30,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Initial Trays (e.g. 30 = 900 eggs)'
        }),
        help_text="Number of full trays (30 eggs each)"
    )
    cost_per_tray = forms.DecimalField(
        min_value=Decimal('0.01'),
        decimal_places=2,
        initial=Decimal('400.00'),
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'placeholder': 'Cost per Tray (e.g. 400.00)'
        }),
        help_text="Purchase cost per tray in KES"
    )
