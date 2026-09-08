"""Shared message format for the real robot hardware.

This keeps the Python app and the microcontroller speaking the same language.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


PROTOCOL_NAME = "lamp-robot-device-protocol-v1"


@dataclass(frozen=True)
class DeviceCommand:
    """A single command message for the robot controller."""

    component: str
    command: str
    payload: Dict[str, Any] = field(default_factory=dict)
    request_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        message = {
            "protocol": PROTOCOL_NAME,
            "component": self.component,
            "command": self.command,
            "payload": self.payload,
        }
        if self.request_id is not None:
            message["request_id"] = self.request_id
        return message


def build_motion_command(gesture_name: str, duration_ms: int) -> Dict[str, Any]:
    return DeviceCommand(
        component="motion",
        command="execute_gesture",
        payload={"gesture": gesture_name, "duration_ms": duration_ms},
    ).to_dict()


def build_lighting_command(state_name: str, rgb: list[int], brightness: float) -> Dict[str, Any]:
    return DeviceCommand(
        component="lighting",
        command="set_state_color",
        payload={"state": state_name, "rgb": rgb, "brightness": brightness},
    ).to_dict()


def build_sfx_command(sound_name: str) -> Dict[str, Any]:
    return DeviceCommand(
        component="sfx",
        command="play_sound",
        payload={"sound": sound_name},
    ).to_dict()


def build_health_command() -> Dict[str, Any]:
    return DeviceCommand(
        component="system",
        command="health_check",
        payload={},
    ).to_dict()
