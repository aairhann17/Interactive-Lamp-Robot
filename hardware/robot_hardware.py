"""Hardware abstraction layer for motion, lighting, audio, and camera access."""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

try:
    import cv2  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    cv2 = None

try:
    import serial  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    serial = None

from expression.gesture_controller import GestureController
from expression.lighting import LightingController
from expression.sfx import SFXController
from speech.stt import SpeechToText
from speech.tts import TextToSpeech


logger = logging.getLogger(__name__)


class NullCameraDriver:
    """Placeholder camera driver for the current simulator-first stack."""

    async def capture_frame(self):
        await asyncio.sleep(0)
        return None

    async def stop(self) -> None:
        await asyncio.sleep(0)


class OpenCVCameraDriver:
    """Minimal camera driver backed by OpenCV."""

    def __init__(self, camera_index: int = 0) -> None:
        self.camera_index = camera_index
        self.camera = None

    async def start(self) -> None:
        await asyncio.sleep(0)
        if cv2 is None:
            return
        if self.camera is None:
            self.camera = cv2.VideoCapture(self.camera_index)

    async def capture_frame(self):
        await asyncio.sleep(0)
        if self.camera is None and cv2 is not None:
            await self.start()
        if self.camera is None:
            return None
        ok, frame = self.camera.read()
        return frame if ok else None

    async def stop(self) -> None:
        await asyncio.sleep(0)
        if self.camera is not None:
            self.camera.release()
            self.camera = None

    def is_available(self) -> bool:
        if cv2 is None:
            return False
        capture = cv2.VideoCapture(self.camera_index)
        try:
            return capture.isOpened()
        finally:
            capture.release()


