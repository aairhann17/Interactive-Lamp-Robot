"""Hardware abstraction layer for motion, lighting, audio, and camera access."""

import asyncio
import logging
from dataclasses import dataclass

from expression.gesture_controller import GestureController
from expression.lighting import LightingController
from expression.sfx import SFXController
from speech.stt import SpeechToText
from speech.tts import TextToSpeech


logger = logging.getLogger(__name__)


class NullCameraDriver:
    """Placeholder camera driver for the current simulator-first stack."""

    async def capture_frame(self):
        return None

    async def stop(self) -> None:
        await asyncio.sleep(0)


@dataclass
class RobotHardware:
    """Bundle of robot-facing device interfaces."""

    motion: GestureController
    lighting: LightingController
    sfx: SFXController
    microphone: SpeechToText
    speaker: TextToSpeech
    camera: NullCameraDriver

    async def stop(self) -> None:
        for component in (self.motion, self.lighting, self.sfx, self.microphone, self.speaker, self.camera):
            if hasattr(component, "stop"):
                await component.stop()


def create_robot_hardware(mode: str = "simulator") -> RobotHardware:
    """Create the current hardware stack.

    The repository still runs against simulator-safe drivers. This factory keeps
    the hardware boundary in one place so real device drivers can be swapped in
    later without changing the orchestrator.
    """

    if mode != "simulator":
        logger.warning("Hardware mode %s is not implemented yet; using simulator-safe drivers", mode)

    return RobotHardware(
        motion=GestureController(),
        lighting=LightingController(),
        sfx=SFXController(),
        microphone=SpeechToText(),
        speaker=TextToSpeech(),
        camera=NullCameraDriver(),
    )
