# Use Python 3.9 bullseye image as base
FROM python:3.9-bullseye

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV TZ=Asia/Manila

# Install system dependencies
# - gcc (for some Python deps)
# - iputils-ping (para makapag-ping)
# - tzdata (IMPORTANT for timezone)
RUN apt-get update && apt-get install -y \
    gcc \
    iputils-ping \
    tzdata \
    && ln -sf /usr/share/zoneinfo/Asia/Manila /etc/localtime \
    && echo "Asia/Manila" > /etc/timezone \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user for security
RUN adduser --disabled-password --gecos '' appuser && \
    chown -R appuser:appuser /app

# Allow non-root user to use ping
RUN setcap cap_net_raw+ep /usr/bin/ping || true

USER appuser

# Expose the port the app runs on
EXPOSE 4000

# Run the application
CMD ["python", "zktime_server.py"]
