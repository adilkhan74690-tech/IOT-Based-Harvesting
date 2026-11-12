from typing import Dict, Any, List, Optional

class RecommendationEngine:
    """
    Intelligent Adaptive Weather Scheduling Engine for Rainwater Harvesting.
    Evaluates live hardware sensor readings combined with Open-Meteo forecasts
    to calculate tank overflow risks and generate actionable operational recommendations.
    
    IMPORTANT: All recommendations are strictly advisory. No hardware control commands
    are issued automatically.
    """

    def __init__(self, tank_capacity_liters: float = 500.0, catchment_area_sqm: float = 25.0, runoff_coeff: float = 0.85):
        """
        :param tank_capacity_liters: Nominal storage tank volume in liters
        :param catchment_area_sqm: Roof/catchment area in square meters
        :param runoff_coeff: Runoff coefficient (typically 0.8 to 0.9 for metal/tile roofs)
        """
        self.tank_capacity_liters = tank_capacity_liters
        self.catchment_area_sqm = catchment_area_sqm
        self.runoff_coeff = runoff_coeff

    def calculate_inflow_liters(self, rainfall_mm: float) -> float:
        """Estimate rainwater collection volume: Inflow (L) = Rain (mm) * Area (m^2) * Runoff Coefficient"""
        if rainfall_mm <= 0:
            return 0.0
        return round(rainfall_mm * self.catchment_area_sqm * self.runoff_coeff, 1)

    def evaluate(self, sensor_data: Dict[str, Any], weather_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate comprehensive scheduling recommendations based on sensor state and weather forecast."""
        
        # Extract sensor metrics safely
        tank_level = sensor_data.get("level")
        if tank_level is None:
            tank_level = 0
        else:
            tank_level = max(0, min(100, int(tank_level)))

        distance_cm = sensor_data.get("distance")
        rain_raw = sensor_data.get("rain_raw", 1023)
        hardware_raining = bool(sensor_data.get("raining", False)) or (rain_raw is not None and rain_raw < 500)
        hardware_full = bool(sensor_data.get("full", False)) or (tank_level >= 90)
        lid_status = sensor_data.get("lid", "UNKNOWN")
        pump_status = sensor_data.get("pump", "UNKNOWN")

        # Extract weather metrics safely
        forecast_summary = weather_data.get("forecast_summary", {})
        next_6h_precip = forecast_summary.get("next_6h_precipitation_mm", 0.0)
        next_24h_precip = forecast_summary.get("next_24h_precipitation_mm", 0.0)
        max_prob_12h = forecast_summary.get("max_rain_probability_next_12h", 0)
        rain_expected_hours = forecast_summary.get("rain_expected_within_hours")
        will_rain_today = forecast_summary.get("will_rain_today", False)
        
        current_weather = weather_data.get("current", {})
        weather_raining = current_weather.get("is_raining", False)
        current_precip = current_weather.get("precipitation", 0.0)

        # Derived calculations
        headroom_percent = max(0, 100 - tank_level)
        available_headroom_liters = round((headroom_percent / 100.0) * self.tank_capacity_liters, 1)
        estimated_inflow_6h = self.calculate_inflow_liters(next_6h_precip)
        estimated_inflow_24h = self.calculate_inflow_liters(next_24h_precip)

        # Inflow percentage of tank capacity
        inflow_headroom_ratio_6h = (estimated_inflow_6h / available_headroom_liters) if available_headroom_liters > 0 else 999.0

        # Assess precipitation urgency
        is_currently_raining = hardware_raining or weather_raining or current_precip > 0.2
        rain_imminent = is_currently_raining or (rain_expected_hours is not None and rain_expected_hours <= 3 and max_prob_12h >= 45)
        rain_expected_today = will_rain_today or max_prob_12h >= 40 or next_24h_precip >= 1.0

        # Overflow Risk Evaluation & Risk Score (0 - 100)
        risk_score = 0
        
        # Base on level
        if tank_level >= 90:
            risk_score += 50
        elif tank_level >= 75:
            risk_score += 35
        elif tank_level >= 50:
            risk_score += 15

        # Factor in active rain
        if is_currently_raining:
            risk_score += 40
        elif rain_imminent:
            risk_score += 30
        elif rain_expected_today:
            risk_score += 15

        # Factor in precipitation volume
        if next_6h_precip >= 15.0 or inflow_headroom_ratio_6h > 1.0:
            risk_score += 20
        elif next_6h_precip >= 5.0 or inflow_headroom_ratio_6h > 0.6:
            risk_score += 10

        risk_score = min(100, max(0, risk_score))

        # Risk Classification
        if risk_score >= 80 or (tank_level >= 90 and (is_currently_raining or rain_imminent)):
            overflow_risk = "CRITICAL"
            risk_color = "red"
        elif risk_score >= 55 or (tank_level >= 75 and rain_expected_today):
            overflow_risk = "HIGH"
            risk_color = "orange"
        elif risk_score >= 35 or (tank_level >= 50 and rain_expected_today):
            overflow_risk = "MODERATE"
            risk_color = "yellow"
        elif risk_score >= 15:
            overflow_risk = "LOW"
            risk_color = "blue"
        else:
            overflow_risk = "MINIMAL"
            risk_color = "emerald"

        # Action Code & Recommendations formulation
        advisories: List[Dict[str, str]] = []
        action_code = "MONITOR"
        headline = "System Nominal: Weather & Storage Monitored"

        # Decision Matrix
        if hardware_full or tank_level >= 90:
            if is_currently_raining:
                action_code = "OVERFLOW_ALERT"
                headline = "Tank at Maximum Capacity: Active Rain Detected"
                advisories.append({
                    "type": "danger",
                    "title": "Tank Fully Loaded with Active Rain",
                    "detail": f"Current tank level is {tank_level}%. Overflow spillway is actively engaged. Divert inflow or utilize excess water for secondary purposes."
                })
            elif rain_imminent:
                action_code = "PREPARE_OVERFLOW"
                headline = "Tank Nearly Full: Rain Expected Soon"
                advisories.append({
                    "type": "warning",
                    "title": "Tank Nearly Full Ahead of Rain",
                    "detail": f"Tank is at {tank_level}% with rainfall anticipated in ~{rain_expected_hours or 1} hours. Consider pre-emptive water transfer to secondary storage."
                })
            else:
                action_code = "CHECK_CAPACITY"
                headline = "Tank Nearly Full: Check Available Capacity"
                advisories.append({
                    "type": "info",
                    "title": "Storage Capacity Peak",
                    "detail": f"Tank at {tank_level}%. No immediate heavy rainfall forecast. Storage is primed for maximum retention."
                })

        elif tank_level >= 70:
            if rain_imminent or (next_6h_precip >= 5.0 and max_prob_12h >= 50):
                action_code = "PREPARE_RAIN"
                headline = "Prepare for Rainfall: Elevated Overflow Risk"
                advisories.append({
                    "type": "warning",
                    "title": "High Inflow Expected on High Tank Level",
                    "detail": f"Expected rainfall of {next_6h_precip}mm in next 6h will generate approx ~{estimated_inflow_6h}L. Available headroom is {available_headroom_liters}L."
                })
            elif rain_expected_today:
                action_code = "CHECK_CAPACITY"
                headline = "Check Available Storage Capacity"
                advisories.append({
                    "type": "info",
                    "title": "Moderate Rain Inbound Today",
                    "detail": f"Peak rain probability {max_prob_12h}%. Current headroom is {headroom_percent}% ({available_headroom_liters}L)."
                })
            else:
                action_code = "CONSERVE"
                headline = "Low Rainfall Probability: Good Storage Reserves"
                advisories.append({
                    "type": "success",
                    "title": "Healthy Stored Volume",
                    "detail": f"Rainfall unlikely in next 24h. Tank is {tank_level}% full; suitable for regular non-potable distribution."
                })

        elif tank_level < 35:
            if rain_imminent:
                action_code = "HARVEST_OPTIMAL"
                headline = "Prepare for Rainfall: Ideal Harvesting Window"
                advisories.append({
                    "type": "success",
                    "title": "High Storage Capacity Ready for Collection",
                    "detail": f"Tank has {headroom_percent}% ({available_headroom_liters}L) headroom. Rain expected in ~{rain_expected_hours or 1} hours. Ensure intake filters are clear."
                })
            elif rain_expected_today:
                action_code = "HARVEST_READY"
                headline = "Rain Expected Soon: Recharging Storage"
                advisories.append({
                    "type": "info",
                    "title": "Recharge Opportunity Today",
                    "detail": f"{next_24h_precip}mm rainfall expected ({max_prob_12h}% chance). Projected harvest: ~{estimated_inflow_24h}L."
                })
            else:
                action_code = "CONSERVE"
                headline = "Low Rainfall Probability: Conserve Storage"
                advisories.append({
                    "type": "warning",
                    "title": "Dry Weather Ahead & Low Tank Reserve",
                    "detail": f"Tank level is low ({tank_level}%) and no significant rain forecast. Conserve stored water."
                })

        else: # Moderate level 35% - 70%
            if rain_imminent:
                action_code = "PREPARE_RAIN"
                headline = "Rain Expected Soon: Ready for Collection"
                advisories.append({
                    "type": "info",
                    "title": "Inflow Imminent",
                    "detail": f"Rain probability {max_prob_12h}%. Tank can comfortably accept ~{available_headroom_liters}L without overflow."
                })
            elif rain_expected_today:
                action_code = "HARVEST_READY"
                headline = "Rain Expected Today: Stable Harvesting Capacity"
                advisories.append({
                    "type": "info",
                    "title": "Rain Forecast Within 24h",
                    "detail": f"Expected rain {next_24h_precip}mm. Available capacity is {available_headroom_liters}L."
                })
            else:
                action_code = "MONITOR"
                headline = "Low Rainfall Probability: Weather Dry"
                advisories.append({
                    "type": "info",
                    "title": "Standard Conservation Mode",
                    "detail": "Weather remains clear. Tank holding steady with nominal storage."
                })

        # Add hardware diagnostic note if needed
        if hardware_raining and not weather_raining:
            advisories.append({
                "type": "info",
                "title": "Localized Shower Detected",
                "detail": "Hardware rain sensor has triggered even though macro weather forecast does not show major regional precipitation."
            })

        return {
            "status": "success",
            "advisory_mode": True,
            "actuation_locked": True,
            "disclaimer": "Advisory only. Automatic hardware pump/servo actuation is disabled.",
            "overflow_risk": overflow_risk,
            "overflow_risk_score": risk_score,
            "overflow_risk_color": risk_color,
            "headline": headline,
            "action_code": action_code,
            "metrics": {
                "tank_level_percent": tank_level,
                "storage_headroom_percent": headroom_percent,
                "available_headroom_liters": available_headroom_liters,
                "estimated_inflow_6h_liters": estimated_inflow_6h,
                "estimated_inflow_24h_liters": estimated_inflow_24h,
                "max_rain_probability_12h": max_prob_12h,
                "rain_expected_hours": rain_expected_hours,
                "is_currently_raining": is_currently_raining
            },
            "advisories": advisories
        }

