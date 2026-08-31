"""Lighting controller for state-based lamp color output."""

import asyncio
import logging
from typing import Any, Dict


logger = logging.getLogger(__name__)


class LightingController:
    """Minimal lighting playback stub for the robot's lamp body."""

    def __init__(self) -> None:
        self.state_colors = {
            "IDLE": (90, 120, 180),
            "NOTICE": (255, 255, 255),
            "GREET": (255, 180, 80),
            "LISTEN": (100, 255, 150),
            "CONVERSE": (255, 200, 120),
            "OBSERVE": (150, 90, 255),
            "DISENGAGE": (70, 90, 120),
        }

    async def set_state_color(self, state_name: str, brightness: float = 1.0) -> Dict[str, Any]:
        rgb = self.state_colors.get(state_name, self.state_colors["IDLE"])
        scaled = tuple(int(channel * brightness) for channel in rgb)
        logger.info("Lighting state %s -> %s", state_name, scaled)
        await asyncio.sleep(0.05)
        return {"state": state_name, "rgb": list(scaled), "brightness": brightness, "status": "simulated"}

    async def stop(self) -> None:
        await asyncio.sleep(0)
