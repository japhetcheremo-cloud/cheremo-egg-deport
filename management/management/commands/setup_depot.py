from decimal import Decimal
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from management.models import BusinessSettings, Inventory
from management.services import InventoryService


class Command(BaseCommand):
    help = "Initializes Cheremo Egg Depot settings, opening stock (30 trays = 900 eggs), and Japhet's admin account."

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, default='japhet', help='Superuser login username (default: japhet)')
        parser.add_argument('--email', type=str, default='japhetcheremo@gmail.com', help='Superuser email')
        parser.add_argument('--password', type=str, default=None, help='Superuser password (if omitted, will prompt or keep existing)')
        parser.add_argument('--init-stock', action='store_true', default=True, help='Initialize opening stock of 30 trays (900 eggs)')

    def handle(self, *args, **options):
        username = options['username']
        email = options['email']
        password = options['password']
        init_stock = options['init_stock']

        self.stdout.write(self.style.NOTICE("Initializing Cheremo Egg Depot system settings..."))
        settings = BusinessSettings.get_settings()
        self.stdout.write(self.style.SUCCESS(f"Business settings verified: {settings.business_name}"))

        # Initialize Opening Stock if not already initialized
        if init_stock and not settings.opening_stock_initialized:
            self.stdout.write(self.style.NOTICE("Setting up opening stock (30 trays = 900 eggs @ KSh 400/tray)..."))
            InventoryService.initialize_opening_stock(initial_trays=30, cost_per_tray=Decimal('400.00'))
            self.stdout.write(self.style.SUCCESS("Opening stock successfully established! 30 trays (900 eggs) available."))
        else:
            inventory = Inventory.get_inventory()
            self.stdout.write(self.style.WARNING(
                f"Opening stock already initialized or skipped. Current stock: {inventory.total_eggs} eggs ({inventory.full_trays} trays, {inventory.loose_eggs} loose)."
            ))

        # Setup Superuser
        if not User.objects.filter(username=username).exists():
            if not password:
                password = 'ChangeMe123!'
                self.stdout.write(self.style.WARNING(f"No password specified for '{username}'. Set to temporary password: '{password}'"))
            user = User.objects.create_superuser(username=username, email=email, password=password)
            self.stdout.write(self.style.SUCCESS(f"Superuser '{username}' created successfully!"))
        else:
            user = User.objects.get(username=username)
            if password:
                user.set_password(password)
                user.save()
                self.stdout.write(self.style.SUCCESS(f"Password updated for existing superuser '{username}'."))
            else:
                self.stdout.write(self.style.NOTICE(f"User '{username}' already exists."))

        self.stdout.write(self.style.SUCCESS("Cheremo Egg Depot setup finished successfully!"))
