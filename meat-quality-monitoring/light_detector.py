"""
Light Detection & PWM Mapping Module for Meat Quality Monitoring System

Provides:
- Brightness analysis of image frames (numpy/OpenCV or raw JPEG bytes).
- Shared brightness-to-PWM mapping with hysteresis and throttling
  to reduce LED flicker.

Both the continuous live-feed monitor and the final capture workflow
use the same :func:`brightness_to_pwm` function so that mapping
logic is never duplicated.
"""

import io
import logging
import time
from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

_opencv_fallback_logged = False

# ---------------------------------------------------------------------------
# Default tunables (can be overridden via LightDetectorConfig)
# ---------------------------------------------------------------------------
DEFAULT_DARK_THRESHOLD: float = 115.0
DEFAULT_BRIGHT_THRESHOLD: float = 120.0
DEFAULT_MIN_PWM: float = 0.0
DEFAULT_MAX_PWM: float = 1.0
DEFAULT_THROTTLE_INTERVAL: float = 0.5  # seconds between PWM updates
DEFAULT_PWM_STEP: float = 0.05  # maximum duty-cycle change per update


# ---------------------------------------------------------------------------
# Configuration dataclass
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class LightDetectorConfig:
    """Tunable parameters for light detection and PWM mapping.

    Attributes:
        dark_threshold: Mean brightness below this → scene is dark.
        bright_threshold: Mean brightness above this → scene is well-lit.
        min_pwm: Minimum PWM duty cycle when LED is on.
        max_pwm: Maximum PWM duty cycle (1.0 = full).
        throttle_interval: Minimum seconds between consecutive PWM changes.
        pwm_step: Maximum duty-cycle delta per update (anti-flicker).
    """

    dark_threshold: float = DEFAULT_DARK_THRESHOLD
    bright_threshold: float = DEFAULT_BRIGHT_THRESHOLD
    min_pwm: float = DEFAULT_MIN_PWM
    max_pwm: float = DEFAULT_MAX_PWM
    throttle_interval: float = DEFAULT_THROTTLE_INTERVAL
    pwm_step: float = DEFAULT_PWM_STEP

    def __post_init__(self) -> None:
        if not 0 <= self.dark_threshold <= 255:
            raise ValueError(f"dark_threshold must be 0-255, got {self.dark_threshold}")
        if not 0 <= self.bright_threshold <= 255:
            raise ValueError(f"bright_threshold must be 0-255, got {self.bright_threshold}")
        if self.dark_threshold >= self.bright_threshold:
            raise ValueError(
                f"dark_threshold ({self.dark_threshold}) must be < bright_threshold ({self.bright_threshold})"
            )
        if not 0.0 <= self.min_pwm <= 1.0:
            raise ValueError(f"min_pwm must be 0.0-1.0, got {self.min_pwm}")
        if not 0.0 <= self.max_pwm <= 1.0:
            raise ValueError(f"max_pwm must be 0.0-1.0, got {self.max_pwm}")
        if self.min_pwm > self.max_pwm:
            raise ValueError(f"min_pwm ({self.min_pwm}) must be <= max_pwm ({self.max_pwm})")


# ---------------------------------------------------------------------------
# Brightness analysis
# ---------------------------------------------------------------------------

def analyze_brightness(frame: np.ndarray) -> float:
    """Compute mean brightness of an image frame.

    Accepts either a **BGR** (OpenCV) or **grayscale** numpy array.
    For colour images the green channel is used (perceptually closest to
    human brightness perception) with a fast scalar fallback.

    Args:
        frame: Image as numpy array (HxWxC or HxW, dtype uint8).

    Returns:
        Mean brightness in the range 0.0 – 255.0.
    """
    if frame is None or frame.size == 0:
        return 255.0  # assume bright if no data

    try:
        if frame.ndim == 2:
            # Already grayscale
            return float(np.mean(frame))
        elif frame.ndim == 3:
            # Convert BGR to grayscale via luminance formula
            # OpenCV loads as BGR; use standard weights
            gray = np.dot(frame[..., :3].astype(np.float32), [0.114, 0.587, 0.299])
            return float(np.mean(gray))
        else:
            return float(np.mean(frame))
    except Exception as exc:
        logger.warning("Brightness analysis error: %s", exc)
        return 255.0


def analyze_brightness_from_jpeg(jpeg_bytes: bytes) -> float:
    """Analyse brightness from raw JPEG bytes.

    Uses OpenCV if available; otherwise falls back to Pillow decoding before
    using a last-resort statistical estimate on the raw JPEG byte values.

    Args:
        jpeg_bytes: JPEG-encoded image bytes.

    Returns:
        Mean brightness (0.0 – 255.0).
    """
    global _opencv_fallback_logged

    if not jpeg_bytes or len(jpeg_bytes) < 100:
        logger.info(
            "Light detector debug: invalid jpeg payload len=%d -> assuming bright scene",
            0 if not jpeg_bytes else len(jpeg_bytes),
        )
        return 255.0

    try:
        import cv2
        arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
        if frame is not None:
            brightness = float(np.mean(frame))
            logger.info(
                "Light detector debug: method=cv2 jpeg_len=%d brightness=%.1f",
                len(jpeg_bytes),
                brightness,
            )
            return brightness
    except ImportError:
        if not _opencv_fallback_logged:
            logger.warning(
                "Light detector debug: OpenCV unavailable; falling back to Pillow JPEG decoding."
            )
            _opencv_fallback_logged = True
    except Exception as exc:
        logger.debug("OpenCV decode failed, trying alternate decoder: %s", exc)

    try:
        from PIL import Image

        with Image.open(io.BytesIO(jpeg_bytes)) as image:
            frame = np.asarray(image.convert("L"), dtype=np.uint8)
        brightness = float(np.mean(frame))
        logger.info(
            "Light detector debug: method=pillow jpeg_len=%d brightness=%.1f",
            len(jpeg_bytes),
            brightness,
        )
        return brightness
    except ImportError:
        logger.warning(
            "Light detector debug: Pillow unavailable; using raw JPEG-byte fallback. "
            "Brightness thresholds may be inaccurate until Pillow or OpenCV is installed."
        )
    except Exception as exc:
        logger.debug("Pillow decode failed, using byte estimate: %s", exc)

    # Last-resort fallback: estimate brightness from JPEG payload bytes.
    try:
        data = np.frombuffer(jpeg_bytes, dtype=np.uint8)
        # Skip JPEG header (first ~200 bytes vary) and look at payload
        payload = data[200:] if len(data) > 400 else data
        brightness = float(np.clip(np.mean(payload) * 1.5, 0, 255))
        logger.info(
            "Light detector debug: method=jpeg_payload_mean jpeg_len=%d brightness=%.1f",
            len(jpeg_bytes),
            brightness,
        )
        return brightness
    except Exception:
        return 255.0


