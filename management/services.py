import math
from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
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


class PricingService:
    """
    Computes the cheapest valid combination of configured egg bundles
    for any requested egg quantity using dynamic programming (unbounded knapsack).
    """

    @classmethod
    def get_bundles(cls, settings=None):
        if settings is None:
            settings = BusinessSettings.get_settings()

        # Available bundles: (eggs_count, price, display_name)
        return [
            (30, settings.full_tray_price, "Full Tray (30 eggs)"),
            (15, settings.half_tray_price, "Half Tray (15 eggs)"),
            (3, settings.three_egg_price, "3 Eggs Offer"),
            (2, settings.two_egg_price, "2 Eggs Offer"),
            (1, settings.single_egg_price, "Single Egg"),
        ]

    @classmethod
    def calculate_optimal_price(cls, quantity: int, settings=None):
        """
        Calculates the cheapest valid combination of configured offers
        that sum up exactly to the given egg quantity.
        Returns a dict containing total_price, breakdown_items, and breakdown_text.
        """
        if not isinstance(quantity, int) or quantity <= 0:
            raise ValidationError("Egg quantity must be a positive integer.")

        bundles = cls.get_bundles(settings)
        # dp[q] = (min_cost, bundle_index_used)
        dp = [None] * (quantity + 1)
        dp[0] = (Decimal('0.00'), -1)

        for q in range(1, quantity + 1):
            best_cost = None
            best_bundle_idx = -1
            for idx, (bundle_size, bundle_price, _) in enumerate(bundles):
                if q >= bundle_size and dp[q - bundle_size] is not None:
                    candidate_cost = dp[q - bundle_size][0] + bundle_price
                    if best_cost is None or candidate_cost < best_cost:
                        best_cost = candidate_cost
                        best_bundle_idx = idx
            dp[q] = (best_cost, best_bundle_idx)

        total_price = dp[quantity][0]

        # Backtrack to reconstruct the combination
        bundle_counts = [0] * len(bundles)
        curr = quantity
        while curr > 0:
            bundle_idx = dp[curr][1]
            if bundle_idx == -1:
                break
            bundle_counts[bundle_idx] += 1
            curr -= bundles[bundle_idx][0]

        breakdown_items = []
        text_parts = []
        for idx, count in enumerate(bundle_counts):
            if count > 0:
                bundle_size, unit_price, bundle_name = bundles[idx]
                subtotal = Decimal(count) * unit_price
                breakdown_items.append({
                    'bundle_name': bundle_name,
                    'bundle_units': count,
                    'eggs_per_bundle': bundle_size,
                    'total_eggs': count * bundle_size,
                    'unit_price': unit_price,
                    'subtotal': subtotal,
                })
                text_parts.append(f"{count} x {bundle_name} @ KSh {unit_price:,.2f} = KSh {subtotal:,.2f}")

        breakdown_text = "; ".join(text_parts)

        return {
            'quantity': quantity,
            'total_price': total_price,
            'breakdown_items': breakdown_items,
            'breakdown_text': breakdown_text,
        }


