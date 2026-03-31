"""
Mock Data Simulation Module for Meat Quality Monitoring System
Simulates realistic sensor readings for MQ136 (H2S), MQ4 (Methane), MQ135 (VOC), and DHT11 (Temp/Humidity)
Multi-Modal System: Gas Sensors + Computer Vision
"""

import random
import time
from typing import Dict, Tuple


class MeatDecaySimulator:
    """
    Simulates meat decay process with realistic sensor readings.
    
    Logic:
    - H2S (MQ136) and Methane (MQ4) trend upward over time (simulating spoilage)
    - Higher temperatures accelerate gas production
    - VOC (MQ135) shows general air quality variations
    - All values include realistic sensor noise
    """
    
    def __init__(self):
        self.start_time = time.time()
        self.time_elapsed = 0  # in seconds
        
        # Base values for fresh meat (ppm)
        self.base_h2s = 0.5  # Initial H2S level (fresh meat)
        self.base_methane = 2.0  # Initial Methane level (MQ4)
        self.base_ammonia = 1.0  # Initial Ammonia level (MQ135)
        
        # Current readings
        self.current_h2s = self.base_h2s
        self.current_methane = self.base_methane
        self.current_ammonia = self.base_ammonia
        
        # Decay rates (ppm per second at reference temp of 25°C)
        self.h2s_decay_rate = 0.005
        self.methane_decay_rate = 0.004  # Methane correlates with spoilage
        self.ammonia_decay_rate = 0.003
        
        # Temperature acceleration factor (Q10 coefficient)
        # For every 10°C increase, reaction rate doubles
        self.q10_coefficient = 2.0
        self.reference_temp = 25.0
        
    def _get_temperature_factor(self, temp_c: float) -> float:
        """
        Calculate temperature acceleration factor based on Q10 rule.
        Higher temperatures exponentially increase decay rate.
        """
        if temp_c <= 0:
            return 0.1  # Very slow decay at freezing temperatures
        
        delta_temp = temp_c - self.reference_temp
        factor = self.q10_coefficient ** (delta_temp / 10.0)
        return max(0.1, factor)  # Minimum factor to prevent zero decay
    
    def _add_noise(self, value: float, noise_percentage: float = 0.05) -> float:
        """
        Add realistic sensor noise to readings.
        """
        noise = random.uniform(-noise_percentage, noise_percentage) * value
        return max(0, value + noise)  # Ensure non-negative values
    
    def update(self, room_temp: float = 25.0, humidity: float = 60.0) -> None:
        """
        Update sensor readings based on elapsed time and environmental conditions.
        
        Args:
            room_temp: Current room temperature in Celsius
            humidity: Current humidity percentage
        """
        # Update elapsed time
        current_time = time.time()
        self.time_elapsed = current_time - self.start_time
        
        # Calculate temperature acceleration factor
        temp_factor = self._get_temperature_factor(room_temp)
        
        # Simulate gas accumulation over time with temperature correlation
        # H2S increases more rapidly as meat spoils
        h2s_increase = self.h2s_decay_rate * temp_factor * (1 + self.time_elapsed / 3600)
        self.current_h2s = self.base_h2s + (h2s_increase * self.time_elapsed)
        
        # Methane (MQ4) follows similar pattern - correlates with spoilage
        methane_increase = self.methane_decay_rate * temp_factor * (1 + self.time_elapsed / 3600)
        self.current_methane = self.base_methane + (methane_increase * self.time_elapsed)
        
        # Ammonia (MQ135) increases due to decomposition
        ammonia_increase = self.ammonia_decay_rate * temp_factor * (1 + self.time_elapsed / 7200)
        self.current_ammonia = self.base_ammonia + (ammonia_increase * self.time_elapsed)
        
        # Add realistic sensor noise
        self.current_h2s = self._add_noise(self.current_h2s, noise_percentage=0.08)
        self.current_methane = self._add_noise(self.current_methane, noise_percentage=0.06)
        self.current_ammonia = self._add_noise(self.current_ammonia, noise_percentage=0.05)
        
        # Temperature and humidity also have slight fluctuations
        self.current_temp = room_temp + random.uniform(-0.5, 0.5)
        self.current_humidity = humidity + random.uniform(-2, 2)
        
        # Clamp humidity to valid range
        self.current_humidity = max(0, min(100, self.current_humidity))
    
    def get_readings(self, room_temp: float = 25.0, humidity: float = 60.0) -> Dict[str, float]:
        """
        Get current sensor readings.
        
        Returns:
            Dictionary with keys: h2s_ppm, methane_ppm, ammonia_ppm, temp_c, humidity
        """
        self.update(room_temp, humidity)
        
        return {
            'h2s_ppm': round(self.current_h2s, 2),
            'methane_ppm': round(self.current_methane, 2),
            'ammonia_ppm': round(self.current_ammonia, 2),
            'temp_c': round(self.current_temp, 1),
            'humidity': round(self.current_humidity, 1)
        }
    
    def reset(self) -> None:
        """Reset the simulation to initial state."""
        self.start_time = time.time()
        self.time_elapsed = 0
        self.current_h2s = self.base_h2s
        self.current_methane = self.base_methane
        self.current_ammonia = self.base_ammonia


# Singleton instance for the application
_simulator = MeatDecaySimulator()


def get_readings(room_temp: float = 25.0, humidity: float = 60.0) -> Dict[str, float]:
    """
    Get current sensor readings from the global simulator instance.
    
    Args:
        room_temp: Current room temperature in Celsius
        humidity: Current humidity percentage
    
    Returns:
        Dictionary with keys: h2s_ppm, methane_ppm, ammonia_ppm, temp_c, humidity
    """
    return _simulator.get_readings(room_temp, humidity)


def reset_simulation() -> None:
    """Reset the global simulation to initial state."""
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
    
    Args:
        image: Input image (not used in simulation, but kept for interface compatibility)
    
    Returns:
        Dictionary with:
        - species: "Beef" or "Mutton"
        - visual_status: "Fresh" or "Rotten"
        - confidence: Confidence score as percentage string (e.g., "99.2%")
        - confidence_float: Confidence as float for calculations
    """
    # Random species selection
    species = random.choice(["Beef", "Mutton"])
    
    # Visual status based on elapsed time (longer time = more likely rotten)
    elapsed = get_time_elapsed()
    rotten_probability = min(0.95, elapsed / 3600)  # Increases over time, max 95%
    visual_status = "Rotten" if random.random() < rotten_probability else "Fresh"
    
    # High confidence score (95-99.9%) to match research paper accuracy
    confidence_float = random.uniform(95.0, 99.9)
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