class SerialCommandTransport:
    """Shared JSON-over-serial helper for real hardware peripherals."""

    def __init__(self, port: str, baudrate: int = 115200, timeout: float = 1.0) -> None:
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self._connection = None

    def connect(self) -> bool:
        if serial is None:
            return False
        if self._connection is not None:
            return True
        self._connection = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
        return True

    def is_available(self) -> bool:
        if serial is None:
            return False

        try:
            probe = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
        except Exception:
            return False

        try:
            return True
        finally:
            probe.close()

    def send(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.connect():
            raise RuntimeError("Serial support is unavailable")

        encoded = (json.dumps(payload) + "\n").encode("utf-8")
        self._connection.write(encoded)
        self._connection.flush()
        return {"status": "sent", **payload}

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None


class SerialGestureController:
    """Motion driver that forwards gesture commands over serial."""

    def __init__(self, transport: SerialCommandTransport) -> None:
        self.transport = transport

    async def execute(self, gesture_name: str, duration_ms: int = 800) -> Dict[str, Any]:
        payload = {
            "component": "motion",
            "gesture": gesture_name,
            "duration_ms": duration_ms,
        }
        logger.info("Sending gesture %s to serial transport", gesture_name)
        return await asyncio.to_thread(self.transport.send, payload)

    async def stop(self) -> None:
        await asyncio.to_thread(self.transport.close)


class SerialLightingController:
    """Lighting driver that forwards state color commands over serial."""

    def __init__(self, transport: SerialCommandTransport, state_colors: Dict[str, tuple[int, int, int]]) -> None:
        self.transport = transport
        self.state_colors = state_colors

    async def set_state_color(self, state_name: str, brightness: float = 1.0) -> Dict[str, Any]:
        rgb = self.state_colors.get(state_name, self.state_colors["IDLE"])
        scaled = [int(channel * brightness) for channel in rgb]
        payload = {
            "component": "lighting",
            "state": state_name,
            "rgb": scaled,
            "brightness": brightness,
        }
        logger.info("Sending lighting state %s to serial transport", state_name)
        return await asyncio.to_thread(self.transport.send, payload)

    async def stop(self) -> None:
        await asyncio.to_thread(self.transport.close)


class SerialSFXController:
    """Sound-effect driver that forwards cue names over serial."""

    def __init__(self, transport: SerialCommandTransport) -> None:
        self.transport = transport

    async def play(self, sound_name: str) -> Dict[str, Any]:
        payload = {"component": "sfx", "sound": sound_name}
        logger.info("Sending sound cue %s to serial transport", sound_name)
        return await asyncio.to_thread(self.transport.send, payload)

    async def stop(self) -> None:
        await asyncio.to_thread(self.transport.close)


@dataclass
class RobotHardware:
    """Bundle of robot-facing device interfaces."""

    motion: Any
    lighting: Any
    sfx: Any
    microphone: SpeechToText
    speaker: TextToSpeech
    camera: Any
    mode: str = "simulator"
    metadata: Dict[str, Any] = field(default_factory=dict)

    async def stop(self) -> None:
        for component in (self.motion, self.lighting, self.sfx, self.microphone, self.speaker, self.camera):
            if hasattr(component, "stop"):
                await component.stop()

    def probe_startup(self) -> Dict[str, Any]:
        """Report basic readiness for deploy-time validation."""
        readiness = {
            "mode": self.mode,
            "camera_available": True,
            "serial_available": True,
            "details": [],
        }

        if isinstance(self.camera, NullCameraDriver):
            readiness["camera_available"] = False
            readiness["details"].append("camera is using the null driver")
        elif isinstance(self.camera, OpenCVCameraDriver) and not self.camera.is_available():
            readiness["camera_available"] = False
            readiness["details"].append(f"camera index {self.camera.camera_index} is not available")

        if self.mode == "real":
            serial_port = self.metadata.get("serial_port")
            transport = self.metadata.get("transport")
            if serial is None or not serial_port:
                readiness["serial_available"] = False
                readiness["details"].append("serial transport is unavailable")
            elif transport is not None and hasattr(transport, "is_available") and not transport.is_available():
                readiness["serial_available"] = False
                readiness["details"].append(f"serial port {serial_port} is not available")

        return readiness

    async def probe(self) -> Dict[str, Any]:
        """Report basic readiness for the configured hardware backend."""
        await asyncio.sleep(0)
        return self.probe_startup()


def create_robot_hardware(mode: str = "simulator", config: Optional[Dict[str, Any]] = None) -> RobotHardware:
    """Create the current hardware stack.

    The repository still runs against simulator-safe drivers. This factory keeps
    the hardware boundary in one place so real device drivers can be swapped in
    later without changing the orchestrator.
    """

    config = config or {}
    camera_index = int(config.get("camera_index", 0))
    serial_port = config.get("serial_port", "")
    serial_baudrate = int(config.get("serial_baudrate", 115200))

    if mode != "simulator":
        if serial is None or not serial_port:
            logger.warning(
                "Hardware mode %s requested but serial hardware is not configured; using simulator-safe drivers",
                mode,
            )
        elif mode == "real":
            logger.info("Hardware mode real requested; using serial-backed adapters when available")

    if mode == "real" and serial is not None and serial_port:
        transport = SerialCommandTransport(serial_port, serial_baudrate)
        return RobotHardware(
            motion=SerialGestureController(transport),
            lighting=SerialLightingController(
                transport,
                {
                    "IDLE": (90, 120, 180),
                    "NOTICE": (255, 255, 255),
                    "GREET": (255, 180, 80),
                    "LISTEN": (100, 255, 150),
                    "CONVERSE": (255, 200, 120),
                    "OBSERVE": (150, 90, 255),
                    "DISENGAGE": (70, 90, 120),
                },
            ),
            sfx=SerialSFXController(transport),
            microphone=SpeechToText(),
            speaker=TextToSpeech(),
            camera=OpenCVCameraDriver(camera_index),
            mode=mode,
            metadata={
                "serial_port": serial_port,
                "serial_baudrate": serial_baudrate,
                "camera_index": camera_index,
                "transport": transport,
            },
        )

    return RobotHardware(
        motion=GestureController(),
        lighting=LightingController(),
        sfx=SFXController(),
        microphone=SpeechToText(),
        speaker=TextToSpeech(),
        camera=NullCameraDriver(),
        mode=mode,
        metadata={"camera_index": camera_index},
    )
