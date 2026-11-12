import time
import requests
import os
from typing import Dict, Any, Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Weather Code Mapping based on WMO standards
WMO_WEATHER_CODES = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Foggy",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snow fall",
    73: "Moderate snow fall",
    75: "Heavy snow fall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail"
}

def get_weather_description(code: Optional[int]) -> str:
    if code is None:
        return "Unknown"
    return WMO_WEATHER_CODES.get(code, f"Weather code {code}")

class WeatherService:
    def __init__(
        self,
        default_lat: float = 30.9010,
        default_lon: float = 75.8573,
        default_location_name: str = "Ludhiana, Punjab, India",
        cache_duration_seconds: int = 600  # 10 minutes cache
    ):
        self.default_lat = float(os.getenv("DEFAULT_LATITUDE", default_lat))
        self.default_lon = float(os.getenv("DEFAULT_LONGITUDE", default_lon))
        self.default_location_name = os.getenv("DEFAULT_LOCATION_NAME", default_location_name)
        self.cache_duration_seconds = cache_duration_seconds
        
        # Cache keyed by (lat, lon) rounded to 2 decimals
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._last_successful_data: Optional[Dict[str, Any]] = None

    def _get_cache_key(self, lat: float, lon: float) -> str:
        return f"{lat:.2f}_{lon:.2f}"

    def get_weather(self, lat: Optional[float] = None, lon: Optional[float] = None, location_name: Optional[str] = None) -> Dict[str, Any]:
        """Fetch hourly and current weather data from Open-Meteo with caching and graceful fallbacks."""
        target_lat = lat if lat is not None else self.default_lat
        target_lon = lon if lon is not None else self.default_lon
        target_name = location_name if location_name is not None else self.default_location_name

        cache_key = self._get_cache_key(target_lat, target_lon)
        now = time.time()

        # Check cache
        if cache_key in self._cache:
            entry = self._cache[cache_key]
            if now - entry["timestamp"] < self.cache_duration_seconds:
                return entry["data"]

        # Fetch fresh data from Open-Meteo
        try:
            url = "https://api.open-meteo.com/v1/forecast"
            params = {
                "latitude": target_lat,
                "longitude": target_lon,
                "hourly": "precipitation_probability,precipitation,rain,weather_code,temperature_2m,relative_humidity_2m",
                "current": "temperature_2m,relative_humidity_2m,precipitation,weather_code,wind_speed_10m",
                "forecast_days": 2,
                "timezone": "auto"
            }
            
            response = requests.get(url, params=params, timeout=8)
            response.raise_for_status()
            raw_data = response.json()
            
            formatted_data = self._format_weather_data(raw_data, target_lat, target_lon, target_name)
            
            # Store in cache
            self._cache[cache_key] = {
                "timestamp": now,
                "data": formatted_data
            }
            self._last_successful_data = formatted_data
            
            return formatted_data

        except Exception as err:
            print(f"WeatherService error fetching forecast: {err}")
            
            # Return last successful data if available, with warning flag
            if self._last_successful_data:
                stale = dict(self._last_successful_data)
                stale["cached"] = True
                stale["warning"] = f"Network error ({str(err)}). Using cached weather."
                return stale

            # Otherwise return a safe fallback structure
            return self._build_fallback_weather(target_lat, target_lon, target_name, str(err))

    def _format_weather_data(self, raw: Dict[str, Any], lat: float, lon: float, location_name: str) -> Dict[str, Any]:
        current_raw = raw.get("current", {})
        hourly_raw = raw.get("hourly", {})
        
        hourly_times = hourly_raw.get("time", [])
        hourly_precip_prob = hourly_raw.get("precipitation_probability", [])
        hourly_precip = hourly_raw.get("precipitation", [])
        hourly_temps = hourly_raw.get("temperature_2m", [])
        hourly_codes = hourly_raw.get("weather_code", [])
        hourly_humidity = hourly_raw.get("relative_humidity_2m", [])

        # Build list of hourly entries (limit to next 24 hours for dashboard clarity)
        hourly_entries = []
        limit = min(len(hourly_times), 24)
        
        next_6h_precip = 0.0
        next_24h_precip = 0.0
        max_prob_12h = 0
        rain_expected_hours = None

        current_weather_code = current_raw.get("weather_code", 0)

        for i in range(limit):
            t = hourly_times[i]
            p_prob = hourly_precip_prob[i] if i < len(hourly_precip_prob) and hourly_precip_prob[i] is not None else 0
            precip = float(hourly_precip[i]) if i < len(hourly_precip) and hourly_precip[i] is not None else 0.0
            temp = hourly_temps[i] if i < len(hourly_temps) else None
            code = hourly_codes[i] if i < len(hourly_codes) else 0
            hum = hourly_humidity[i] if i < len(hourly_humidity) else None

            if i < 6:
                next_6h_precip += precip
            if i < 24:
                next_24h_precip += precip
            if i < 12:
                if p_prob > max_prob_12h:
                    max_prob_12h = p_prob

            # Detect first significant rain expectation (> 30% prob or precip > 0.2mm)
            if rain_expected_hours is None and (p_prob >= 35 or precip >= 0.2):
                rain_expected_hours = i

            hourly_entries.append({
                "time": t,
                "hour": t.split("T")[-1] if "T" in t else t,
                "precipitation_probability": p_prob,
                "precipitation": round(precip, 2),
                "temperature": temp,
                "weather_code": code,
                "condition": get_weather_description(code),
                "humidity": hum
            })

        return {
            "status": "success",
            "is_fallback": False,
            "last_updated": time.strftime("%Y-%m-%d %H:%M:%S"),
            "location": {
                "name": location_name,
                "latitude": lat,
                "longitude": lon,
                "timezone": raw.get("timezone", "UTC")
            },
            "current": {
                "temperature": current_raw.get("temperature_2m"),
                "humidity": current_raw.get("relative_humidity_2m"),
                "precipitation": current_raw.get("precipitation", 0.0),
                "weather_code": current_weather_code,
                "condition": get_weather_description(current_weather_code),
                "wind_speed": current_raw.get("wind_speed_10m"),
                "is_raining": (current_raw.get("precipitation", 0) > 0.1) or (current_weather_code in [51, 53, 55, 61, 63, 65, 80, 81, 82, 95, 96, 99])
            },
            "forecast_summary": {
                "next_6h_precipitation_mm": round(next_6h_precip, 2),
                "next_24h_precipitation_mm": round(next_24h_precip, 2),
                "max_rain_probability_next_12h": max_prob_12h,
                "rain_expected_within_hours": rain_expected_hours,
                "will_rain_today": (max_prob_12h >= 40 or next_24h_precip >= 1.0)
            },
            "hourly": hourly_entries
        }

    def _build_fallback_weather(self, lat: float, lon: float, location_name: str, error_message: str) -> Dict[str, Any]:
        """Provides a safe placeholder structure when network is unavailable."""
        current_hour_int = int(time.strftime("%H"))
        hourly_entries = []
        for i in range(24):
            hr = (current_hour_int + i) % 24
            hourly_entries.append({
                "time": f"{hr:02d}:00",
                "hour": f"{hr:02d}:00",
                "precipitation_probability": 0,
                "precipitation": 0.0,
                "temperature": 25.0,
                "weather_code": 1,
                "condition": "Mainly clear (Offline)",
                "humidity": 50
            })

        return {
            "status": "warning",
            "is_fallback": True,
            "error": error_message,
            "last_updated": time.strftime("%Y-%m-%d %H:%M:%S"),
            "location": {
                "name": location_name,
                "latitude": lat,
                "longitude": lon,
                "timezone": "UTC"
            },
            "current": {
                "temperature": 25.0,
                "humidity": 50,
                "precipitation": 0.0,
                "weather_code": 1,
                "condition": "Mainly clear (Offline)",
                "wind_speed": 0.0,
                "is_raining": False
            },
            "forecast_summary": {
                "next_6h_precipitation_mm": 0.0,
                "next_24h_precipitation_mm": 0.0,
                "max_rain_probability_next_12h": 0,
                "rain_expected_within_hours": None,
                "will_rain_today": False
            },
            "hourly": hourly_entries
        }

