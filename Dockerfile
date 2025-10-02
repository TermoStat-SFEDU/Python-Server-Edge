# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set work directory
WORKDIR /app

# Install system dependencies (git is required for pip git installs)
RUN apt-get update && \
    apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY requirements.txt /app/
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Copy project
COPY . /app/

# --- FIX: Ensure entrypoint.sh has correct line endings and is executable ---
# 1. Convert CRLF (Windows) line endings to LF (Unix)
RUN sed -i 's/\r$//' /app/entrypoint.sh
# 2. Make entrypoint script executable
RUN chmod +x /app/entrypoint.sh

# Expose port 8000