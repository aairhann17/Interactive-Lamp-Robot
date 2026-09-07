"""End-to-end demonstration of the lamp robot interaction loop."""

import asyncio
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orchestrator.coordinator import RobotOrchestrator


def parse_args() -> argparse.Namespace:
    """Parse demo runtime options."""
    parser = argparse.ArgumentParser(description="Run the lamp robot interaction demo")
    parser.add_argument(
        "--bridge-url",
        type=str,
        default=None,
        help="WebSocket URL of an already running simulator bridge server.",
    )
    parser.add_argument(
        "--hold-seconds",
        type=float,
        default=1.0,
        help="How long to keep the simulator bridge alive after the scripted interaction.",
    )
    return parser.parse_args()


async def run_demo(hold_seconds: float = 1.0, bridge_url: str | None = None) -> None:
    orchestrator = RobotOrchestrator(simulator_bridge_url=bridge_url)

    await orchestrator.event_bus.start()
    orchestrator._setup_event_subscriptions()
    await orchestrator._initialize_subsystems()
    await orchestrator._start_subsystems()

    # Allow the browser simulator time to connect before the first updates.
    await asyncio.sleep(1.0)

    print("Demo: face detected")
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

    # Keep the simulator alive briefly so the browser can render the final state.
    if hold_seconds > 0:
        await asyncio.sleep(hold_seconds)

    print("Demo: final robot state:", orchestrator.fsm.current_state.value)
    await orchestrator.shutdown()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(run_demo(hold_seconds=args.hold_seconds, bridge_url=args.bridge_url))
