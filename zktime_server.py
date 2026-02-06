from flask import Flask, jsonify, request
from zk import ZK
from datetime import datetime
import os
import time

# =====================================================
# ENVIRONMENT FIX (Kubernetes / Docker SAFE)
# =====================================================
os.environ["TZ"] = "Asia/Manila"
if hasattr(time, "tzset"):
    time.tzset()

app = Flask(__name__)

# =====================================================
# CONFIG
# =====================================================
DEFAULT_PORT = int(os.getenv("DEVICE_PORT", 4370))
DEFAULT_DEVICE_IP = os.getenv("DEVICE_IP")

PUNCH_STATE = {
    0: "IN",
    1: "OUT",
    2: "BREAK_IN",
    3: "BREAK_OUT",
    4: "OVERTIME_IN",
    5: "OVERTIME_OUT"
}

# =====================================================
# UTILS
# =====================================================
def connect_device(ip: str):
    zk = ZK(ip, port=DEFAULT_PORT, timeout=5)
    conn = zk.connect()
    return zk, conn


def safe_parse_timestamp(ts):
    """
    FINAL SAFE timestamp parser
    - skips corrupted ZKTeco records
    - Python 3.11 safe
    """
    try:
        if ts is None:
            return None

        if isinstance(ts, datetime):
            ts.replace()  # force validation
            return ts

        if isinstance(ts, str):
            return datetime.strptime(ts[:19], "%Y-%m-%d %H:%M:%S")

    except Exception:
        return None


def safe_get_attendance(conn):
    """
    CRITICAL FIX:
    - skips corrupted records BEFORE they crash the app
    """
    valid_records = []
    skipped = 0

    for att in conn.get_attendance():
        try:
            ts = att.timestamp
            parsed = safe_parse_timestamp(ts)
            if parsed is None:
                skipped += 1
                continue

            valid_records.append(att)

        except Exception:
            skipped += 1

    return valid_records, skipped


# =====================================================
# ROUTES
# =====================================================
@app.route("/logs")
def get_logs():
    ip = request.args.get("ip") or DEFAULT_DEVICE_IP
    if not ip:
        return jsonify({
            "success": False,
            "message": "Missing required parameter: ip"
        }), 400

    # Optional start date filter
    start_date = None
    start_date_str = request.args.get("start")
    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
        except ValueError:
            return jsonify({
                "success": False,
                "message": "Invalid start date format. Use YYYY-MM-DD"
            }), 400

    zk = conn = None
    try:
        zk, conn = connect_device(ip)
        attendances, skipped = safe_get_attendance(conn)

        logs = []

        for att in attendances:
            timestamp = safe_parse_timestamp(att.timestamp)
            if timestamp is None:
                continue

            if start_date and timestamp < start_date:
                continue

            punch_code = getattr(att, "punch", None)
            if punch_code is None:
                punch_code = getattr(att, "status", None)

            logs.append({
                "user_id": att.user_id,
                "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "punch": PUNCH_STATE.get(punch_code, "Unknown"),
                "status": getattr(att, "status", None),
            })

        return jsonify({
            "success": True,
            "count": len(logs),
            "logs": logs,
            "total_corrupted_skipped": skipped,
            "device_ip": ip
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e),
            "device_ip": ip
        }), 500

    finally:
        if conn:
            conn.disconnect()


@app.route("/ping")
def ping():
    return jsonify({"success": True, "message": "ZKTeco middleware is alive"})


# =====================================================
# MAIN
# =====================================================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=4000, debug=True)
