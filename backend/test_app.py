import unittest
import json
from app import app, parse_arduino_data, latest_data, data_lock

class TestFlaskEndpoints(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_home(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["status"], "success")

    def test_health(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["server"], "online")
        self.assertIn("arduino", data)

    def test_sensors(self):
        response = self.client.get("/api/sensors")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("connected", data)
        self.assertIn("level", data)
        self.assertIn("distance", data)
        self.assertIn("rain_raw", data)
        self.assertIn("lid", data)
        self.assertIn("pump", data)
        self.assertIn("led", data)

    def test_weather(self):
        response = self.client.get("/api/weather")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn(data["status"], ["success", "warning"])
        self.assertIn("current", data)
        self.assertIn("hourly", data)
        self.assertEqual(data["location"]["name"], "Ludhiana, Punjab, India")
        self.assertAlmostEqual(data["location"]["latitude"], 30.9010, places=1)
        self.assertAlmostEqual(data["location"]["longitude"], 75.8573, places=1)

    def test_recommendations(self):
        response = self.client.get("/api/recommendations")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("overflow_risk", data)
        self.assertIn("headline", data)
        self.assertTrue(data["advisory_mode"])
        self.assertTrue(data["actuation_locked"])

    def test_dashboard_aggregated(self):
        response = self.client.get("/api/dashboard")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["status"], "success")
        self.assertIn("sensors", data)
        self.assertIn("weather", data)
        self.assertIn("recommendations", data)
        self.assertEqual(data["weather"]["location"]["name"], "Ludhiana, Punjab, India")

    def test_serve_dashboard_page(self):
        response = self.client.get("/dashboard")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"<!doctype html>", response.data.lower())

    def test_parse_arduino_data(self):
        line = "Time: 4s | Dist: 6.9 cm | Level: 85% | Rain raw: 1022 (DRY) | Full: YES | Lid: CLOSED | Pump: OFF | LED: BLUE"
        parsed = parse_arduino_data(line)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["time"], 4)
        self.assertEqual(parsed["distance"], 6.9)
        self.assertEqual(parsed["level"], 85)
        self.assertEqual(parsed["rain_raw"], 1022)
        self.assertFalse(parsed["raining"])
        self.assertTrue(parsed["full"])
        self.assertEqual(parsed["lid"], "CLOSED")
        self.assertEqual(parsed["pump"], "OFF")
        self.assertEqual(parsed["led"], "BLUE")

if __name__ == "__main__":
    unittest.main()

