"""
WSGI config for Cheremo Egg Depot project.
"""

import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'depot.settings')

application = get_wsgi_application()

# Serverless compatibility for Vercel
app = application

# Auto-migrate on Vercel cold-start if running serverless
if os.getenv('VERCEL') == '1':
    try:
        from django.core.management import call_command
        call_command('migrate', interactive=False)
        call_command('setup_depot', username='japhet', email='japhetcheremo@gmail.com', password=os.getenv('ADMIN_PASSWORD', 'CheremoDepot2026!'))
    except Exception as e:
        print(f"Serverless init notice: {e}")
