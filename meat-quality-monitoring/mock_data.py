"""
Mock Data Simulation Module for Meat Quality Monitoring System
Simulates realistic sensor readings for MQ136 (H2S), MQ137 (NH3), MQ135 (VOC),
and AHT10 (Temp/Humidity).

The values produced here are tuned against the thresholds defined in config.py so
that the dashboard colour/status indicators actually respond:

    H2S (MQ136): 0-100 ppm   (fresh < 10,  warning 10-50,  critical > 50)
    NH3 (MQ137): 0-200 ppm   (fresh < 25,  warning 25-100, critical > 100)
    VOC (MQ135): 0-1200 ppm  (fresh < 600, warning 600-1000, critical > 1000)

Behaviour:
  - The fresh-meat baseline is randomised on every start/reset, so no two runs
    look identical.
  - A temperature-dependent upward drift (Q10 rule) models spoilage, pushing the
    readings toward warning / critical bands over time.
  - Each sample adds realistic Gaussian sensor noise + jitter, so the live charts
    look like genuine sensor output rather than a straight diagonal line.
"""

import random
import time
from typing import Dict, Tuple


# Physical measurement ceilings for each gas sensor (ppm).
H2S_MAX = 100.0   # MQ136
NH3_MAX = 200.0   # MQ137
VOC_MAX = 1200.0  # MQ135


def _clamp(value: float, low: float, high: float) -> float:
    """Clamp ``value`` into the inclusive ``[low, high]`` range."""
    return max(low, min(high, value))


class MeatDecaySimulator:
    """
    Simulates meat decay with realistic, noisy sensor readings.

    Logic:
      - Baseline starts randomised within the "fresh" band for each gas.
      - A Q10 temperature factor accelerates decay (rate ~doubles every +10C).
      - A slow autocatalytic time boost makes the curve steepen as meat spoils.
      - Realistic Gaussian noise is added on every tick.
    """

    def __init__(self):
        self.start_time = time.time()
        self.time_elapsed = 0.0  # seconds since the simulation started

        # ---- Randomised fresh-meat baseline (inside "fresh" thresholds) ----
        self.base_h2s = random.uniform(1.0, 7.0)      # fresh: < 10
        self.base_nh3 = random.uniform(5.0, 20.0)     # fresh: < 25
        self.base_voc = random.uniform(350.0, 560.0)  # fresh: < 600

        # Current readings (start at the randomised baseline)
        self.current_h2s = self.base_h2s
        self.current_nh3 = self.base_nh3
        self.current_voc = self.base_voc

        # ---- Per-tick spoilage drift (ppm per refresh) at the reference temp ----
        # Tuned so the simulation visibly progresses over a few minutes.
        self.h2s_drift = random.uniform(0.08, 0.18)
        self.nh3_drift = random.uniform(0.25, 0.45)
        self.voc_drift = random.uniform(1.5, 3.0)

        # Q10 temperature acceleration: reaction rate ~doubles every +10C.
        self.q10_coefficient = 2.0
        self.reference_temp = 25.0  # baseline room temperature (slider default)

        # Sensor noise amplitudes (std-dev of the Gaussian jitter per reading).
        self.h2s_noise = 0.25
        self.nh3_noise = 0.6
        self.voc_noise = 8.0

        # Environmental readings
        self.current_temp = self.reference_temp
        self.current_humidity = 70.0

    def _get_temperature_factor(self, temp_c: float) -> float:
        """
        Calculate temperature acceleration factor based on the Q10 rule.
        Higher temperatures exponentially increase the decay/gas-production rate.
        """
        if temp_c <= 0:
            return 0.15  # near-freezing: decay almost stalls
        delta_temp = temp_c - self.reference_temp
        factor = self.q10_coefficient ** (delta_temp / 10.0)
        return max(0.15, factor)

    def update(self, room_temp: float = 25.0, humidity: float = 60.0) -> None:
        """
        Advance the simulation one tick based on elapsed time and environment.

        Args:
            room_temp: Current room/ambient temperature in Celsius.
            humidity:  Current humidity percentage.
        """
        self.time_elapsed = time.time() - self.start_time

        temp_factor = self._get_temperature_factor(room_temp)

        # Autocatalytic boost: decay accelerates slightly as the meat spoils
        # (bacterial growth is exponential). Divisor scales the timeline.
        time_boost = 1.0 + self.time_elapsed / 900.0

        # Random-walk drift upward, scaled by temperature and time.
        # The Gaussian component makes individual readings dip occasionally,
        # which looks like genuine sensor jitter.
        self.current_h2s += random.gauss(self.h2s_drift * temp_factor * time_boost, self.h2s_noise)
        self.current_nh3 += random.gauss(self.nh3_drift * temp_factor * time_boost, self.nh3_noise)
        self.current_voc += random.gauss(self.voc_drift * temp_factor * time_boost, self.voc_noise)

        # Clamp to physical sensor measurement ranges
        self.current_h2s = _clamp(self.current_h2s, 0.0, H2S_MAX)
        self.current_nh3 = _clamp(self.current_nh3, 0.0, NH3_MAX)
        self.current_voc = _clamp(self.current_voc, 0.0, VOC_MAX)

        # Realistic environmental fluctuations around the slider values
        self.current_temp = room_temp + random.gauss(0.0, 0.3)
        self.current_humidity = _clamp(humidity + random.gauss(0.0, 1.5), 0.0, 100.0)

    def get_readings(self, room_temp: float = 25.0, humidity: float = 60.0) -> Dict[str, float]:
        """
        Advance the simulation and return the latest sensor readings.

        Returns:
            Dictionary with keys: h2s_ppm, nh3_ppm, voc_ppm, temp_c, humidity
            (plus ammonia_ppm / methane_ppm aliases for backward compatibility).
        """
        self.update(room_temp, humidity)

        return {
            'h2s_ppm': round(self.current_h2s, 2),
            'nh3_ppm': round(self.current_nh3, 2),
            'voc_ppm': round(self.current_voc, 2),
            # Backward-compatible aliases used by older code paths
            'ammonia_ppm': round(self.current_nh3, 2),
            'methane_ppm': round(self.current_voc, 2),
            'temp_c': round(self.current_temp, 1),
            'humidity': round(self.current_humidity, 1),
        }

    def reset(self) -> None:
        """Reset the simulation with a fresh randomised baseline."""
        self.__init__()


