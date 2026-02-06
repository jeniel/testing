from flask import Flask, jsonify, request
from zk import ZK, const
from datetime import datetime
import os
import locale
import sys

app = Flask(__name__)

# Force consistent locale and timezone handling to avoid environment-specific issues
def initialize_environment():
    """
    Initialize consistent environment settings to avoid timezone/locale issues.
    Forces Philippine Time since local environment (PHT) works correctly.
    """
    try:
        # Set locale to C (standard) to avoid locale-specific date parsing issues
        locale.setlocale(locale.LC_ALL, 'C')
    except:
        try:
            # Fallback to POSIX standard
            locale.setlocale(locale.LC_ALL, 'POSIX') 
        except:
            # If all fails, just continue - the safe parsing should handle it
            pass
    
    # Force Philippine Time since that's what works in local environment
    # This affects how the pyzk library internally processes dates from the device
    os.environ['TZ'] = 'Asia/Manila'
    
    # Call tzset to apply the timezone change (Unix/Linux only)
    if hasattr(os, 'tzset'):
        os.tzset()

# Initialize environment before anything else
initialize_environment()

# Supported timestamp formats from ZKTeco devices
TIMESTAMP_FORMATS = [
    "%Y-%m-%d %H:%M:%S",  # 2025-05-19 12:07:18
    "%d-%m-%Y %H:%M:%S",  # 19-05-2025 12:07:18
    "%m-%d-%Y %H:%M:%S",  # 05-19-2025 12:07:18
    "%Y/%m/%d %H:%M:%S",  # 2025/05/19 12:07:18
    "%d/%m/%Y %H:%M:%S",  # 19/05/2025 12:07:18
    "%m/%d/%Y %H:%M:%S",  # 05/19/2025 12:07:18
    "%Y%m%d%H%M%S",       # 20250519120718 (compact format)
    "%d.%m.%Y %H:%M:%S",  # 19.05.2025 12:07:18
    "%Y.%m.%d %H:%M:%S",  # 2025.05.19 12:07:18
]

def parse_timestamp(ts):
    """
    Parse a timestamp that could be a datetime object or a string in various formats.
    Returns a datetime object or None if parsing fails.
    """
    if isinstance(ts, datetime):
        return ts
    if isinstance(ts, str):
        for fmt in TIMESTAMP_FORMATS:
            try:
                return datetime.strptime(ts, fmt)
            except ValueError:
                continue
    return None

def safe_parse_timestamp(ts, debug_info=None):
    """
    Enhanced timestamp parsing with debugging and error handling.
    Handles timezone-aware and naive datetime objects consistently.
    Returns a tuple: (datetime_obj, debug_dict)
    """
    debug = {
        "original_value": ts,
        "original_type": type(ts).__name__,
        "parsed_successfully": False,
        "format_used": None,
        "error": None,
        "timezone_info": None
    }
    
    try:
        # If already a datetime object, handle timezone issues
        if isinstance(ts, datetime):
            debug["parsed_successfully"] = True
            debug["format_used"] = "datetime_object"
            
            # Check if it's timezone-aware
            if ts.tzinfo is not None:
                debug["timezone_info"] = str(ts.tzinfo)
                # Convert to naive UTC datetime for consistency
                if ts.utctimetuple():
                    # Convert to UTC naive datetime
                    naive_utc = datetime.utctimetuple(ts)
                    result = datetime(*naive_utc[:6])
                    debug["format_used"] = "datetime_object_tz_converted"
                    return result, debug
            else:
                debug["timezone_info"] = "naive"
            
            return ts, debug
        
        # If it's a string, try various formats
        if isinstance(ts, str):
            # First try to handle common ZKTeco string formats
            for fmt in TIMESTAMP_FORMATS:
                try:
                    parsed_dt = datetime.strptime(ts, fmt)
                    debug["parsed_successfully"] = True
                    debug["format_used"] = fmt
                    debug["timezone_info"] = "naive_from_string"
                    return parsed_dt, debug
                except ValueError as e:
                    continue
            
            # If no format worked, record the error
            debug["error"] = f"No matching format found for string: '{ts}'"
        else:
            debug["error"] = f"Unexpected timestamp type: {type(ts)}"
            
    except Exception as e:
        debug["error"] = str(e)
    
    return None, debug

