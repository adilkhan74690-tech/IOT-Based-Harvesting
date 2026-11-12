import os
import re
import time
import threading
import serial
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from weather_service import WeatherService
from recommendation_engine import RecommendationEngine

app = Flask(__name__)
CORS(app)

# Configuration from environment variables with safe defaults
SERIAL_PORT = os.getenv("SERIAL_PORT", "COM7")
BAUD_RATE = int(os.getenv("BAUD_RATE", "9600"))
DEFAULT_LATITUDE = float(os.getenv("DEFAULT_LATITUDE", "30.9010"))
DEFAULT_LONGITUDE = float(os.getenv("DEFAULT_LONGITUDE", "75.8573"))
DEFAULT_LOCATION_NAME = os.getenv("DEFAULT_LOCATION_NAME", "Ludhiana, Punjab, India")

# Services
weather_service = WeatherService(
    default_lat=DEFAULT_LATITUDE,
    default_lon=DEFAULT_LONGITUDE,
    default_location_name=DEFAULT_LOCATION_NAME
)
recommendation_engine = RecommendationEngine()

# Latest Arduino data
latest_data = {
    "connected": False,
    "time": None,
    "distance": None,
    "level": None,
    "rain_raw": None,
    "raining": None,
    "full": None,
    "lid": None,
    "pump": None,
    "led": None,
    "last_updated": None,
    "error": None
}

data_lock = threading.Lock()


def parse_arduino_data(line):
    """Parse the existing Arduino Serial Monitor output."""
    try:
        data = {}

        time_match = re.search(r"Time:\s*(\d+)s", line)
        distance_match = re.search(r"Dist:\s*([\d.]+)\s*cm", line)
        level_match = re.search(r"Level:\s*(\d+)%", line)
        rain_match = re.search(r"Rain raw:\s*(\d+)\s*\((DRY|RAIN)\)", line)
        full_match = re.search(r"Full:\s*(YES|NO)", line)
        lid_match = re.search(r"Lid:\s*(OPEN|CLOSED)", line)
        pump_match = re.search(r"Pump:\s*(ON|OFF)", line)
        led_match = re.search(r"LED:\s*(BLUE|RED|YELLOW|GREEN)", line)

        if not all([
            time_match, distance_match, level_match,
            rain_match, full_match, lid_match,
            pump_match, led_match
        ]):
            return None

        data["time"] = int(time_match.group(1))
        data["distance"] = float(distance_match.group(1))
        data["level"] = int(level_match.group(1))
        data["rain_raw"] = int(rain_match.group(1))
        data["raining"] = rain_match.group(2) == "RAIN"
        data["full"] = full_match.group(1) == "YES"
        data["lid"] = lid_match.group(1)
        data["pump"] = pump_match.group(1)
        data["led"] = led_match.group(1)

        return data

    except (ValueError, AttributeError):
        return None


def read_arduino():
    """Continuously read Arduino data in a background thread."""
    while True:
        try:
            print(f"Connecting to Arduino on {SERIAL_PORT}...")

            with serial.Serial(
                SERIAL_PORT,
                BAUD_RATE,
                timeout=2
            ) as arduino:

                time.sleep(2)
                arduino.reset_input_buffer()

                print("Arduino connected successfully!")

                with data_lock:
                    latest_data["connected"] = True
                    latest_data["error"] = None

                while True:
                    line = arduino.readline().decode(
                        "utf-8", errors="replace"
                    ).strip()

                    if not line:
                        continue

                    parsed = parse_arduino_data(line)

                    if parsed:
                        with data_lock:
                            latest_data.update(parsed)
                            latest_data["connected"] = True
                            latest_data["last_updated"] = time.strftime(
                                "%Y-%m-%d %H:%M:%S"
                            )
                            latest_data["error"] = None

                        print("Arduino Data:", parsed)

        except serial.SerialException as error:
            print("Arduino connection error:", error)

            with data_lock:
                latest_data["connected"] = False
                latest_data["error"] = str(error)

            time.sleep(3)

        except Exception as error:
            print("Unexpected error:", error)

            with data_lock:
                latest_data["connected"] = False
                latest_data["error"] = str(error)

            time.sleep(3)


@app.route("/")
def home():
    return jsonify({
        "status": "success",
        "message": "Rainwater Weather Backend Running",
        "version": "2.0.0"
    })


@app.route("/api/health")
def health():
    with data_lock:
        connected = latest_data["connected"]

    return jsonify({
        "server": "online",
        "project": "Smart Rainwater Harvesting",
        "arduino": "connected" if connected else "disconnected",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    })


@app.route("/api/sensors")
def sensors():
    with data_lock:
        return jsonify(latest_data.copy())


@app.route("/api/weather")
def weather():
    """Fetch Open-Meteo weather with optional query parameters lat, lon, name."""
    lat_param = request.args.get("lat", type=float)
    lon_param = request.args.get("lon", type=float)
    name_param = request.args.get("name", type=str)

    weather_result = weather_service.get_weather(
        lat=lat_param,
        lon=lon_param,
        location_name=name_param
    )
    return jsonify(weather_result)


@app.route("/api/recommendations")
def recommendations():
    """Generate advisory scheduling recommendations combining sensors + forecast."""
    lat_param = request.args.get("lat", type=float)
    lon_param = request.args.get("lon", type=float)
    
    with data_lock:
        current_sensors = latest_data.copy()

    weather_result = weather_service.get_weather(lat=lat_param, lon=lon_param)
    recs = recommendation_engine.evaluate(current_sensors, weather_result)
    return jsonify(recs)


@app.route("/api/dashboard")
def dashboard():
    """Aggregated endpoint returning sensors, weather, and recommendations in one call."""
    lat_param = request.args.get("lat", type=float)
    lon_param = request.args.get("lon", type=float)
    name_param = request.args.get("name", type=str)

    with data_lock:
        current_sensors = latest_data.copy()

    weather_result = weather_service.get_weather(lat=lat_param, lon=lon_param, location_name=name_param)
    recs = recommendation_engine.evaluate(current_sensors, weather_result)

    return jsonify({
        "status": "success",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "sensors": current_sensors,
        "weather": weather_result,
        "recommendations": recs
    })


FRONTEND_DIST = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "dist"))

@app.route("/dashboard")
def serve_dashboard():
    """Serve the compiled React Vite production dashboard."""
    if os.path.exists(FRONTEND_DIST):
        return send_from_directory(FRONTEND_DIST, "index.html")
    return jsonify({
        "error": "Dashboard build not found",
        "message": "Run 'npm run build' inside the frontend directory"
    }), 404

@app.route("/assets/<path:path>")
def serve_dashboard_assets(path):
    """Serve compiled frontend asset bundles (JS, CSS, SVGs)."""
    assets_dir = os.path.join(FRONTEND_DIST, "assets")
    if os.path.exists(assets_dir):
        return send_from_directory(assets_dir, path)
    return "Asset not found", 404

@app.route("/vite.svg")
def serve_vite_svg():
    if os.path.exists(FRONTEND_DIST):
        return send_from_directory(FRONTEND_DIST, "vite.svg")
    return "Not found", 404


if __name__ == "__main__":
    # Start Arduino reader in background thread
    arduino_thread = threading.Thread(
        target=read_arduino,
        daemon=True
    )
    arduino_thread.start()

    # Start Flask server
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False,
        use_reloader=False
    )