def analyze_brightness_from_bytes(image_bytes: bytes) -> float:
    """Alias for generic byte-based brightness analysis."""
    return analyze_brightness_from_jpeg(image_bytes)


# ---------------------------------------------------------------------------
# Shared brightness → PWM mapping (with hysteresis & throttling)
# ---------------------------------------------------------------------------

def brightness_to_pwm(
    brightness: float,
    config: Optional[LightDetectorConfig] = None,
    current_duty: float = 0.0,
    last_update_time: Optional[float] = None,
) -> Tuple[float, bool]:
    """Map a brightness reading to a PWM duty cycle.

    This is the **single shared function** used by both the continuous
    live-feed monitor and the final capture workflow.

    Hysteresis logic:
    - brightness < dark_threshold  → LED needed, compute proportional PWM.
    - brightness > bright_threshold → LED off (duty = 0).
    - in between → keep previous state (hysteresis band).

    Throttling:
    - If *last_update_time* is given and less than *throttle_interval*
      seconds have elapsed, the returned duty cycle is clamped to
      ± *pwm_step* from *current_duty*.

    Args:
        brightness: Mean brightness (0–255).
        config: Tunable parameters (uses defaults if *None*).
        current_duty: Current PWM duty cycle (0.0–1.0).
        last_update_time: Unix timestamp of the last PWM update, or *None*
            to skip throttling.

    Returns:
        ``(target_duty, changed)`` – *target_duty* is the new duty cycle
        and *changed* is *True* when the value differs from *current_duty*.
    """
    if config is None:
        config = LightDetectorConfig()

    brightness = float(np.clip(brightness, 0.0, 255.0))
    current_duty = max(0.0, min(1.0, float(current_duty)))

    # --- Determine raw target duty based on hysteresis ---
    decision = "unchanged"
    throttled = False
    elapsed: Optional[float] = None

    if brightness >= config.bright_threshold:
        # Well-lit scene: LED off immediately.
        raw_duty = 0.0
        decision = "bright_off"
    elif brightness <= config.dark_threshold:
        # Dark scene: once the dark threshold is crossed, ramp from min_pwm
        # at the threshold to max_pwm at zero brightness using an aggressive
        # square-root curve so the LED ramps up quickly even for moderate
        # darkness.
        if config.dark_threshold <= 0:
            raw_duty = config.max_pwm
        else:
            darkness_ratio = 1.0 - (brightness / config.dark_threshold)
            aggressive_ratio = darkness_ratio ** 0.5  # square-root for fast ramp
            raw_duty = config.min_pwm + aggressive_ratio * (config.max_pwm - config.min_pwm)
        decision = "dark_proportional"
    else:
        # Hysteresis band: if the LED is currently off, keep it off until the
        # frame crosses the dark threshold. Once already on, taper linearly
        # from the current active duty toward zero as ambient light returns.
        if current_duty <= 0.001:
            raw_duty = 0.0
            decision = "hysteresis_keep_off"
        else:
            band_span = config.bright_threshold - config.dark_threshold
            taper_ratio = 1.0 - ((brightness - config.dark_threshold) / band_span)
            taper_ratio = max(0.0, min(1.0, taper_ratio))
            raw_duty = current_duty * taper_ratio
            decision = "hysteresis_taper"

    # --- Throttle rate of change ---
    # Never throttle a full-off transition once the scene is clearly bright;
    # this guarantees ambient-light recovery turns the LED off immediately.
    if last_update_time is not None and raw_duty > 0.0:
        elapsed = time.monotonic() - last_update_time
        if elapsed < config.throttle_interval:
            delta = raw_duty - current_duty
            if abs(delta) > config.pwm_step:
                raw_duty = current_duty + config.pwm_step * (1 if delta > 0 else -1)
                throttled = True

    target_duty = max(0.0, min(1.0, raw_duty))
    changed = abs(target_duty - current_duty) > 0.001
    logger.info(
        "PWM mapping debug: brightness=%.1f current=%.2f target=%.2f changed=%s decision=%s throttled=%s elapsed=%s thresholds=(%.1f,%.1f) pwm_range=(%.2f,%.2f)",
        brightness,
        current_duty,
        target_duty,
        changed,
        decision,
        throttled,
        "none" if elapsed is None else f"{elapsed:.2f}s",
        config.dark_threshold,
        config.bright_threshold,
        config.min_pwm,
        config.max_pwm,
    )
    return target_duty, changed
