#!/bin/sh

# Exit immediately if a command exits with a non-zero status
set -e

# Применяем миграции базы данных
echo "Applying database migrations..."
python manage.py migrate

# Если включен TEST_MODE, генерируем начальные данные
if [ "$TEST_MODE" = "1" ]; then
  echo "TEST_MODE is enabled. Seeding initial test data..."
  python manage.py seed_test_data
else
  echo "TEST_MODE is disabled. Skipping data seeding."
fi

# Собираем статические файлы
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Запускаем сервер
echo "Starting daphne server..."
daphne -b 0.0.0.0 -p 8000 core.asgi:application
