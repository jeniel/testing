# 🕓 ZKTeco Python Middleware

A lightweight **Python Flask middleware** for communicating with **ZKTeco biometric devices** (fingerprint, face, or RFID).
This middleware acts as a **bridge between ZKTeco devices and HISMK2 HR** — allowing you to easily fetch attendance logs or test connectivity through simple REST endpoints.

---

## 🚀 Features

✅ Connect to ZKTeco devices over LAN
✅ Retrieve biometric attendance logs
✅ Filter logs by date
✅ Test device connectivity (ping test)
✅ Simple RESTful API interface

---

## 🧰 Requirements

- **Python 3.9+**
- **ZKTeco device** connected via LAN
- Access to device IP and port (default: `4370`)

Dependencies are listed in [`requirements.txt`](./requirements.txt):

```
Flask==3.1.0
pyzk==0.9
```

---

## ⚙️ Installation & Setup

### 1️⃣ Clone the repository

```bash
git clone https://github.com/hisd3/zkteco-py-middleware
cd zkteco-py-middleware
```

### 2️⃣ (Optional) Create and activate a virtual environment

```bash
python -m venv venv
source venv/bin/activate      # macOS/Linux
venv\Scripts\activate         # Windows
```

### 3️⃣ Install dependencies

```bash
pip install -r requirements.txt
```

### 4️⃣ Run the server

```bash
python zktime_server.py
```

By default, the middleware runs at:
👉 **[http://localhost:4000](http://localhost:4000)**

---

## 🌐 Available Endpoints

### 1️⃣ `GET /ping-test`

Quick connectivity test — checks if the ZKTeco device is reachable and responding.

#### **Parameters**

| Name | Type   | Required | Description       |
| ---- | ------ | -------- | ----------------- |
| `ip` | string | ✅       | Device IP address |

#### **Example Request**

```
GET /ping-test?ip=192.168.1.31
```

#### **Example Response**

```json
{
  "success": true,
  "message": "Connected",
  "device_info": "ZKTeco UFace 302"
}
```

---

### 2️⃣ `GET /logs`

Fetches attendance logs from the device.
Supports optional date filtering via `start` (and later `end`).

#### **Parameters**

| Name    | Type   | Required | Description                     |
| ------- | ------ | -------- | ------------------------------- |
| `ip`    | string | ✅       | Device IP address               |
| `start` | string | ❌       | Start date (format: YYYY-MM-DD) |

#### **Example Request**

```
GET /logs?ip=192.168.1.31&start=2025-10-01
```

#### **Example Response**

```json
{
  "success": true,
  "count": 3,
  "logs": [
    {
      "user_id": 1,
      "timestamp": "2025-10-21 07:30:25",
      "raw_punch_code": 0,
      "punch": "IN",
      "status": 0
    },
    {
      "user_id": 1,
      "timestamp": "2025-10-21 17:30:10",
      "raw_punch_code": 1,
      "punch": "OUT",
      "status": 1
    }
  ]
}
```

---

### 3️⃣ `GET /`

Displays a simple JSON guide of available routes.

#### **Example Response**

```json
{
  "routes": {
    "/ping-test?ip=DEVICE_IP": "Check device connection",
    "/logs?ip=DEVICE_IP&start=YYYY-MM-DD&end=YYYY-MM-DD": "Fetch attendance logs"
  }
}
```

---

## 💡 Usage Example

You can call the middleware using **cURL**, **Postman**, or from your own backend:

```bash
curl "http://localhost:4000/logs?ip=192.168.1.31&start=2025-10-01"
```

This returns a JSON list of all attendance logs since the given start date.

---

## 🧠 How It Works (Overview)

1. The Flask app exposes simple HTTP routes.
2. When `/logs` or `/ping-test` is called, it connects to the ZKTeco device using the `pyzk` library.
3. Data (like logs or device info) is fetched directly from the biometric device.
4. The server then returns the data as JSON — making it easy for other systems to consume.

---

## 🧑‍💻 Author

**John Michael C. Hinacay**
# testing