class InventoryService:
    """
    Handles atomic inventory updates, auditable stock movements,
    and Weighted Average Cost (WAC) calculations.
    """

    @classmethod
    @transaction.atomic
    def initialize_opening_stock(cls, initial_trays: int = 30, cost_per_tray: Decimal = Decimal('400.00')):
        """
        Initializes opening stock once (default 30 trays = 900 eggs at KES 400 per tray).
        Safe against server restarts.
        """
        settings = BusinessSettings.get_settings()
        if settings.opening_stock_initialized:
            raise ValidationError("Opening stock has already been initialized.")

        inventory = Inventory.objects.select_for_update().get_or_create(id=1)[0]
        total_eggs = initial_trays * 30
        wac_per_egg = (cost_per_tray / Decimal('30')).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)

        inventory.total_eggs = total_eggs
        inventory.weighted_average_cost_per_egg = wac_per_egg
        inventory.save()

        settings.opening_stock_initialized = True
        settings.save()

        StockMovement.objects.create(
            movement_type='opening_stock',
            quantity_change=total_eggs,
            balance_after=total_eggs,
            unit_cost=wac_per_egg,
            total_value=Decimal(total_eggs) * wac_per_egg,
            reference_id="INIT-STOCK",
            description=f"Opening stock initialized: {initial_trays} trays ({total_eggs} eggs) @ KSh {cost_per_tray}/tray",
            created_at=timezone.now(),
        )

        return inventory

    @classmethod
    @transaction.atomic
    def record_sale(cls, quantity: int, customer_name: str = "", sale_date=None, notes: str = ""):
        """
        Validates available stock, applies optimal pricing breakdown,
        deducts stock atomically, and records the sale with stock movement audit.
        """
        if quantity <= 0:
            raise ValidationError("Quantity of eggs must be greater than zero.")

        if sale_date is None:
            sale_date = timezone.now()

        inventory = Inventory.objects.select_for_update().get_or_create(id=1)[0]

        if inventory.total_eggs < quantity:
            raise ValidationError(
                f"Insufficient stock! Available: {inventory.total_eggs} eggs "
                f"({inventory.full_trays} full trays, {inventory.loose_eggs} loose). "
                f"Cannot sell {quantity} eggs."
            )

        pricing = PricingService.calculate_optimal_price(quantity)
        total_amount = pricing['total_price']
        breakdown_text = pricing['breakdown_text']
        breakdown_items = pricing['breakdown_items']

        # COGS based on current WAC snapshot
        unit_cost = inventory.weighted_average_cost_per_egg
        cogs = (Decimal(quantity) * unit_cost).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        gross_profit = total_amount - cogs

        # Deduct inventory
        inventory.total_eggs -= quantity
        inventory.save()

        # Create Sale
        sale = Sale.objects.create(
            customer_name=customer_name.strip() if customer_name.strip() else "Walk-in Customer",
            quantity=quantity,
            unit_cost_at_sale=unit_cost,
            total_cost_of_goods_sold=cogs,
            total_amount=total_amount,
            gross_profit=gross_profit,
            pricing_breakdown=breakdown_text,
            sale_date=sale_date,
            notes=notes.strip(),
        )

        # Create itemized SaleItems
        for item in breakdown_items:
            SaleItem.objects.create(
                sale=sale,
                bundle_name=item['bundle_name'],
                bundle_units=item['bundle_units'],
                eggs_per_bundle=item['eggs_per_bundle'],
                total_eggs=item['total_eggs'],
                unit_price=item['unit_price'],
                subtotal=item['subtotal'],
            )

        # Record auditable StockMovement
        StockMovement.objects.create(
            movement_type='sale',
            quantity_change=-quantity,
            balance_after=inventory.total_eggs,
            unit_cost=unit_cost,
            total_value=cogs,
            reference_id=f"Sale #{sale.id}",
            description=f"Sale #{sale.id} to {sale.customer_name} ({quantity} eggs for KSh {total_amount:,.2f})",
            created_at=sale_date,
        )

        return sale

    @classmethod
    @transaction.atomic
    def cancel_sale(cls, sale_id: int, reason: str = ""):
        """
        Safely cancels a sale and restores the eggs to inventory.
        Never deletes historical records.
        """
        sale = Sale.objects.select_for_update().get(id=sale_id)
        if sale.is_cancelled:
            raise ValidationError("This sale has already been cancelled.")

        inventory = Inventory.objects.select_for_update().get_or_create(id=1)[0]
        inventory.total_eggs += sale.quantity
        inventory.save()

        sale.is_cancelled = True
        if reason:
            sale.notes = f"{sale.notes} [Cancelled: {reason}]".strip()
        sale.save()

        StockMovement.objects.create(
            movement_type='sale_cancellation',
            quantity_change=sale.quantity,
            balance_after=inventory.total_eggs,
            unit_cost=sale.unit_cost_at_sale,
            total_value=sale.total_cost_of_goods_sold,
            reference_id=f"Cancel #{sale.id}",
            description=f"Cancelled Sale #{sale.id} ({sale.quantity} eggs restored). Reason: {reason or 'Not specified'}",
            created_at=timezone.now(),
        )

        return sale

    @classmethod
    @transaction.atomic
    def record_delivery(cls, supplier_name: str, trays_received: int, purchase_price_per_tray: Decimal,
                        delivery_date=None, notes: str = "", receipt_image=None):
        """
        Increases inventory stock by trays * 30 and recalculates the Weighted Average Cost (WAC).
        """
        if trays_received <= 0:
            raise ValidationError("Trays received must be at least 1.")
        if purchase_price_per_tray <= Decimal('0.00'):
            raise ValidationError("Purchase price per tray must be greater than zero.")

        if delivery_date is None:
            delivery_date = timezone.now()

        inventory = Inventory.objects.select_for_update().get_or_create(id=1)[0]
        eggs_added = trays_received * 30
        delivery_cost = Decimal(trays_received) * purchase_price_per_tray
        cost_per_egg = (delivery_cost / Decimal(eggs_added)).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)

        # Recalculate Weighted Average Cost (WAC)
        if inventory.total_eggs == 0:
            new_wac = cost_per_egg
        else:
            old_stock_value = Decimal(inventory.total_eggs) * inventory.weighted_average_cost_per_egg
            total_value = old_stock_value + delivery_cost
            new_total_eggs = inventory.total_eggs + eggs_added
            new_wac = (total_value / Decimal(new_total_eggs)).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)

        inventory.total_eggs += eggs_added
        inventory.weighted_average_cost_per_egg = new_wac
        inventory.save()

        delivery = Delivery.objects.create(
            supplier_name=supplier_name.strip(),
            trays_received=trays_received,
            eggs_received=eggs_added,
            purchase_price_per_tray=purchase_price_per_tray,
            cost_per_egg=cost_per_egg,
            total_cost=delivery_cost,
            delivery_date=delivery_date,
            receipt_image=receipt_image,
            notes=notes.strip(),
        )

        StockMovement.objects.create(
            movement_type='delivery',
            quantity_change=eggs_added,
            balance_after=inventory.total_eggs,
            unit_cost=cost_per_egg,
            total_value=delivery_cost,
            reference_id=f"Delivery #{delivery.id}",
            description=f"Restock Delivery #{delivery.id} from {delivery.supplier_name}: {trays_received} trays ({eggs_added} eggs @ KSh {purchase_price_per_tray}/tray)",
            created_at=delivery_date,
        )

        return delivery

    @classmethod
    @transaction.atomic
    def record_adjustment(cls, quantity: int, reason: str, adjustment_type: str = 'loss',
                          adjustment_date=None, notes: str = ""):
        """
        Records egg losses (breakage, spoilage) or physical stock count adjustments.
        Deducts from stock and accounts for cost.
        """
        if quantity <= 0:
            raise ValidationError("Quantity must be a positive integer.")

        if adjustment_date is None:
            adjustment_date = timezone.now()

        inventory = Inventory.objects.select_for_update().get_or_create(id=1)[0]
        unit_cost = inventory.weighted_average_cost_per_egg

        if adjustment_type == 'loss':
            if inventory.total_eggs < quantity:
                raise ValidationError(
                    f"Cannot report loss of {quantity} eggs. Current available stock is only {inventory.total_eggs} eggs."
                )
            inventory.total_eggs -= quantity
            quantity_change = -quantity
            movement_type = 'loss' if reason in ('broken', 'spoiled') else 'adjustment_loss'
        else: # gain
            inventory.total_eggs += quantity
            quantity_change = quantity
            movement_type = 'adjustment_gain'

        inventory.save()
        total_loss_cost = (Decimal(quantity) * unit_cost).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        adj = InventoryAdjustment.objects.create(
            adjustment_type=adjustment_type,
            quantity=quantity,
            unit_cost=unit_cost,
            total_loss_cost=total_loss_cost if adjustment_type == 'loss' else Decimal('0.00'),
            reason=reason,
            adjustment_date=adjustment_date,
            notes=notes.strip(),
        )

        StockMovement.objects.create(
            movement_type=movement_type,
            quantity_change=quantity_change,
            balance_after=inventory.total_eggs,
            unit_cost=unit_cost,
            total_value=total_loss_cost,
            reference_id=f"Adjustment #{adj.id}",
            description=f"Inventory {adj.get_adjustment_type_display()} #{adj.id} ({adj.get_reason_display()}): {abs(quantity_change)} eggs",
            created_at=adjustment_date,
        )

        return adj


