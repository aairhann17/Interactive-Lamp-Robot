"""Cloud VLM abstraction for object description analysis."""

import asyncio
import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class VLMAnalyzer:
    """Thin wrapper around a cloud vision-language model.

    If no API key is configured, it falls back to a deterministic placeholder
    response so the rest of the orchestration pipeline stays testable.
    """

    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.provider = "anthropic" if self.api_key else "fallback"

    async def analyze_object(self, frame=None, user_prompt: str = "") -> Dict[str, Any]:
        if not self.api_key:
            return {
                "label": "unidentified object",
                "description": "A small object was detected but no cloud model is configured yet.",
                "source": "fallback",
            }

        try:
            import anthropic  # type: ignore
        except Exception as exc:  # pragma: no cover - optional dependency
            logger.warning("Anthropic SDK unavailable: %s", exc)
            return {
                "label": "unidentified object",
                "description": "Vision analysis could not run because the SDK is unavailable.",
                "source": "fallback",
            }

        # The full frame is intentionally not sent in this MVP stub: the real
        # implementation should use a cropped object frame and minimal context.
        prompt = user_prompt or "Describe the primary object in this image in one sentence."

        try:
            client = anthropic.Anthropic(api_key=self.api_key)
            response = await asyncio.to_thread(
                client.messages.create,
                model="claude-3-5-sonnet-20241022",
                max_tokens=128,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt,
                            }
                        ],
                    }
                ],
            )

            text = getattr(response, "content", [])
            message_text = "".join(
                part.text for part in text if getattr(part, "type", "") == "text"
            ) if text else ""

            if message_text:
                return {
                    "label": "identified object",
                    "description": message_text.strip(),
                    "source": "anthropic",
                }
        except Exception as exc:  # pragma: no cover - network/API dependent
            logger.warning("VLM analysis call failed: %s", exc)

        return {
            "label": "unidentified object",
            "description": "Cloud vision analysis failed; falling back to a safe default description.",
            "source": "fallback",
        }

    async def stop(self) -> None:
        return None
