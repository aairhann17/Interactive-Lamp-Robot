"""WebSocket bridge that streams orchestrator updates to the browser simulator."""

import asyncio
import json
import logging
from typing import Any, Dict, Optional, Set

import websockets


logger = logging.getLogger(__name__)


class SimulatorBridge:
    """Broadcast robot state and expression updates to connected clients."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8765) -> None:
        self.host = host
        self.port = port
        self._server = None
        self._clients: Set[Any] = set()
        self._running = False
        self._last_messages: Dict[str, Dict[str, Any]] = {}

    async def start(self) -> None:
        if self._running:
            return

        self._server = await websockets.serve(self._handle_client, self.host, self.port)
        self._running = True
        logger.info("Simulator bridge listening on ws://%s:%s", self.host, self.port)

    async def stop(self) -> None:
        self._running = False

        for client in self._clients.copy():
            try:
                await client.close()
            except Exception as exc:
                logger.debug("Error closing simulator client: %s", exc)

        self._clients.clear()

        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    async def _handle_client(self, websocket) -> None:
        self._clients.add(websocket)
        logger.info("Simulator client connected")

        try:
            for message_type in ("state", "motion", "lighting", "speech", "memory"):
                message = self._last_messages.get(message_type)
                if message is not None:
                    await websocket.send(json.dumps(message))

            async for message in websocket:
                try:
                    payload = json.loads(message)
                except json.JSONDecodeError:
                    logger.debug("Ignoring non-JSON simulator client message: %s", message)
                    continue

                if isinstance(payload, dict):
                    await self._broadcast(payload)
        except Exception as exc:
            logger.debug("Simulator client disconnected: %s", exc)
        finally:
            self._clients.discard(websocket)

    async def _broadcast(self, message: Dict[str, Any]) -> None:
        message_type = message.get("type")
        if message_type:
            self._last_messages[message_type] = message

        if not self._clients:
            return

        payload = json.dumps(message)
        stale_clients = []
        for client in self._clients.copy():
            try:
                await client.send(payload)
            except Exception:
                stale_clients.append(client)

        for client in stale_clients:
            self._clients.discard(client)

    async def send_state(self, old_state: str, new_state: str) -> None:
        await self._broadcast({"type": "state", "old_state": old_state, "new_state": new_state})

    async def send_motion(self, gesture_payload: Dict[str, Any]) -> None:
        await self._broadcast({"type": "motion", **gesture_payload})

    async def send_lighting(self, lighting_payload: Dict[str, Any]) -> None:
        await self._broadcast({"type": "lighting", **lighting_payload})

    async def send_speech(self, speech_text: str) -> None:
        await self._broadcast({"type": "speech", "text": speech_text})

    async def send_memory(self, memory_payload: Dict[str, Any]) -> None:
        await self._broadcast({"type": "memory", **memory_payload})