# Singleton instance for the application
_simulator = MeatDecaySimulator()


def get_readings(room_temp: float = 25.0, humidity: float = 60.0) -> Dict[str, float]:
    """
    Get current sensor readings from the global simulator instance.

    Args:
        room_temp: Current room temperature in Celsius
        humidity: Current humidity percentage

    Returns:
        Dictionary with keys: h2s_ppm, nh3_ppm, voc_ppm, temp_c, humidity
    """
    return _simulator.get_readings(room_temp, humidity)


def reset_simulation() -> None:
    """Reset the global simulation to a fresh randomised state."""
    _simulator.reset()


def get_time_elapsed() -> float:
    """Get the elapsed time since simulation started (in seconds)."""
    return _simulator.time_elapsed


def predict_image(image=None) -> Dict[str, any]:
    """
    Mock Custom CNN prediction function for meat quality classification.

    Simulates a deep learning model that:
    1. Classifies meat species (Beef/Mutton)
    2. Detects visual spoilage (Fresh/Rotten)
    3. Provides confidence scores

    The result is randomised so each prediction differs, and the probability of
    a "Rotten" verdict grows with elapsed time (matching the gas decay curve).

    Args:
        image: Input image (not used in simulation, kept for interface parity)

    Returns:
        Dictionary with:
        - species: "Beef" or "Mutton"
        - visual_status: "Fresh" or "Rotten"
        - confidence: Confidence score as percentage string (e.g., "99.2%")
        - confidence_float: Confidence as float for calculations
    """
    # Weighted species selection (beef is the more common test sample)
    species = random.choices(["Beef", "Mutton"], weights=[0.7, 0.3])[0]

    # Visual spoilage probability grows with elapsed time (caps at 95%)
    elapsed = get_time_elapsed()
    rotten_probability = min(0.95, elapsed / 3600.0)
    visual_status = "Rotten" if random.random() < rotten_probability else "Fresh"

    # Realistic high-confidence score (94.0-99.9%) matching research-paper accuracy
    confidence_float = random.uniform(94.0, 99.9)
    confidence = f"{confidence_float:.1f}%"

    return {
        'species': species,
        'visual_status': visual_status,
        'confidence': confidence,
        'confidence_float': confidence_float
    }


def get_fusion_decision(visual_result: str, gas_readings: Dict[str, float]) -> Tuple[str, str]:
    """
    Perform fusion analysis combining visual and gas sensor data.

    Args:
        visual_result: "Fresh" or "Rotten" from CNN prediction
        gas_readings: Dictionary with gas sensor readings

    Returns:
        Tuple of (status, color) where status is one of:
        - "SAFE" (Green)
        - "WARNING" (Orange/Yellow)
        - "SPOILED" (Red)
        - "CRITICAL" (Dark Red)
    """
    h2s = gas_readings.get('h2s_ppm', 0)
    methane = gas_readings.get('methane_ppm', 0)

    # Define gas thresholds
    H2S_WARNING = 10
    H2S_CRITICAL = 50
    METHANE_WARNING = 25
    METHANE_CRITICAL = 100

    # Determine gas status
    gas_critical = h2s >= H2S_CRITICAL or methane >= METHANE_CRITICAL
    gas_warning = h2s >= H2S_WARNING or methane >= METHANE_WARNING
    gas_low = not gas_warning

    # Fusion logic
    if visual_result == "Rotten" or gas_critical:
        return "CRITICAL", "#8B0000"  # Dark Red
    elif visual_result == "Fresh" and gas_low:
        return "SAFE", "#00AA00"  # Green
    elif visual_result == "Fresh" and gas_warning:
        return "WARNING", "#FF9800"  # Orange
    elif visual_result == "Rotten" and gas_low:
        return "SPOILED", "#FF0000"  # Red
    else:
        return "WARNING", "#FFC107"  # Yellow
