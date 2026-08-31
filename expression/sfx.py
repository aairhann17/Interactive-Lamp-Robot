"""Simple sound-effect controller for robot expression cues."""

import asyncio
import logging
from typing import Any, Dict


logger = logging.getLogger(__name__)


class SFXController:
    """A minimal SFX wrapper that emits event-like playback commands."""

    def __init__(self) -> None:
        self.sounds = {
            "engagement_chime": "ascending bell",
            "thinking_beep": "soft processing tone",
            "success_ding": "confirmation chime",
            "confused_chirp": "uncertain chirp",
        }

    async def play(self, sound_name: str) -> Dict[str, Any]:
        sound = self.sounds.get(sound_name, "neutral hum")
        logger.info("Playing sound effect: %s", sound_name)
        await asyncio.sleep(0.05)
        return {"sound": sound_name, "label": sound, "status": "simulated"}

    async def stop(self) -> None:
        await asyncio.sleep(0)
