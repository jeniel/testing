from flask import Flask, jsonify, request
from zk import ZK, const
from datetime import datetime
import os
import locale
import sys
import time

# =====================================================
# ENVIRONMENT INITIALIZATION (Docker / K8s SAFE)
# =====================================================
def initialize_environment():
    """
    Force consistent locale and timezone handling.
    Target timezone: Asia/Manila (PHT)
    """
    # Locale (avoid date parsing issues)
    try:
        locale.setlocale(locale.LC_ALL, "C")
    except:
        pass

    # Timezone
    os.environ["TZ"] = "Asia/Manila"
    if hasattr(time, "tzset"):
        time.tzset()

initialize_environment()

app = Flask(__name__)

# =====================================================
# TIMESTAMP FORMATS
# =====================================================
TIMESTAMP_FORMATS = [
    "%Y-%m-%d %H:%M:%S",
    "%d-%m-%Y %H:%M:%S",
    "%m-%d-%Y %H:%M:%S",
    "%Y/%m/%d %H:%M:%S",
    "%d/%m/%Y %H:%M:%S",
    "%m/%d/%Y %H:%M:%S",
    "%Y%m%d%H%M%S",
    "%d.%m.%Y %H:%M:%S",
    "%Y.%m.%d %H:%M:%S",
]

def safe_parse_timestamp(ts):
    """
    Safely parse timestamps from ZKTeco.
    Always returns NAIVE datetime assumed as PHT.
    """
    debug = {
        "original_value": ts,
        "original_type": type(ts).__name__,
        "parsed_successfully": False,
        "format_used": None,
    }

    if isinstance(ts, datetime):
        debug["parsed_successfully"] = True
        debug["format_used"] = "datetime_object"
        return ts.replace(tzinfo=None), debug

    if isinstance(ts, str):
        for fmt in TIMESTAMP_FORMATS:
            try:
                parsed = datetime.strptime(ts, fmt)
                debug["parsed_successfully"] = True
                debug["format_used"] = fmt
                return parsed, debug
            except ValueError:
                continue

    debug["error"] = "Unable to parse timestamp"
    return None, debug

# =====================================================
# DEVICE CONFIG
# =====================================================
DEFAULT_PORT = int(os.getenv("DEVICE_PORT", 4370))
DEFAULT_DEVICE_IP = os.getenv("DEVICE_IP")

def connect_device(ip: str):
    zk = ZK(ip, port=DEFAULT_PORT, timeout=5)
    conn = zk.connect()
    return zk, conn

def safe_get_attendance(conn, device_ip):
    """
    Fetch attendance safely under PHT timezone.
    """
    try:
        return conn.get_attendance(), None
    except Exception as e:
        error_msg = str(e)
        if "day is out of range for month" in error_msg:
            return None, {
                "error_type": "timezone_date_parsing_error",
                "original_error": error_msg,
                "device_ip": device_ip,
                "timezone_used": "Asia/Manila",
            }
        return None, {
            "error_type": "general_error",
            "original_error": error_msg,
            "device_ip": device_ip,
        }

# =====================================================
# PUNCH STATE MAP
# =====================================================
PUNCH_STATE = {
    0: "IN",
    1: "OUT",
    2: "BREAK_IN",
    3: "BREAK_OUT",
    4: "OVERTIME_IN",
    5: "OVERTIME_OUT",
}

# =====================================================
# ROUTES
# =====================================================
@app.route("/logs")
def get_logs():
    ip = request.args.get("ip") or DEFAULT_DEVICE_IP
    if not ip:
        return jsonify({"success": False, "message": "Missing ip"}), 400

    start_date_str = request.args.get("start")
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d") if start_date_str else None

    try:
        zk, conn = connect_device(ip)
        attendances, error_info = safe_get_attendance(conn, ip)
        conn.disconnect()

        if attendances is None:
            return jsonify({"success": False, "error": error_info}), 500

        logs = []
        parsing_errors = []

        for i, att in enumerate(attendances):
            ts, debug = safe_parse_timestamp(att.timestamp)
            if not ts:
                parsing_errors.append({"index": i, "debug": debug})
                continue

            if start_date and ts < start_date:
                continue

            punch_code = getattr(att, "punch", getattr(att, "status", None))

            logs.append({
                "user_id": att.user_id,
                "timestamp": ts.strftime("%Y-%m-%d %H:%M:%S"),
                "punch": PUNCH_STATE.get(punch_code, "Unknown"),
                "raw_punch_code": punch_code,
            })

        response = {
            "success": True,
            "count": len(logs),
            "logs": logs,
            "device_ip": ip,
        }

        if parsing_errors:
            response["parsing_errors"] = parsing_errors[:10]
            response["total_parsing_errors"] = len(parsing_errors)

        return jsonify(response)

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/ping-test")
def ping_test():
    ip = request.args.get("ip") or DEFAULT_DEVICE_IP
    if not ip:
        return jsonify({"success": False, "message": "Missing ip"}), 400

    try:
        zk, conn = connect_device(ip)
        info = conn.get_device_name()
        conn.disconnect()
        return jsonify({"success": True, "device_info": info})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/")
def home():
    return jsonify({
        "routes": {
            "/ping-test?ip=DEVICE_IP": "Test device connection",
            "/logs?ip=DEVICE_IP&start=YYYY-MM-DD": "Fetch attendance logs",
        },
        "timezone": "Asia/Manila (PHT)",
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=4000, debug=True)
