from decimal import Decimal
import os
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.conf import settings

from .models import (
    BusinessSettings,
    Inventory,
    Sale,
    Delivery,
    Expense,
    InventoryAdjustment,
    StockMovement,
)
from .services import (
    PricingService,
    InventoryService,
    RestockingCalculator,
    AccountingService,
)


class PricingAlgorithmTests(TestCase):
    """
    Tests for exact optimal pricing across all sample quantities specified:
    1 egg = KSh 20
    2 eggs = KSh 35
    3 eggs = KSh 55
    4 eggs = KSh 70
    5 eggs = KSh 90
    10 eggs = KSh 175
    15 eggs = KSh 240
    16 eggs = KSh 260
    30 eggs = KSh 480
    31 eggs = KSh 500
    """

    def setUp(self):
        self.settings = BusinessSettings.get_settings()
        self.settings.single_egg_price = Decimal('20.00')
        self.settings.two_egg_price = Decimal('35.00')
        self.settings.three_egg_price = Decimal('55.00')
        self.settings.half_tray_price = Decimal('240.00')
        self.settings.full_tray_price = Decimal('480.00')
        self.settings.save()

    def test_sample_quantities_cheapest_combination(self):
        expected_prices = {
            1: Decimal('20.00'),
            2: Decimal('35.00'),
            3: Decimal('55.00'),
            4: Decimal('70.00'),
            5: Decimal('90.00'),
            10: Decimal('175.00'),
            15: Decimal('240.00'),
            16: Decimal('260.00'),
            30: Decimal('480.00'),
            31: Decimal('500.00'),
        }

        for quantity, expected_price in expected_prices.items():
            result = PricingService.calculate_optimal_price(quantity, self.settings)
            self.assertEqual(
                result['total_price'],
                expected_price,
                f"Mismatch for {quantity} eggs! Expected {expected_price}, got {result['total_price']}. Breakdown: {result['breakdown_text']}"
            )
            self.assertTrue(len(result['breakdown_items']) > 0)
            self.assertTrue(len(result['breakdown_text']) > 0)

    def test_invalid_quantities_rejected(self):
        with self.assertRaises(ValidationError):
            PricingService.calculate_optimal_price(0, self.settings)

        with self.assertRaises(ValidationError):
            PricingService.calculate_optimal_price(-5, self.settings)


class InventoryServiceTests(TestCase):
    """
    Tests for inventory initialization, sales, deliveries, stock safety, and prevention of overselling.
    """

    def setUp(self):
        self.settings = BusinessSettings.get_settings()
        self.settings.opening_stock_initialized = False
        self.settings.save()
        Inventory.objects.filter(id=1).delete()
        StockMovement.objects.all().delete()

    def test_opening_stock_initialization(self):
        inv = InventoryService.initialize_opening_stock(initial_trays=30, cost_per_tray=Decimal('400.00'))
        self.assertEqual(inv.total_eggs, 900)
        self.assertEqual(inv.full_trays, 30)
        self.assertEqual(inv.loose_eggs, 0)
        self.assertAlmostEqual(float(inv.weighted_average_cost_per_egg), 400.0 / 30.0, places=2)

        # Ensure opening stock cannot be duplicated
        with self.assertRaises(ValidationError):
            InventoryService.initialize_opening_stock(initial_trays=30)

        # Movement audit created
        self.assertTrue(StockMovement.objects.filter(movement_type='opening_stock').exists())

    def test_sale_reduces_stock_correctly(self):
        InventoryService.initialize_opening_stock(initial_trays=30, cost_per_tray=Decimal('400.00'))
        sale = InventoryService.record_sale(quantity=16, customer_name="Alice")
        
        inv = Inventory.get_inventory()
        self.assertEqual(inv.total_eggs, 900 - 16)
        self.assertEqual(sale.total_amount, Decimal('260.00'))
        self.assertFalse(sale.is_cancelled)

        # StockMovement audit check
        movement = StockMovement.objects.filter(movement_type='sale').first()
        self.assertIsNotNone(movement)
        self.assertEqual(movement.quantity_change, -16)
        self.assertEqual(movement.balance_after, 884)

    def test_delivery_increases_stock_and_updates_wac(self):
        inv = Inventory.get_inventory()
        inv.total_eggs = 0
        inv.weighted_average_cost_per_egg = Decimal('0.0000')
        inv.save()

        # Delivery 1: 10 trays at KSh 400 = 300 eggs @ 13.3333
        d1 = InventoryService.record_delivery(
            supplier_name="Farm A",
            trays_received=10,
            purchase_price_per_tray=Decimal('400.00')
        )
        inv.refresh_from_db()
        self.assertEqual(inv.total_eggs, 300)
        self.assertEqual(d1.total_cost, Decimal('4000.00'))

        # Delivery 2: 10 trays at KSh 450 = 300 eggs @ 15.00
        # Total cost: 4000 + 4500 = 8500 for 600 eggs => WAC = 8500 / 600 = 14.1667
        InventoryService.record_delivery(
            supplier_name="Farm B",
            trays_received=10,
            purchase_price_per_tray=Decimal('450.00')
        )
        inv.refresh_from_db()
        self.assertEqual(inv.total_eggs, 600)
        self.assertAlmostEqual(float(inv.weighted_average_cost_per_egg), 8500.0 / 600.0, places=2)

    def test_insufficient_stock_rejects_sale(self):
        inv = Inventory.get_inventory()
        inv.total_eggs = 20
        inv.save()

        with self.assertRaises(ValidationError):
            InventoryService.record_sale(quantity=25, customer_name="Bob")

        # Inventory remains untouched at 20
        inv.refresh_from_db()
        self.assertEqual(inv.total_eggs, 20)

    def test_safe_sale_cancellation(self):
        InventoryService.initialize_opening_stock(initial_trays=30)
        sale = InventoryService.record_sale(quantity=50, customer_name="Charles")
        
        inv = Inventory.get_inventory()
        self.assertEqual(inv.total_eggs, 850)

        InventoryService.cancel_sale(sale.id, reason="Customer cancelled")
        sale.refresh_from_db()
        inv.refresh_from_db()

        self.assertTrue(sale.is_cancelled)
        self.assertEqual(inv.total_eggs, 900)
        self.assertTrue(StockMovement.objects.filter(movement_type='sale_cancellation').exists())


