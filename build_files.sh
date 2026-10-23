#!/usr/bin/env bash
echo "Building Cheremo Egg Depot for Vercel..."
python3 -m pip install -r requirements.txt
python3 manage.py collectstatic --noinput --clear
echo "Build completed successfully!"