class RestockingCalculator:
    """
    Computes egg restocking requirements based on current inventory and full tray purchases.
    """

    @classmethod
    def calculate(cls, current_stock_eggs: int, target_trays: int, purchase_cost_per_tray: Decimal):
        if target_trays < 0:
            raise ValidationError("Target stock in full trays must be zero or positive.")
        if purchase_cost_per_tray < Decimal('0.00'):
            raise ValidationError("Purchase cost per tray cannot be negative.")

        target_eggs = target_trays * 30
        eggs_needed = max(0, target_eggs - current_stock_eggs)
        # Round up to full trays
        trays_to_purchase = math.ceil(eggs_needed / 30) if eggs_needed > 0 else 0
        eggs_to_receive = trays_to_purchase * 30
        projected_stock_eggs = current_stock_eggs + eggs_to_receive
        projected_full_trays = projected_stock_eggs // 30
        projected_loose_eggs = projected_stock_eggs % 30
        expected_cost = Decimal(trays_to_purchase) * purchase_cost_per_tray

        return {
            'current_stock_eggs': current_stock_eggs,
            'target_trays': target_trays,
            'target_eggs': target_eggs,
            'eggs_needed': eggs_needed,
            'trays_to_purchase': trays_to_purchase,
            'eggs_to_receive': eggs_to_receive,
            'projected_stock_eggs': projected_stock_eggs,
            'projected_full_trays': projected_full_trays,
            'projected_loose_eggs': projected_loose_eggs,
            'purchase_cost_per_tray': purchase_cost_per_tray,
            'expected_cost': expected_cost,
            'note': (
                "Purchases are strictly made in full trays (30 eggs each). "
                "Because of this, the projected stock after delivery may slightly exceed the exact target if there were loose eggs."
            )
        }


