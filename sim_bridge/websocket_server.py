"""Bridge between the Python app and the browser simulator.

This file moves robot updates into the browser so you can watch the lamp react
in real time.
"""

import asyncio
import json
import logging
from typing import Any, Awaitable, Callable, Dict, Optional, Set

import websockets


logger = logging.getLogger(__name__)


class SimulatorBridge:
    """Share robot updates with every connected browser window."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8765) -> None:
        self.host = host
        self.port = port
        self._server = None
        self._clients: Set[Any] = set()
        self._running = False
        self._last_messages: Dict[str, Dict[str, Any]] = {}
        self._command_handler: Optional[Callable[[Dict[str, Any]], Awaitable[None] | None]] = None

    def set_command_handler(
        self,
        handler: Optional[Callable[[Dict[str, Any]], Awaitable[None] | None]],
    ) -> None:
        """Set a callback for control commands coming from the browser."""
        self._command_handler = handler

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
                    if payload.get("type") == "control":
                        await self._handle_control(payload)
                    else:
                        await self._broadcast(payload)
        except Exception as exc:
            logger.debug("Simulator client disconnected: %s", exc)
        finally:
            self._clients.discard(websocket)

    async def _handle_control(self, payload: Dict[str, Any]) -> None:
        if self._command_handler is not None:
            result = self._command_handler(payload)
            if asyncio.iscoroutine(result):
                await result
            return

        state_name = payload.get("state")
        command = payload.get("command")

        if command == "run_demo":
            await self._run_demo_sequence()
            return

        if not state_name:
            return

        await self._apply_state_snapshot(state_name, payload.get("from", "IDLE"))

    async def _apply_state_snapshot(self, state_name: str, old_state: str = "IDLE") -> None:
        state_message = {"type": "state", "old_state": old_state, "new_state": state_name}
        await self._broadcast(state_message)

        gesture_map = {
            "NOTICE": {"gesture": "attention_grab", "duration_ms": 800, "joints": {"base_rotation": 35.0, "lift": 38.0, "extension": 28.0, "head_tilt": 12.0, "eye_pan": 12.0}, "status": "simulated"},
            "GREET": {"gesture": "warm_embrace", "duration_ms": 800, "joints": {"base_rotation": 18.0, "lift": 48.0, "extension": 45.0, "head_tilt": -8.0, "eye_pan": 4.0}, "status": "simulated"},
            "LISTEN": {"gesture": "neutral", "duration_ms": 800, "joints": {"base_rotation": 0.0, "lift": 20.0, "extension": 10.0, "head_tilt": 0.0, "eye_pan": 0.0}, "status": "simulated"},
            "CONVERSE": {"gesture": "curious_inspect", "duration_ms": 800, "joints": {"base_rotation": 12.0, "lift": 32.0, "extension": 22.0, "head_tilt": 15.0, "eye_pan": -10.0}, "status": "simulated"},
            "OBSERVE": {"gesture": "curious_inspect", "duration_ms": 800, "joints": {"base_rotation": 12.0, "lift": 32.0, "extension": 22.0, "head_tilt": 15.0, "eye_pan": -10.0}, "status": "simulated"},
            "DISENGAGE": {"gesture": "farewell_wave", "duration_ms": 800, "joints": {"base_rotation": -40.0, "lift": 50.0, "extension": 35.0, "head_tilt": -15.0, "eye_pan": 15.0}, "status": "simulated"},
            "IDLE": {"gesture": "neutral", "duration_ms": 800, "joints": {"base_rotation": 0.0, "lift": 20.0, "extension": 10.0, "head_tilt": 0.0, "eye_pan": 0.0}, "status": "simulated"},
        }

        motion = gesture_map.get(state_name, gesture_map["IDLE"])
        lighting = {
            "IDLE": {"state": "IDLE", "rgb": [90, 120, 180], "brightness": 0.6, "status": "simulated"},
            "NOTICE": {"state": "NOTICE", "rgb": [255, 255, 255], "brightness": 0.9, "status": "simulated"},
            "GREET": {"state": "GREET", "rgb": [255, 180, 80], "brightness": 0.9, "status": "simulated"},
            "LISTEN": {"state": "LISTEN", "rgb": [100, 255, 150], "brightness": 0.8, "status": "simulated"},
            "CONVERSE": {"state": "CONVERSE", "rgb": [255, 200, 120], "brightness": 0.85, "status": "simulated"},
            "OBSERVE": {"state": "OBSERVE", "rgb": [150, 90, 255], "brightness": 0.85, "status": "simulated"},
            "DISENGAGE": {"state": "DISENGAGE", "rgb": [70, 90, 120], "brightness": 0.45, "status": "simulated"},
        }.get(state_name, {"state": state_name, "rgb": [90, 120, 180], "brightness": 0.6, "status": "simulated"})

        await self._broadcast({"type": "motion", **motion})
        await self._broadcast({"type": "lighting", **lighting})

    async def _run_demo_sequence(self) -> None:
        demo_steps = [
            ("NOTICE", "Hi there. I noticed you.", "notice_entry", "A person entered the room."),
            ("GREET", "Hello! I’m glad you’re here.", "greet_entry", "Warm greeting sequence."),
            ("LISTEN", "I’m listening.", "listen_entry", "Waiting for user speech."),
            ("CONVERSE", "Tell me about the object you’re holding.", "dialogue_entry", "Conversational response in progress."),
            ("OBSERVE", "That looks like a coffee mug.", "observe_entry", "Object observation recalled."),
            ("DISENGAGE", "Goodbye for now.", "disengage_entry", "Leaving the conversation."),
            ("IDLE", "Standing by.", "idle_entry", "Returning to rest."),
        ]

        for state_name, speech_text, memory_label, memory_description in demo_steps:
            await self._apply_state_snapshot(state_name)
            await self._broadcast({"type": "speech", "text": speech_text})
            await self._broadcast({"type": "memory", "label": memory_label, "description": memory_description})
            await asyncio.sleep(1.0)

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
