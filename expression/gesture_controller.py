"""Gesture controller for motion playback and state-driven robot motion."""

import asyncio
import logging
from typing import Any, Dict


logger = logging.getLogger(__name__)


class GestureController:
    """Deterministic stub for motion execution in the MVP."""

    def __init__(self) -> None:
        self.gestures = {
            "neutral": {"base_rotation": 0.0, "lift": 20.0, "extension": 10.0, "head_tilt": 0.0, "eye_pan": 0.0},
            "attention_grab": {"base_rotation": 35.0, "lift": 38.0, "extension": 28.0, "head_tilt": 12.0, "eye_pan": 12.0},
            "warm_embrace": {"base_rotation": 18.0, "lift": 48.0, "extension": 45.0, "head_tilt": -8.0, "eye_pan": 4.0},
            "curious_inspect": {"base_rotation": 12.0, "lift": 32.0, "extension": 22.0, "head_tilt": 15.0, "eye_pan": -10.0},
            "confused_shrug": {"base_rotation": -18.0, "lift": 25.0, "extension": 15.0, "head_tilt": -12.0, "eye_pan": 18.0},
            "farewell_wave": {"base_rotation": -40.0, "lift": 50.0, "extension": 35.0, "head_tilt": -15.0, "eye_pan": 15.0},
        }

    async def execute(self, gesture_name: str, duration_ms: int = 800) -> Dict[str, Any]:
        gesture = self.gestures.get(gesture_name, self.gestures["neutral"])
        logger.info("Executing gesture %s for %d ms", gesture_name, duration_ms)
        await asyncio.sleep(0.05)
        return {
            "gesture": gesture_name,
            "duration_ms": duration_ms,
            "joints": gesture,
            "status": "simulated",
        }

    async def stop(self) -> None:
        await asyncio.sleep(0)