# Default port for ZKTeco device
DEFAULT_PORT = int(os.getenv("DEVICE_PORT", 4370))  # read from env or fallback 4370
DEFAULT_DEVICE_IP = os.getenv("DEVICE_IP")          # read from env

def connect_device(ip: str):
    """
    Connect to a ZKTeco biometric device by IP.
    """
    zk = ZK(ip, port=DEFAULT_PORT, timeout=5)
    conn = zk.connect()
    return zk, conn

def safe_get_attendance(conn, device_ip):
    """
    Safely get attendance data with timezone handling.
    Forces Philippine Time during library call since that works in local environment.
    """
    try:
        # Force Philippine Time for the library call
        original_tz = os.environ.get('TZ')
        os.environ['TZ'] = 'Asia/Manila'
        if hasattr(os, 'tzset'):
            os.tzset()
        
        # Get attendance data with PHT timezone
        result = conn.get_attendance()
        
        # Restore original timezone (though it should already be Asia/Manila)
        if original_tz:
            os.environ['TZ'] = original_tz
        else:
            os.environ['TZ'] = 'Asia/Manila'  # Keep it as Manila
        if hasattr(os, 'tzset'):
            os.tzset()
            
        return result, None
        
    except Exception as e:
        # Restore timezone even if it fails
        try:
            if original_tz:
                os.environ['TZ'] = original_tz
            else:
                os.environ['TZ'] = 'Asia/Manila'
            if hasattr(os, 'tzset'):
                os.tzset()
        except:
            pass
            
        error_msg = str(e)
        if "day is out of range for month" in error_msg:
            return None, {
                "error_type": "timezone_date_parsing_error",
                "original_error": error_msg,
                "suggested_fix": "Timezone issue persists even with PHT. May be device firmware or data corruption.",
                "device_ip": device_ip,
                "timezone_used": "Asia/Manila"
            }
        else:
            return None, {
                "error_type": "general_error", 
                "original_error": error_msg,
                "device_ip": device_ip
            }

# Punch state mapping
PUNCH_STATE = {
    0: "IN",
    1: "OUT",
    2: "BREAK_IN",
    3: "BREAK_OUT",
    4: "OVERTIME_IN",
    5: "OVERTIME_OUT",
}

@app.route("/debug-environment")
def debug_environment():
    """
    Debug endpoint to check environment differences between local and deployed.
    """
    import sys
    import locale
    import platform
    import time
    
    try:
        import zk
        zk_version = getattr(zk, '__version__', 'unknown')
    except:
        zk_version = 'unknown'

    try:
        current_locale = locale.getlocale()
        default_locale = locale.getdefaultlocale()
    except:
        current_locale = 'unknown'
        default_locale = 'unknown'

    # Get timezone information
    try:
        import time
        timezone_info = {
            "timezone_name": time.tzname,
            "daylight_saving": time.daylight,
            "timezone_offset": time.timezone,
            "current_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "utc_time": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        }
    except:
        timezone_info = "unknown"

    return jsonify({
        "python_version": sys.version,
        "platform": platform.platform(),
        "pyzk_version": zk_version,
        "current_locale": current_locale,
        "default_locale": default_locale,
        "timezone_info": timezone_info,
        "environment_vars": {
            "TZ": os.environ.get('TZ', 'not_set'),
            "LANG": os.environ.get('LANG', 'not_set'),
            "LC_ALL": os.environ.get('LC_ALL', 'not_set'),
            "LC_TIME": os.environ.get('LC_TIME', 'not_set'),
        }
    })

@app.route("/debug-timestamps")
def debug_timestamps():
    """
    Debug endpoint to examine raw timestamp formats from devices.
    """
    ip = request.args.get("ip") or DEFAULT_DEVICE_IP
    if not ip:
        return jsonify({"success": False, "message": "Missing required parameter: ip"}), 400

    limit = int(request.args.get("limit", 5))  # Limit to first N records

    try:
        zk, conn = connect_device(ip)
        
        # Use safe attendance retrieval
        attendances, error_info = safe_get_attendance(conn, ip)
        conn.disconnect()
        
        if attendances is None:
            return jsonify({
                "success": False, 
                "device_ip": ip,
                "library_error": error_info
            }), 500

        debug_data = []
        processed_count = 0
        
        for att in attendances:
            if processed_count >= limit:
                break
                
            timestamp, debug_info = safe_parse_timestamp(att.timestamp)
            
            debug_data.append({
                "user_id": att.user_id,
                "raw_timestamp": att.timestamp,
                "raw_timestamp_type": type(att.timestamp).__name__,
                "raw_timestamp_repr": repr(att.timestamp),
                "parsed_timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S") if timestamp else None,
                "debug_info": debug_info,
                "punch_code": getattr(att, "punch", None),
                "status": getattr(att, "status", None),
            })
            processed_count += 1

        return jsonify({
            "success": True, 
            "device_ip": ip,
            "total_records": len(attendances),
            "debug_sample": debug_data
        })

    except Exception as e:
        return jsonify({"success": False, "message": str(e), "device_ip": ip}), 500

