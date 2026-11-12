import unittest
from recommendation_engine import RecommendationEngine

class TestRecommendationEngine(unittest.TestCase):
    def setUp(self):
        self.engine = RecommendationEngine(tank_capacity_liters=1000.0, catchment_area_sqm=50.0)

    def test_high_tank_imminent_rain_critical_risk(self):
        sensor_data = {
            "level": 92,
            "distance": 5.2,
            "raining": True,
            "rain_raw": 320,
            "full": True,
            "lid": "CLOSED",
            "pump": "OFF",
            "led": "BLUE"
        }
        weather_data = {
            "current": {"is_raining": True, "precipitation": 3.5},
            "forecast_summary": {
                "next_6h_precipitation_mm": 15.0,
                "next_24h_precipitation_mm": 35.0,
                "max_rain_probability_next_12h": 90,
                "rain_expected_within_hours": 0,
                "will_rain_today": True
            }
        }
        rec = self.engine.evaluate(sensor_data, weather_data)
        self.assertEqual(rec["overflow_risk"], "CRITICAL")
        self.assertTrue(rec["advisory_mode"])
        self.assertTrue(rec["actuation_locked"])
        self.assertIn("Tank at Maximum Capacity", rec["headline"])
        self.assertGreater(rec["overflow_risk_score"], 70)

    def test_low_tank_rain_expected_optimal_harvest(self):
        sensor_data = {
            "level": 20,
            "distance": 35.0,
            "raining": False,
            "rain_raw": 1022,
            "full": False,
            "lid": "CLOSED",
            "pump": "OFF",
            "led": "YELLOW"
        }
        weather_data = {
            "current": {"is_raining": False, "precipitation": 0.0},
            "forecast_summary": {
                "next_6h_precipitation_mm": 6.0,
                "next_24h_precipitation_mm": 12.0,
                "max_rain_probability_next_12h": 70,
                "rain_expected_within_hours": 2,
                "will_rain_today": True
            }
        }
        rec = self.engine.evaluate(sensor_data, weather_data)
        self.assertIn(rec["overflow_risk"], ["LOW", "MODERATE", "MINIMAL"])
        self.assertEqual(rec["action_code"], "HARVEST_OPTIMAL")
        self.assertIn("Prepare for Rainfall", rec["headline"])
        self.assertEqual(rec["metrics"]["storage_headroom_percent"], 80)

    def test_low_tank_dry_weather_conserve(self):
        sensor_data = {
            "level": 15,
            "distance": 40.0,
            "raining": False,
            "rain_raw": 1023,
            "full": False,
            "lid": "CLOSED",
            "pump": "OFF",
            "led": "RED"
        }
        weather_data = {
            "current": {"is_raining": False, "precipitation": 0.0},
            "forecast_summary": {
                "next_6h_precipitation_mm": 0.0,
                "next_24h_precipitation_mm": 0.0,
                "max_rain_probability_next_12h": 5,
                "rain_expected_within_hours": None,
                "will_rain_today": False
            }
        }
        rec = self.engine.evaluate(sensor_data, weather_data)
        self.assertEqual(rec["overflow_risk"], "MINIMAL")
        self.assertEqual(rec["action_code"], "CONSERVE")
        self.assertIn("Low Rainfall Probability", rec["headline"])

    def test_advisory_safety_constraint(self):
        # Guarantee no control commands ever returned
        sensor_data = {"level": 85, "raining": False}
        weather_data = {"forecast_summary": {}}
        rec = self.engine.evaluate(sensor_data, weather_data)
        self.assertTrue(rec["advisory_mode"])
        self.assertTrue(rec["actuation_locked"])
        self.assertNotIn("pump_command", rec)
        self.assertNotIn("servo_command", rec)

if __name__ == "__main__":
    unittest.main()

