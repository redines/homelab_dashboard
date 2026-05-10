#!/usr/bin/env bash
set -euo pipefail

echo "==> Installing Node dependencies..."
npm install

echo "==> Building Tailwind CSS..."
npm run build:css

echo "==> Running Django migrations..."
python manage.py migrate --run-syncdb

echo "==> Collecting static files..."
python manage.py collectstatic --noinput

echo ""
echo "Dev container ready!"
echo "  Start the dev server : npm run dev"
echo "  Run Python tests      : pytest"
echo "  Run JS tests          : npm test"