@app.route("/logs")
def get_logs():
    """
    Fetch attendance logs.
    Optional fallback to DEVICE_IP env if no ip query param is provided.
    """
    ip = request.args.get("ip") or DEFAULT_DEVICE_IP
    if not ip:
        return jsonify({"success": False, "message": "Missing required parameter: ip"}), 400

    start_date_str = request.args.get("start")
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d") if start_date_str else None

    try:
        zk, conn = connect_device(ip)
        
        # Use safe attendance retrieval
        attendances, error_info = safe_get_attendance(conn, ip)
        conn.disconnect()
        
        if attendances is None:
            return jsonify({
                "success": False, 
                "message": f"Failed to retrieve attendance data: {error_info['original_error']}",
                "device_ip": ip,
                "error_details": error_info
            }), 500

        logs = []
        parsing_errors = []
        
        for i, att in enumerate(attendances):
            timestamp, debug_info = safe_parse_timestamp(att.timestamp, f"record_{i}")
            
            if timestamp is None:
                # Collect parsing errors for debugging
                parsing_errors.append({
                    "record_index": i,
                    "user_id": getattr(att, "user_id", "unknown"),
                    "debug_info": debug_info
                })
                continue

            if start_date and timestamp < start_date:
                continue

            punch_code = getattr(att, "punch", None)
            if punch_code is None:
                punch_code = getattr(att, "status", None)

            logs.append(
                {
                    "user_id": att.user_id,
                    "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                    "raw_punch_code": punch_code,
                    "punch": PUNCH_STATE.get(punch_code, "Unknown"),
                    "status": getattr(att, "status", None),
                }
            )

        response_data = {
            "success": True, 
            "count": len(logs), 
            "logs": logs,
            "device_ip": ip
        }
        
        # Include parsing errors if any (for debugging)
        if parsing_errors:
            response_data["parsing_errors"] = parsing_errors[:10]  # Limit to first 10
            response_data["total_parsing_errors"] = len(parsing_errors)

        return jsonify(response_data)

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/ping-test")
def ping_test():
    """
    Quick connectivity test.
    Uses DEVICE_IP env if no query parameter provided.
    """
    ip = request.args.get("ip") or DEFAULT_DEVICE_IP
    if not ip:
        return jsonify({"success": False, "message": "Missing required parameter: ip"}), 400

    try:
        zk, conn = connect_device(ip)
        info = conn.get_device_name()
        conn.disconnect()
        return jsonify({"success": True, "message": "Connected", "device_info": info})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/")
def home():
    """
    Homepage listing available routes.
    """
    return jsonify(
        {
            "routes": {
                "/ping-test?ip=DEVICE_IP": "Check device connection",
                "/logs?ip=DEVICE_IP&start=YYYY-MM-DD": "Fetch attendance logs",
                "/debug-timestamps?ip=DEVICE_IP&limit=5": "Debug timestamp formats (default 5 records)",
                "/debug-environment": "Show environment info (Python version, locale, etc.)",
            },
            "note": "DEVICE_IP will default to env variable if not provided in query."
        }
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=4000, debug=True)
