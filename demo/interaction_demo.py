"""End-to-end demonstration of the lamp robot interaction loop."""

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orchestrator.coordinator import RobotOrchestrator


async def run_demo() -> None:
    orchestrator = RobotOrchestrator()

    await orchestrator.event_bus.start()
    orchestrator._setup_event_subscriptions()
    await orchestrator._initialize_subsystems()
    await orchestrator._start_subsystems()

    print("Demo: face detected")
    orchestrator.fsm.current_state = orchestrator.fsm.current_state
    await orchestrator._on_face_detected(type("Evt", (), {"payload": {"confidence": 0.95}})())

    print("Demo: user speaks")
    await orchestrator._on_speech_received(
        type(
            "Evt",
            (),
            {"payload": {"text": "Hello there! Can you tell me what this object is?"}},
        )()
    )

    print("Demo: object observation")
    await orchestrator._on_vlm_response(
        type(
            "Evt",
            (),
            {"payload": {"label": "coffee mug", "description": "A warm ceramic mug used for hot drinks."}},
        )()
    )

    print("Demo: final robot state:", orchestrator.fsm.current_state.value)
    await orchestrator.shutdown()


if __name__ == "__main__":
    asyncio.run(run_demo())
