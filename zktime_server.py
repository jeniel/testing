from flask import Flask, jsonify, request
from zk import ZK, const
from datetime import datetime, timedelta
import os, time, locale

# =====================================================
# ENVIRONMENT INITIALIZATION (Docker / K8s SAFE)
# =====================================================
def initialize_environment():
    """Force consistent locale and timezone handling (PHT)."""
    try:
        locale.setlocale(locale.LC_ALL, "C")
    except:
        pass
    os.environ["TZ"] = "Asia/Manila"  # UTC+8
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
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds
DEVICE_GMT_OFFSET = -8  # If device is Etc/GMT+8, shift by 16h to PHT

def connect_device(ip: str):
    zk = ZK(ip, port=DEFAULT_PORT, timeout=5)
    conn = zk.connect()
    return zk, conn

def safe_get_attendance(conn, device_ip):
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

def sync_device_time(device_ip):
    """Sync device clock to current server PHT."""
    zk = ZK(device_ip, port=DEFAULT_PORT, timeout=5)
    try:
        conn = zk.connect()
        now = datetime.now()
        conn.set_time(now)
        conn.disconnect()
        return True, now
    except Exception as e:
        return False, str(e)

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
# TIME CHECK FUNCTION
# =====================================================
def check_all_times(device_ip):
    container_time = datetime.now()
    server_time = datetime.utcnow() + timedelta(hours=8)  # PHT
    try:
        zk, conn = connect_device(device_ip)
        device_time = conn.get_time()
        conn.disconnect()
    except Exception as e:
        device_time = f"Error: {str(e)}"

    diff_server_device = diff_container_device = None
    if isinstance(device_time, datetime):
        diff_server_device = server_time - device_time
        diff_container_device = container_time - device_time

    return {
        "container_time": str(container_time),
        "server_time": str(server_time),
        "device_time": str(device_time),
        "diff_server_device": str(diff_server_device),
        "diff_container_device": str(diff_container_device),
    }

# =====================================================
# /logs ROUTE
# =====================================================
@app.route("/logs")
def get_logs():
    ip = request.args.get("ip") or DEFAULT_DEVICE_IP
    if not ip:
        return jsonify({"success": False, "message": "Missing ip"}), 400

    start_date_str = request.args.get("start")
    try:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d") if start_date_str else None
    except Exception:
        start_date = None

    # Retry logic for device connection
    attendances = None
    error_info = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            zk, conn = connect_device(ip)
            attendances, error_info = safe_get_attendance(conn, ip)
            conn.disconnect()
            if attendances is not None:
                break
        except Exception as e:
            error_info = {"error_type": "connection_error", "original_error": str(e), "device_ip": ip}
        time.sleep(RETRY_DELAY)

    logs = []
    parsing_errors = []

    if attendances is None and error_info:
        # Include device error as pseudo-log
        logs.append({
            "user_id": None,
            "timestamp": str(datetime.now()),
            "punch": "ERROR",
            "raw_punch_code": None,
            "corrupted": True,
            "device_error": error_info
        })
        return jsonify({
            "success": True,
            "device_ip": ip,
            "count": 0,
            "logs": logs,
            "total_parsing_errors": 0,
        })

    # Process each attendance record
    for i, att in enumerate(attendances):
        ts, debug = safe_parse_timestamp(att.timestamp)

        if ts:
            # Adjust if device is Etc/GMT+8 (UTC-8) → shift 16h to PHT
            ts += timedelta(hours=8 - DEVICE_GMT_OFFSET)  # 8 - (-8) = 16h
        else:
            parsing_errors.append({
                "index": i,
                "user_id": getattr(att, "user_id", None),
                "original_value": debug["original_value"],
                "original_type": debug["original_type"],
                "error": debug.get("error", "Unknown parse error"),
            })
            logs.append({
                "user_id": getattr(att, "user_id", None),
                "timestamp": str(debug["original_value"]),
                "punch": PUNCH_STATE.get(getattr(att, "punch", getattr(att, "status", None)), "Unknown"),
                "raw_punch_code": getattr(att, "punch", getattr(att, "status", None)),
                "corrupted": True
            })
            continue

        if start_date and ts < start_date:
            continue

        punch_code = getattr(att, "punch", getattr(att, "status", None))
        logs.append({
            "user_id": att.user_id,
            "timestamp": ts.strftime("%Y-%m-%d %H:%M:%S"),
            "punch": PUNCH_STATE.get(punch_code, "Unknown"),
            "raw_punch_code": punch_code,
            "corrupted": False
        })

    return jsonify({
        "success": True,
        "device_ip": ip,
        "count": len(logs),
        "logs": logs,
        "total_parsing_errors": len(parsing_errors),
        "parsing_errors": parsing_errors[:10]  # first 10
    })

# =====================================================
# OTHER ROUTES
# =====================================================
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

@app.route("/sync-time")
def sync_time():
    ip = request.args.get("ip") or DEFAULT_DEVICE_IP
    if not ip:
        return jsonify({"success": False, "message": "Missing ip"}), 400

    success, result = sync_device_time(ip)
    if success:
        return jsonify({"success": True, "device_ip": ip, "synced_time": str(result)})
    else:
        return jsonify({"success": False, "device_ip": ip, "error": result})

@app.route("/time-check")
def time_check():
    ip = request.args.get("ip") or DEFAULT_DEVICE_IP
    if not ip:
        return jsonify({"success": False, "message": "Missing ip"}), 400

    times_info = check_all_times(ip)
    return jsonify({"success": True, "device_ip": ip, "times": times_info})

@app.route("/")
def home():
    return jsonify({
        "routes": {
            "/ping-test?ip=DEVICE_IP": "Test device connection",
            "/logs?ip=DEVICE_IP&start=YYYY-MM-DD": "Fetch attendance logs (corrupted logs included)",
            "/sync-time?ip=DEVICE_IP": "Sync device clock to server PHT",
            "/time-check?ip=DEVICE_IP": "Check container/server/device time",
        },
        "timezone": "Asia/Manila (PHT)",
    })

# =====================================================
# RUN FLASK
# =====================================================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=4000, debug=True)
