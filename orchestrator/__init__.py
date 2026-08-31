"""
Orchestrator package - FSM, event bus, and main coordination logic.
"""

from orchestrator.fsm import StateMachine, RobotState
from orchestrator.event_bus import (
    EventBus,
    Event,
    get_event_bus,
    event_face_detected,
    event_face_lost,
    event_object_presented,
    event_speech_received,
    event_llm_response,
    event_vlm_object_analyzed,
    event_state_changed,
)
from orchestrator.coordinator import RobotOrchestrator

__all__ = [
    "StateMachine",
    "RobotState",
    "EventBus",
    "Event",
    "get_event_bus",
    "event_face_detected",
    "event_face_lost",
    "event_object_presented",
    "event_speech_received",
    "event_llm_response",
    "event_vlm_object_analyzed",
    "event_state_changed",
    "RobotOrchestrator",
]
