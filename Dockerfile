FROM python:3.11-slim

# Install system packages needed to build wheels and runtime deps
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
    build-essential \
    cargo \
    gcc \
    libpq-dev \
    curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy only requirements first to leverage Docker cache
COPY requirements.txt .

# Upgrade packaging tools and install Python deps
RUN python -m pip install --upgrade pip setuptools wheel && \
    pip install -r requirements.txt

# Copy application code
COPY . .

# Expose port and default command (adjust main:app if different)
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
