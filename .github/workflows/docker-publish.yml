# File: Dockerfile
# ---- Builder Stage ----
# Этот этап используется для установки зависимостей, включая те, что требуют компиляции.
FROM python:3.11-bookworm AS builder

# Установка системных зависимостей, необходимых для сборки
# psycopg2-binary и потенциально других пакетов.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Создание и активация виртуального окружения
ENV VIRTUAL_ENV=/opt/venv
RUN python -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Копирование файла зависимостей и их установка
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


# ---- Final Stage ----
# Этот этап создает финальный, легковесный образ для запуска приложения.
FROM python:3.11-slim-bookworm AS final

WORKDIR /app

# Установка системных зависимостей, необходимых для работы приложения в runtime.
# libpq5 требуется для psycopg2.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libpq5 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Копирование виртуального окружения с установленными пакетами из builder stage.
COPY --from=builder /opt/venv /opt/venv

# Копирование исходного кода приложения
COPY . .

# Активация виртуального окружения
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Указание точки входа
ENTRYPOINT ["/app/entrypoint.sh"]
