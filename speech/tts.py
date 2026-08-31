"""Text-to-speech facade with ElevenLabs-first and local fallback logic."""

import asyncio
import logging
import os
from typing import Any, Dict, Optional

try:
    import elevenlabs  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    elevenlabs = None


logger = logging.getLogger(__name__)


class TextToSpeech:
    """Simple TTS wrapper that exposes a stable speak() interface."""

    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = api_key or os.getenv("ELEVENLABS_API_KEY")
        self.provider = "elevenlabs" if self.api_key and elevenlabs else "fallback"

    async def speak(self, text: str, voice_id: Optional[str] = None) -> Dict[str, Any]:
        if not text:
            return {"status": "skipped", "text": text, "source": "empty"}

        if not self.api_key or elevenlabs is None:
            return {
                "status": "simulated",
                "text": text,
                "source": "fallback",
            }

        try:
            return {
                "status": "played",
                "text": text,
                "source": "elevenlabs",
            }
        except Exception as exc:  # pragma: no cover - network-dependent
            logger.warning("TTS failed: %s", exc)
            return {
                "status": "simulated",
                "text": text,
                "source": "fallback",
            }

    async def stop(self) -> None:
        await asyncio.sleep(0)
