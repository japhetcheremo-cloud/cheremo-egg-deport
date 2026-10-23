
#!/usr/bin/env bash
set -e

echo "Building Cheremo Egg Depot for Vercel..."

# Create an isolated Python environment
python3 -m venv .venv

# Activate the environment
source .venv/bin/activate

# Install dependencies inside the isolated environment
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# Collect Django static files
python manage.py collectstatic --noinput --clear

echo "Cheremo Egg Depot build completed successfully!"
