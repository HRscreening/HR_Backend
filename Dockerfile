FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install --no-cache-dir uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install Python dependencies
RUN uv pip install --system --no-cache .

# Copy app
COPY . .

EXPOSE 8000