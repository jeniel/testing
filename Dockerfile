# Use full Python 3.9 bullseye image (non-slim) for proper timezone support
FROM python:3.9-bullseye

# -----------------------------
# Set working directory
# -----------------------------
WORKDIR /app

# -----------------------------
# Set environment variables
# -----------------------------
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV TZ=Asia/Manila

# -----------------------------
# Install system dependencies and configure timezone
# -----------------------------
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y \
    gcc \
    iputils-ping \
    tzdata \
    && ln -sf /usr/share/zoneinfo/Asia/Manila /etc/localtime \
    && echo "Asia/Manila" > /etc/timezone \
    && dpkg-reconfigure -f noninteractive tzdata \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# -----------------------------
# Copy requirements first to leverage Docker cache
# -----------------------------
COPY requirements.txt .

# -----------------------------
# Install Python dependencies
# -----------------------------
RUN pip install --no-cache-dir -r requirements.txt

# -----------------------------
# Copy application code
# -----------------------------
COPY . .

# -----------------------------
# Create non-root user for security and set timezone permissions
# -----------------------------
RUN adduser --disabled-password --gecos '' appuser \
    && chown -R appuser:appuser /app \
    && chmod 644 /etc/localtime /etc/timezone

# Allow non-root user to use ping
RUN setcap cap_net_raw+ep /usr/bin/ping || true

# -----------------------------
# Switch to non-root user
# -----------------------------
USER appuser

# -----------------------------
# Expose the port the app runs on
# -----------------------------
EXPOSE 4000

# -----------------------------
# Set locale and TZ explicitly (for Python inside container)
# -----------------------------
ENV LC_ALL=C
ENV LANG=C

# -----------------------------
# Run the application
# -----------------------------
CMD ["python", "zktime_server.py"]
