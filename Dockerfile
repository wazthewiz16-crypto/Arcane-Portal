# Use Python 3.9 slim image
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install system dependencies for Playwright (all at once)
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libwayland-client0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xdg-utils \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxext6 \
    libxrender1 \
    libxtst6 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Set Playwright browser path BEFORE installing
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Install Playwright browsers to the specified path
RUN playwright install chromium

# Verify the browser was installed
RUN ls -la /ms-playwright/chromium-*/chrome-linux/chrome || echo "Browser not found at expected location"

# Copy application code
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV HEADLESS_BROWSER=true

# Run the application (overridden by Railway Custom Start Command)
# CMD ["python", "run_signals.py"]
