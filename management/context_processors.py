from django.utils import timezone
from .models import BusinessSettings, Inventory


def business_context(request):
    """
    Context processor to make depot branding, currency, and inventory alert
    accessible in all templates.
    """
    try:
        settings = BusinessSettings.get_settings()
        inventory = Inventory.get_inventory()
        is_low_stock = inventory.is_low_stock(settings.low_stock_threshold)
    except Exception:
        settings = None
        inventory = None
        is_low_stock = False

    return {
        'business': settings,
        'inventory_status': inventory,
        'is_low_stock': is_low_stock,
        'current_year': timezone.now().year,
    }
