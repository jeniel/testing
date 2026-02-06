#!/bin/sh
# ----------------------------
# Force Manila timezone at fail-safe
# ----------------------------

# Overwrite /etc/localtime symlink
if [ -f /usr/share/zoneinfo/Asia/Manila ]; then
    ln -sf /usr/share/zoneinfo/Asia/Manila /etc/localtime
    echo "Asia/Manila" > /etc/timezone
fi

# Export TZ for Python
export TZ=Asia/Manila

# Optional: Print timezone check
echo "Container timezone: $(date)"

# Execute main command
exec "$@"
