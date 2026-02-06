# Base image
FROM python:3.9-slim

# Working directory
WORKDIR /app

# Environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Manila

# Install system dependencies + tzdata
RUN apt-get update && apt-get install -y \
    gcc \
    iputils-ping \
    libcap2-bin \
    tzdata \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy and install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ZKTeco patch (skip invalid timestamps)
RUN SITE_PKG=$(python -c "import site; print(site.getsitepackages()[0])") && \
    sed -i 's/return datetime(year, month, day, hour, minute, second)/try:\n            return datetime(year, month, day, hour, minute, second)\n        except ValueError:\n            return None/g' ${SITE_PKG}/zk/base.py

# Copy application code
COPY . .

# Add non-root user and permissions
RUN adduser --disabled-password --gecos '' appuser && \
    chown -R appuser:appuser /app && \
    setcap cap_net_raw+ep /usr/bin/ping

# Copy entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

USER appuser
EXPOSE 4000

# Entrypoint & CMD
ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "zktime_server.py"]