class AccountingService:
    """
    Provides transparent accounting and profit calculations across any date range.
    """

    @classmethod
    def get_financial_summary(cls, start_date=None, end_date=None):
        """
        Gross profit: Sales revenue minus Cost of Goods Sold.
        Net profit: Gross profit minus Operating Expenses and Stock Loss costs.
        """
        sales_qs = Sale.objects.filter(is_cancelled=False)
        expenses_qs = Expense.objects.all()
        losses_qs = InventoryAdjustment.objects.filter(adjustment_type='loss')
        deliveries_qs = Delivery.objects.all()

        if start_date:
            sales_qs = sales_qs.filter(sale_date__gte=start_date)
            expenses_qs = expenses_qs.filter(expense_date__gte=start_date)
            losses_qs = losses_qs.filter(adjustment_date__gte=start_date)
            deliveries_qs = deliveries_qs.filter(delivery_date__gte=start_date)

        if end_date:
            sales_qs = sales_qs.filter(sale_date__lte=end_date)
            expenses_qs = expenses_qs.filter(expense_date__lte=end_date)
            losses_qs = losses_qs.filter(adjustment_date__lte=end_date)
            deliveries_qs = deliveries_qs.filter(delivery_date__lte=end_date)

        total_sales_count = sales_qs.count()
        total_eggs_sold = sum(s.quantity for s in sales_qs) or 0
        total_revenue = sum(s.total_amount for s in sales_qs) or Decimal('0.00')
        total_cogs = sum(s.total_cost_of_goods_sold for s in sales_qs) or Decimal('0.00')
        gross_profit = total_revenue - total_cogs

        total_expenses = sum(e.amount for e in expenses_qs) or Decimal('0.00')
        total_losses_cost = sum(l.total_loss_cost for l in losses_qs) or Decimal('0.00')
        total_eggs_lost = sum(l.quantity for l in losses_qs) or 0

        # Deliveries represent inventory asset purchases, not operating expenses
        total_delivery_purchases = sum(d.total_cost for d in deliveries_qs) or Decimal('0.00')
        total_trays_received = sum(d.trays_received for d in deliveries_qs) or 0

        # Net profit = Gross profit - Operating expenses - Stock loss costs
        net_profit = gross_profit - total_expenses - total_losses_cost

        # Live inventory snapshot
        inventory = Inventory.get_inventory()

        return {
            'sales_count': total_sales_count,
            'total_eggs_sold': total_eggs_sold,
            'total_revenue': total_revenue,
            'total_cogs': total_cogs,
            'gross_profit': gross_profit,
            'total_expenses': total_expenses,
            'total_losses_cost': total_losses_cost,
            'total_eggs_lost': total_eggs_lost,
            'total_delivery_purchases': total_delivery_purchases,
            'total_trays_received': total_trays_received,
            'net_profit': net_profit,
            'current_stock_eggs': inventory.total_eggs,
            'current_full_trays': inventory.full_trays,
            'current_loose_eggs': inventory.loose_eggs,
            'stock_value': inventory.stock_value,
            'wac_per_egg': inventory.weighted_average_cost_per_egg,
        }