class RestockingCalculatorTests(TestCase):
    def test_restocking_calculator_rounding_up(self):
        # Example from requirements:
        # If I have 20 eggs and want a total of 30 trays (900 eggs):
        # Target = 900 eggs, needed = 880, trays = ceil(880/30) = 30 trays, projected = 920 eggs.
        result = RestockingCalculator.calculate(
            current_stock_eggs=20,
            target_trays=30,
            purchase_cost_per_tray=Decimal('400.00')
        )
        self.assertEqual(result['target_eggs'], 900)
        self.assertEqual(result['eggs_needed'], 880)
        self.assertEqual(result['trays_to_purchase'], 30)
        self.assertEqual(result['projected_stock_eggs'], 920)
        self.assertEqual(result['expected_cost'], Decimal('12000.00'))


class AccountingAndProfitTests(TestCase):
    def setUp(self):
        self.settings = BusinessSettings.get_settings()
        self.settings.opening_stock_initialized = False
        self.settings.save()
        Sale.objects.all().delete()
        Expense.objects.all().delete()
        InventoryAdjustment.objects.all().delete()
        Delivery.objects.all().delete()
        InventoryService.initialize_opening_stock(initial_trays=30, cost_per_tray=Decimal('400.00'))

    def test_financial_summary_and_net_profit(self):
        # Sale 1: 30 eggs (1 full tray = KSh 480.00). Cost = 30 * 13.3333 = KSh 400.00
        InventoryService.record_sale(quantity=30, customer_name="Market Vendor")

        # Operating Expense: Transport KSh 30.00
        Expense.objects.create(category='Transport', description='Fuel', amount=Decimal('30.00'))

        # Egg Loss: 2 eggs broken. Unit cost = 13.3333 => loss cost = 26.67
        InventoryService.record_adjustment(quantity=2, reason='broken', adjustment_type='loss')

        summary = AccountingService.get_financial_summary()

        self.assertEqual(summary['total_revenue'], Decimal('480.00'))
        self.assertEqual(summary['total_cogs'], Decimal('400.00'))
        self.assertEqual(summary['gross_profit'], Decimal('80.00'))
        self.assertEqual(summary['total_expenses'], Decimal('30.00'))
        self.assertAlmostEqual(float(summary['total_losses_cost']), 26.67, places=2)
        
        # Net Profit = 80 - 30 - 26.67 = 23.33
        expected_net = Decimal('80.00') - Decimal('30.00') - summary['total_losses_cost']
        self.assertEqual(summary['net_profit'], expected_net)


class SecurityAndAccessTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_superuser(
            username='japhet_test',
            email='japhet@example.com',
            password='TestPassword123!'
        )

    def test_anonymous_users_redirected_to_login(self):
        protected_urls = [
            reverse('dashboard'),
            reverse('sales'),
            reverse('deliveries'),
            reverse('expenses'),
            reverse('inventory'),
            reverse('transactions'),
            reverse('reports'),
            reverse('settings'),
        ]
        for url in protected_urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302)
            self.assertIn('/login/', response.url)

    def test_authenticated_user_access(self):
        self.client.login(username='japhet_test', password='TestPassword123!')
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_csrf_protection_enabled(self):
        # POST without CSRF token to login view using client with enforce_csrf_checks=True
        csrf_client = Client(enforce_csrf_checks=True)
        response = csrf_client.post(reverse('login'), {'username': 'japhet_test', 'password': 'wrong'})
        # Should be rejected with 403 Forbidden due to missing CSRF token
        self.assertEqual(response.status_code, 403)


class CloudinaryConfigurationTests(TestCase):
    def test_cloudinary_settings_loaded(self):
        self.assertTrue(hasattr(settings, 'CLOUDINARY_STORAGE'))
        self.assertTrue(hasattr(settings, 'STORAGES'))
        self.assertIn('default', settings.STORAGES)
        self.assertIn('staticfiles', settings.STORAGES)
