"""Sender for the browser simulator.

This file pushes robot updates from Python to the page shown in the browser.
"""

import asyncio
import json
import logging
from typing import Any, Dict, Optional

import websockets


logger = logging.getLogger(__name__)


class SimulatorBridgePublisher:
    """Send robot updates to the browser bridge."""

    def __init__(self, uri: str = "ws://127.0.0.1:8765") -> None:
        self.uri = uri
        self._socket: Optional[Any] = None
        self._connect_lock = asyncio.Lock()

    async def start(self) -> None:
        await self._ensure_connected()

    async def stop(self) -> None:
        if self._socket is not None:
            try:
                await self._socket.close()
            finally:
                self._socket = None

    async def _ensure_connected(self) -> bool:
        if self._socket is not None:
            return True

        async with self._connect_lock:
            if self._socket is not None:
                return True

            try:
                self._socket = await websockets.connect(self.uri)
                logger.info("Connected to simulator bridge at %s", self.uri)
                return True
            except Exception as exc:
                logger.warning("Unable to connect to simulator bridge at %s: %s", self.uri, exc)
                self._socket = None
                return False

    async def _send(self, message: Dict[str, Any]) -> None:
        if not await self._ensure_connected():
            return

        try:
            await self._socket.send(json.dumps(message))
        except Exception as exc:
            logger.warning("Simulator bridge publish failed: %s", exc)
            self._socket = None

    async def send_state(self, old_state: str, new_state: str) -> None:
        await self._send({"type": "state", "old_state": old_state, "new_state": new_state})

    async def send_motion(self, gesture_payload: Dict[str, Any]) -> None:
        await self._send({"type": "motion", **gesture_payload})

    async def send_lighting(self, lighting_payload: Dict[str, Any]) -> None:
        await self._send({"type": "lighting", **lighting_payload})

    async def send_speech(self, speech_text: str) -> None:
        await self._send({"type": "speech", "text": speech_text})

    async def send_memory(self, memory_payload: Dict[str, Any]) -> None:
        await self._send({"type": "memory", **memory_payload})
