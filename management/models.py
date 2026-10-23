from decimal import Decimal
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator


class BusinessSettings(models.Model):
    """
    Singleton model for Cheremo Egg Depot business parameters and pricing rules.
    """
    business_name = models.CharField(max_length=150, default="Cheremo Egg Depot")
    owner_name = models.CharField(max_length=100, default="Japhet")
    contact_phone = models.CharField(max_length=50, default="+254 700 000 000", blank=True)
    contact_email = models.EmailField(default="japhetcheremo@gmail.com", blank=True)
    currency = models.CharField(max_length=10, default="KES")
    timezone_name = models.CharField(max_length=50, default="Africa/Nairobi")

    # Configurable Retail Egg Prices
    single_egg_price = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('20.00'),
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Price for 1 loose egg (Default: KES 20)"
    )
    two_egg_price = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('35.00'),
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Offer for 2 eggs (Default: KES 35)"
    )
    three_egg_price = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('55.00'),
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Offer for 3 eggs (Default: KES 55)"
    )
    half_tray_price = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('240.00'),
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Price for half tray / 15 eggs (Default: KES 240)"
    )
    full_tray_price = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('480.00'),
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Price for full tray / 30 eggs (Default: KES 480)"
    )

    # Restocking & Inventory Defaults
    default_purchase_cost_per_tray = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('400.00'),
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Default supplier purchase cost per 30-egg tray (Default: KES 400)"
    )
    low_stock_threshold = models.PositiveIntegerField(
        default=300,
        help_text="Warning threshold in eggs (e.g., 300 eggs = 10 full trays)"
    )
    
    # Branding & Receipt
    logo = models.ImageField(upload_to='branding/', blank=True, null=True)
    opening_stock_initialized = models.BooleanField(
        default=False,
        help_text="Tracks whether the one-time opening stock (30 trays = 900 eggs) was initialized"
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Business Settings"
        verbose_name_plural = "Business Settings"

    def __str__(self):
        return f"{self.business_name} Settings (Owner: {self.owner_name})"

    @classmethod
    def get_settings(cls):
        obj, _ = cls.objects.get_or_create(id=1)
        return obj


class Inventory(models.Model):
    """
    Live aggregated egg stock and Weighted Average Cost (WAC) per egg.
    """
    total_eggs = models.PositiveIntegerField(default=0)
    weighted_average_cost_per_egg = models.DecimalField(
        max_digits=10, decimal_places=4, default=Decimal('13.3333'),
        validators=[MinValueValidator(Decimal('0.0000'))]
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Inventory Status"
        verbose_name_plural = "Inventory Status"

    def __str__(self):
        return f"Current Stock: {self.total_eggs} eggs ({self.full_trays} trays, {self.loose_eggs} loose)"

    @classmethod
    def get_inventory(cls):
        obj, _ = cls.objects.get_or_create(id=1)
        return obj

    @property
    def full_trays(self):
        return self.total_eggs // 30

    @property
    def loose_eggs(self):
        return self.total_eggs % 30

    @property
    def stock_value(self):
        return Decimal(self.total_eggs) * self.weighted_average_cost_per_egg

    def is_low_stock(self, threshold=None):
        if threshold is None:
            threshold = BusinessSettings.get_settings().low_stock_threshold
        return self.total_eggs <= threshold


class Delivery(models.Model):
    """
    Supplier egg restock delivery (purchased in full trays).
    """
    supplier_name = models.CharField(max_length=150, help_text="Name of supplier / poultry farm")
    trays_received = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    eggs_received = models.PositiveIntegerField()
    purchase_price_per_tray = models.DecimalField(
        max_digits=10, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    cost_per_egg = models.DecimalField(max_digits=10, decimal_places=4)
    total_cost = models.DecimalField(max_digits=12, decimal_places=2)
    delivery_date = models.DateTimeField(default=timezone.now, db_index=True)
    receipt_image = models.ImageField(upload_to='deliveries/', blank=True, null=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-delivery_date', '-id']
        verbose_name_plural = "Deliveries"

    def __str__(self):
        return f"Delivery #{self.id} from {self.supplier_name} - {self.trays_received} trays ({self.eggs_received} eggs)"

    def save(self, *args, **kwargs):
        self.eggs_received = self.trays_received * 30
        self.total_cost = Decimal(self.trays_received) * self.purchase_price_per_tray
        if self.eggs_received > 0:
            self.cost_per_egg = self.total_cost / Decimal(self.eggs_received)
        else:
            self.cost_per_egg = Decimal('0.0000')
        super().save(*args, **kwargs)


class Sale(models.Model):
    """
    Customer egg sales record with frozen pricing breakdown and COGS snapshot.
    """
    customer_name = models.CharField(max_length=150, blank=True, default="Walk-in Customer")
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_cost_at_sale = models.DecimalField(
        max_digits=10, decimal_places=4, default=Decimal('0.0000'),
        help_text="Weighted average cost per egg at the time of sale"
    )
    total_cost_of_goods_sold = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        help_text="Cost of eggs sold: quantity * unit_cost_at_sale"
    )
    total_amount = models.DecimalField(
        max_digits=12, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Total revenue charged for the eggs"
    )
    gross_profit = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        help_text="total_amount - total_cost_of_goods_sold"
    )
    pricing_breakdown = models.TextField(
        help_text="Detailed text explanation of pricing bundles and offer combinations applied"
    )
    sale_date = models.DateTimeField(default=timezone.now, db_index=True)
    notes = models.TextField(blank=True)
    is_cancelled = models.BooleanField(
        default=False,
        help_text="Flagged if sale is cancelled or returned to avoid double counting"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-sale_date', '-id']

    def __str__(self):
        status = " (CANCELLED)" if self.is_cancelled else ""
        return f"Sale #{self.id} - {self.quantity} eggs to {self.customer_name} (KES {self.total_amount}){status}"


class SaleItem(models.Model):
    """
    Itemized bundles applied to fulfill the total quantity sold.
    """
    sale = models.ForeignKey(Sale, related_name='items', on_delete=models.CASCADE)
    bundle_name = models.CharField(max_length=100) # e.g. "Full Tray (30 eggs)", "2 Eggs Offer", "Single Egg"
    bundle_units = models.PositiveIntegerField() # e.g. 2 bundles
    eggs_per_bundle = models.PositiveIntegerField() # e.g. 30 eggs
    total_eggs = models.PositiveIntegerField() # bundle_units * eggs_per_bundle
    unit_price = models.DecimalField(max_digits=10, decimal_places=2) # e.g. 480.00
    subtotal = models.DecimalField(max_digits=12, decimal_places=2) # bundle_units * unit_price

    def __str__(self):
        return f"{self.bundle_units}x {self.bundle_name} = KES {self.subtotal}"


class Expense(models.Model):
    """
    Operating expenses separate from inventory purchases.
    """
    CATEGORY_CHOICES = [
        ('Transport', 'Transport & Fuel'),
        ('Packaging', 'Egg Trays & Packaging'),
        ('Utilities', 'Electricity & Water'),
        ('Rent', 'Depot Rent'),
        ('Labour', 'Labour / Casual Wages'),
        ('Maintenance', 'Equipment & Repairs'),
        ('Other', 'Other Operating Expense'),
    ]

    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='Other')
    description = models.CharField(max_length=255)
    amount = models.DecimalField(
        max_digits=12, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    expense_date = models.DateTimeField(default=timezone.now, db_index=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-expense_date', '-id']

    def __str__(self):
        return f"Expense #{self.id}: {self.description} (KES {self.amount})"


class InventoryAdjustment(models.Model):
    """
    Egg losses (broken, spoiled) or physical stock count reconciliation.
    """
    ADJUSTMENT_TYPES = [
        ('loss', 'Stock Loss (Breakage / Spoilage / Shortage)'),
        ('gain', 'Stock Count Correction (Surplus)'),
    ]

    REASON_CHOICES = [
        ('broken', 'Broken Eggs'),
        ('spoiled', 'Spoiled Eggs'),
        ('count_correction_loss', 'Stock-count Correction (Shortage)'),
        ('count_correction_gain', 'Stock-count Correction (Surplus)'),
        ('other', 'Other Approved Adjustment'),
    ]

    adjustment_type = models.CharField(max_length=10, choices=ADJUSTMENT_TYPES, default='loss')
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_cost = models.DecimalField(
        max_digits=10, decimal_places=4, default=Decimal('0.0000'),
        help_text="Unit cost per egg at time of adjustment"
    )
    total_loss_cost = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        help_text="Financial loss impact: quantity * unit_cost"
    )
    reason = models.CharField(max_length=50, choices=REASON_CHOICES)
    adjustment_date = models.DateTimeField(default=timezone.now, db_index=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-adjustment_date', '-id']

    def __str__(self):
        return f"Adjustment #{self.id} ({self.get_reason_display()}): {self.quantity} eggs"


class StockMovement(models.Model):
    """
    Immutable audit log of every change in egg stock.
    """
    MOVEMENT_TYPES = [
        ('opening_stock', 'Opening Stock'),
        ('delivery', 'Restocking Delivery'),
        ('sale', 'Customer Sale'),
        ('sale_cancellation', 'Sale Cancellation'),
        ('loss', 'Broken / Spoiled Loss'),
        ('adjustment_gain', 'Adjustment (Count Surplus)'),
        ('adjustment_loss', 'Adjustment (Count Shortage)'),
    ]

    movement_type = models.CharField(max_length=30, choices=MOVEMENT_TYPES, db_index=True)
    quantity_change = models.IntegerField(help_text="Signed egg count change (+ for addition, - for deduction)")
    balance_after = models.IntegerField(help_text="Total eggs in stock immediately after this movement")
    unit_cost = models.DecimalField(max_digits=10, decimal_places=4, default=Decimal('0.0000'))
    total_value = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    reference_id = models.CharField(max_length=100, blank=True, help_text="e.g. Sale #1, Delivery #3")
    description = models.CharField(max_length=255)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ['-created_at', '-id']

    def __str__(self):
        sign = "+" if self.quantity_change > 0 else ""
        return f"{self.created_at.strftime('%Y-%m-%d %H:%M')} | {self.get_movement_type_display()}: {sign}{self.quantity_change} eggs (Balance: {self.balance_after})"
