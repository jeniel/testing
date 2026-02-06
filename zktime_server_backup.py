from flask import Flask, jsonify, request
from zk import ZK, const
from datetime import datetime

app = Flask(__name__)

DEFAULT_PORT = 4370


def connect_device(ip: str):
    """
    Connect to a ZKTeco biometric device by IP.
    """
    zk = ZK(ip, port=DEFAULT_PORT, timeout=5)
    conn = zk.connect()
    return zk, conn


# Punch state mapping (common meanings)
PUNCH_STATE = {
    0: "IN",
    1: "OUT",
    2: "BREAK_IN",
    3: "BREAK_OUT",
    4: "OVERTIME_IN",
    5: "OVERTIME_OUT",
}


@app.route("/logs")
def get_logs():
    """
    Middleware endpoint for fetching biometric attendance logs.
    Query Params:
      ip     (required): Biometric device IP address
      start  (optional): Start date (YYYY-MM-DD)

    Example:
      GET /logs?ip=192.168.1.31&start=2025-10-01
    """
    ip = request.args.get("ip")
    start_date_str = request.args.get("start")

    if not ip:
        return jsonify({"success": False, "message": "Missing required parameter: ip"}), 400

    # Parse start date (optional)
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d") if start_date_str else None

    try:
        zk, conn = connect_device(ip)
        attendances = conn.get_attendance()
        conn.disconnect()

        logs = []
        for att in attendances:
            # Ensure timestamp is a datetime object
            timestamp = att.timestamp
            if isinstance(timestamp, str):
                try:
                    timestamp = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    continue  # skip invalid timestamps

            # Apply start date filter
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

        return jsonify({"success": True, "count": len(logs), "logs": logs})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500



@app.route("/ping-test")
def ping_test():
    """
    Quick connectivity test.
    Example:
      GET /ping-test?ip=192.168.1.31
    """
    ip = request.args.get("ip")
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
    return jsonify(
        {
            "routes": {
                "/ping-test?ip=DEVICE_IP": "Check device connection",
                "/logs?ip=DEVICE_IP&start=YYYY-MM-DD&end=YYYY-MM-DD": "Fetch attendance logs",
            }
        }
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=4000, debug=True)