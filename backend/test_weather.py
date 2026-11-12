import unittest
from weather_service import WeatherService, get_weather_description

class TestWeatherService(unittest.TestCase):
    def setUp(self):
        self.service = WeatherService()

    def test_live_weather_fetch(self):
        weather = self.service.get_weather()
        self.assertIn(weather["status"], ["success", "warning"])
        self.assertIn("current", weather)
        self.assertIn("forecast_summary", weather)
        self.assertIn("hourly", weather)
        self.assertEqual(weather["location"]["name"], "Ludhiana, Punjab, India")
        self.assertAlmostEqual(weather["location"]["latitude"], 30.9010, places=1)
        self.assertAlmostEqual(weather["location"]["longitude"], 75.8573, places=1)
        
        # Verify hourly fields
        self.assertGreater(len(weather["hourly"]), 0)
        first_hour = weather["hourly"][0]
        self.assertIn("precipitation_probability", first_hour)
        self.assertIn("precipitation", first_hour)
        self.assertIn("temperature", first_hour)
        self.assertIn("condition", first_hour)

    def test_weather_caching(self):
        # First call populates cache
        w1 = self.service.get_weather()
        t1 = w1.get("last_updated")
        
        # Second immediate call should hit cache
        w2 = self.service.get_weather()
        self.assertEqual(w1["location"]["name"], w2["location"]["name"])
        self.assertEqual(t1, w2.get("last_updated"))

    def test_fallback_structure(self):
        # Force fallback by providing dummy service with non-existent URL or mocking
        fallback = self.service._build_fallback_weather(10.0, 20.0, "Test City", "Simulated error")
        self.assertTrue(fallback["is_fallback"])
        self.assertEqual(fallback["location"]["name"], "Test City")
        self.assertEqual(len(fallback["hourly"]), 24)
        self.assertIn("rain_expected_within_hours", fallback["forecast_summary"])

    def test_wmo_code_description(self):
        self.assertEqual(get_weather_description(0), "Clear sky")
        self.assertEqual(get_weather_description(65), "Heavy rain")
        self.assertEqual(get_weather_description(95), "Thunderstorm")
        self.assertEqual(get_weather_description(None), "Unknown")

if __name__ == "__main__":
    unittest.main()

