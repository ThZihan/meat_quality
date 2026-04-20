"""
PWM LED Controller Module for Meat Quality Monitoring System
Provides PWM-controlled LED illumination with graceful fallback
for non-Raspberry-Pi or environments without GPIO libraries.

Duty cycle range: 0.0 (off) to 1.0 (full brightness).
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Detect available GPIO backend
# ---------------------------------------------------------------------------
_GPIO_AVAILABLE = False
_GPIO_BACKEND: Optional[str] = None

try:
    from gpiozero import PWMLED  # type: ignore[import-untyped]
    _GPIO_AVAILABLE = True
    _GPIO_BACKEND = "gpiozero"
except ImportError:
    pass

if not _GPIO_AVAILABLE:
    try:
        import RPi.GPIO as _RPiGPIO  # type: ignore[import-untyped]
        _GPIO_AVAILABLE = True
        _GPIO_BACKEND = "rpi_gpio"
    except ImportError:
        pass

if not _GPIO_AVAILABLE:
    logger.info("No GPIO library found – LED control will be a silent no-op")


# ---------------------------------------------------------------------------
# LEDController
# ---------------------------------------------------------------------------
class LEDController:
    """
    PWM LED controller with duty-cycle range **0.0 – 1.0**.

    Falls back to a silent no-op when GPIO hardware or libraries are
    unavailable, so the rest of the application never needs to guard
    LED calls.
    """

    def __init__(self, gpio_pin: int = 18, pwm_frequency: int = 1000):
        self._gpio_pin = gpio_pin
        self._pwm_frequency = pwm_frequency
        self._duty_cycle: float = 0.0
        self._available: bool = False
        self._pwm = None  # gpiozero PWMLED *or* RPi.GPIO PWM instance

        if not _GPIO_AVAILABLE:
            logger.info("LED on GPIO %d disabled (no GPIO library)", gpio_pin)
            return

        try:
            if _GPIO_BACKEND == "gpiozero":
                self._pwm = PWMLED(gpio_pin)
                self._pwm.value = 0.0
                self._available = True
                logger.info("LED initialised on GPIO %d via gpiozero", gpio_pin)
            elif _GPIO_BACKEND == "rpi_gpio":
                _RPiGPIO.setmode(_RPiGPIO.BCM)
                _RPiGPIO.setup(gpio_pin, _RPiGPIO.OUT)
                self._pwm = _RPiGPIO.PWM(gpio_pin, pwm_frequency)
                self._pwm.start(0)
                self._available = True
                logger.info("LED initialised on GPIO %d via RPi.GPIO", gpio_pin)
        except Exception as exc:
            logger.warning(
                "LED init failed on GPIO %d: %s – LED disabled", gpio_pin, exc
            )

    # -- public properties --------------------------------------------------

    @property
    def available(self) -> bool:
        """True if a real GPIO PWM backend is active."""
        return self._available

    @property
    def duty_cycle(self) -> float:
        """Current duty cycle (0.0 – 1.0)."""
        return self._duty_cycle

    # -- core API -----------------------------------------------------------

    def set_brightness(self, duty_cycle: float) -> None:
        """Set LED brightness.

        Args:
            duty_cycle: 0.0 (off) to 1.0 (full brightness).
        """
        duty_cycle = max(0.0, min(1.0, float(duty_cycle)))
        self._duty_cycle = duty_cycle

        logger.info(
            "LED controller debug: request duty=%.2f available=%s backend=%s gpio=%d",
            duty_cycle,
            self._available,
            _GPIO_BACKEND or "none",
            self._gpio_pin,
        )

        if not self._available:
            logger.info(
                "LED controller debug: skipped hardware write for duty=%.2f because controller is unavailable",
                duty_cycle,
            )
            return

        try:
            if _GPIO_BACKEND == "gpiozero" and self._pwm is not None:
                self._pwm.value = duty_cycle
            elif _GPIO_BACKEND == "rpi_gpio" and self._pwm is not None:
                self._pwm.ChangeDutyCycle(duty_cycle * 100.0)
            logger.info(
                "LED controller debug: applied duty=%.2f via %s on GPIO %d",
                duty_cycle,
                _GPIO_BACKEND,
                self._gpio_pin,
            )
        except Exception as exc:
            logger.error("LED set_brightness error: %s", exc)

    def update(self, duty_cycle: float) -> None:
        """Update the LED duty cycle.

        This is an alias for :meth:`set_brightness` so callers can use a more
        generic update-oriented API.
        """
        self.set_brightness(duty_cycle)

    def turn_off(self) -> None:
        """Convenience: set duty cycle to 0."""
        self.set_brightness(0.0)

    def off(self) -> None:
        """Alias for :meth:`turn_off`."""
        self.turn_off()

    def turn_on(self) -> None:
        """Convenience: set duty cycle to 1."""
        self.set_brightness(1.0)

    def cleanup(self) -> None:
        """Turn off LED and release GPIO resources."""
        try:
            self.turn_off()
        except Exception:
            pass

        if self._available and self._pwm is not None:
            try:
                if _GPIO_BACKEND == "gpiozero":
                    self._pwm.close()
                elif _GPIO_BACKEND == "rpi_gpio":
                    self._pwm.stop()
                    import RPi.GPIO as GPIO  # type: ignore[import-untyped]
                    GPIO.cleanup(self._gpio_pin)
            except Exception as exc:
                logger.debug("LED cleanup note: %s", exc)

        self._available = False
        self._pwm = None
        logger.info("LED controller cleaned up")


# ---------------------------------------------------------------------------
# Module-level singleton helpers
# ---------------------------------------------------------------------------
_led_instance: Optional[LEDController] = None


def get_led_controller(
    gpio_pin: int = 18, pwm_frequency: int = 1000
) -> LEDController:
    """Return (and lazily create) the global :class:`LEDController`."""
    global _led_instance
    if _led_instance is None:
        _led_instance = LEDController(gpio_pin=gpio_pin, pwm_frequency=pwm_frequency)
    return _led_instance


def cleanup_led() -> None:
    """Tear down the global LED controller and release hardware."""
    global _led_instance
    if _led_instance is not None:
        _led_instance.cleanup()
        _led_instance = None
