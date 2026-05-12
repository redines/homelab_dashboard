#!/usr/bin/env bash
set -euo pipefail

echo "==> Configuring SSH known hosts..."
mkdir -p ~/.ssh
chmod 700 ~/.ssh
touch ~/.ssh/known_hosts
if ! ssh-keygen -F "[192.168.50.210]:2222" >/dev/null; then
  ssh-keyscan -p 2222 192.168.50.210 >> ~/.ssh/known_hosts \
    || echo "Warning: could not add 192.168.50.210:2222 to SSH known_hosts"
fi
chmod 600 ~/.ssh/known_hosts

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
