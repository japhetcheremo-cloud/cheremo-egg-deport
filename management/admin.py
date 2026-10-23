from django.contrib import admin
from .models import (
    BusinessSettings,
    Inventory,
    Sale,
    SaleItem,
    Delivery,
    Expense,
    InventoryAdjustment,
    StockMovement,
)


@admin.register(BusinessSettings)
class BusinessSettingsAdmin(admin.ModelAdmin):
    list_display = ('business_name', 'owner_name', 'single_egg_price', 'full_tray_price', 'updated_at')
    fieldsets = (
        ('Depot Identity', {
            'fields': ('business_name', 'owner_name', 'contact_phone', 'contact_email', 'currency', 'timezone_name', 'logo')
        }),
        ('Configurable Retail Pricing (KES)', {
            'fields': ('single_egg_price', 'two_egg_price', 'three_egg_price', 'half_tray_price', 'full_tray_price')
        }),
        ('Restocking & Inventory Defaults', {
            'fields': ('default_purchase_cost_per_tray', 'low_stock_threshold', 'opening_stock_initialized')
        }),
    )


@admin.register(Inventory)
class InventoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'total_eggs', 'full_trays', 'loose_eggs', 'weighted_average_cost_per_egg', 'updated_at')
    readonly_fields = ('total_eggs', 'weighted_average_cost_per_egg', 'updated_at')


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0
    readonly_fields = ('bundle_name', 'bundle_units', 'eggs_per_bundle', 'total_eggs', 'unit_price', 'subtotal')
    can_delete = False


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ('id', 'sale_date', 'customer_name', 'quantity', 'total_amount', 'gross_profit', 'is_cancelled')
    list_filter = ('is_cancelled', 'sale_date')
    search_fields = ('customer_name', 'notes', 'pricing_breakdown')
    inlines = [SaleItemInline]
    readonly_fields = ('quantity', 'unit_cost_at_sale', 'total_cost_of_goods_sold', 'total_amount', 'gross_profit', 'pricing_breakdown', 'created_at')


@admin.register(Delivery)
class DeliveryAdmin(admin.ModelAdmin):
    list_display = ('id', 'delivery_date', 'supplier_name', 'trays_received', 'eggs_received', 'purchase_price_per_tray', 'total_cost')
    list_filter = ('delivery_date',)
    search_fields = ('supplier_name', 'notes')


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ('id', 'expense_date', 'category', 'description', 'amount')
    list_filter = ('category', 'expense_date')
    search_fields = ('description', 'notes')


@admin.register(InventoryAdjustment)
class InventoryAdjustmentAdmin(admin.ModelAdmin):
    list_display = ('id', 'adjustment_date', 'adjustment_type', 'reason', 'quantity', 'total_loss_cost')
    list_filter = ('adjustment_type', 'reason', 'adjustment_date')
    search_fields = ('notes',)


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ('id', 'created_at', 'movement_type', 'quantity_change', 'balance_after', 'unit_cost', 'reference_id', 'description')
    list_filter = ('movement_type', 'created_at')
    search_fields = ('reference_id', 'description')
    readonly_fields = ('movement_type', 'quantity_change', 'balance_after', 'unit_cost', 'total_value', 'reference_id', 'description', 'created_at')

    def has_add_permission(self, request):
        # Prevent manual additions to audit trail outside standard service methods
        return False

    def has_delete_permission(self, request, obj=None):
        return False
