"""Robot conversation helper.

This file turns what the person said into a short reply, a movement idea, and
light/sound suggestions.
"""

import asyncio
import json
import logging
import os
from typing import Any, Dict, Optional

try:
    import anthropic  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    anthropic = None


logger = logging.getLogger(__name__)


class ConversationManager:
    """Turn a user's words into the robot's reply plan."""

    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.system_prompt = (
            "You are a warm, curious lamp robot. Respond in JSON with keys "
            "speech, gesture, light, sfx, observe_trigger. Keep the voice warm and short."
        )

    async def generate_response(
        self,
        user_text: str,
        scene_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not user_text:
            user_text = "hello"

        if not self.api_key or anthropic is None:
            return {
                "speech": "Hello there! I am glad to see you. How can I help today?",
                "gesture": "warm_embrace",
                "light": {"hue": 48, "saturation": 0.8, "brightness": 0.85},
                "sfx": "engagement_chime",
                "observe_trigger": False,
                "source": "fallback",
            }

        try:
            client = anthropic.Anthropic(api_key=self.api_key)
            payload = {
                "model": "claude-3-5-sonnet-20241022",
                "max_tokens": 200,
                "temperature": 0.8,
                "system": self.system_prompt,
                "messages": [
                    {
                        "role": "user",
                        "content": (
                            f"User said: {user_text}. "
                            f"Scene context: {json.dumps(scene_context or {}, default=str)}"
                        ),
                    }
                ],
            }
            response = await asyncio.to_thread(client.messages.create, **payload)
            text = "".join(
                part.text for part in getattr(response, "content", []) if getattr(part, "type", "") == "text"
            )
            if text:
                try:
                    data = json.loads(text)
                    data.setdefault("source", "anthropic")
                    return data
                except json.JSONDecodeError:
                    logger.warning("LLM returned non-JSON text: %s", text)

        except Exception as exc:  # pragma: no cover - network dependent
            logger.warning("Conversation generation failed: %s", exc)

        return {
            "speech": "I heard you, and I am paying attention. Tell me what you would like to explore.",
            "gesture": "curious_inspect",
            "light": {"hue": 130, "saturation": 0.7, "brightness": 0.75},
            "sfx": "thinking_beep",
            "observe_trigger": False,
            "source": "fallback",
        }

    async def stop(self) -> None:
        await asyncio.sleep(0)
