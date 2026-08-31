"""
Orchestrator Coordinator - Ties together FSM, perception, dialogue, and expression.

This is the main orchestration logic that binds all subsystems.
"""

import asyncio
import logging
from typing import Optional

import yaml

from dialogue.conversation import ConversationManager
from expression.gesture_controller import GestureController
from expression.lighting import LightingController
from expression.sfx import SFXController
from memory.scene_memory import SceneMemory
from orchestrator.fsm import StateMachine, RobotState
from orchestrator.event_bus import get_event_bus, Event
from perception import PerceptionPipeline
from speech.stt import SpeechToText
from speech.tts import TextToSpeech


logger = logging.getLogger(__name__)


class RobotOrchestrator:
    """
    Main orchestrator that coordinates all robot systems.
    
    Responsibilities:
    - Maintain FSM state
    - Subscribe to perception events
    - Trigger expression outputs
    - Manage dialogue flow
    - Coordinate memory updates
    """
    
    def __init__(self, config_path: str = "config.yaml"):
        """Initialize orchestrator with config."""
        self.config = self._load_config(config_path)
        self.fsm = StateMachine(initial_state=RobotState.IDLE)
        self.event_bus = get_event_bus()
        
        # Initialize subsystems
        self.perception = PerceptionPipeline(
            camera_index=0,
            min_detection_confidence=self.config.get("perception", {}).get("face_detection", {}).get("min_confidence", 0.5),
            object_threshold=self.config.get("perception", {}).get("object_detection", {}).get("present_object_min_area_px", 5000),
        )
        self.dialogue = ConversationManager()
        self.speech_to_text = SpeechToText()
        self.text_to_speech = TextToSpeech()
        self.expression = {
            "gesture": GestureController(),
            "lighting": LightingController(),
            "sfx": SFXController(),
        }
        self.memory = SceneMemory()
        self.simulator_bridge = None
        
        # Current context
        self.current_user_speech = ""
        self.observed_objects = []
        
        self._running = False
        self._tasks = []
    
    def _load_config(self, config_path: str) -> dict:
        """Load configuration from YAML file."""
        try:
            with open(config_path) as f:
                return yaml.safe_load(f) or {}
        except FileNotFoundError:
            logger.warning(f"Config file {config_path} not found, using defaults")
            return {}
    
    async def run(self) -> None:
        """Start the orchestrator and all subsystems."""
        logger.info("Initializing orchestrator")
        
        # Start event bus
        await self.event_bus.start()
        
        # Subscribe to events
        self._setup_event_subscriptions()
        
        # Initialize subsystems
        await self._initialize_subsystems()
        
        # Start subsystems
        await self._start_subsystems()
        
        self._running = True
        logger.info("Orchestrator running")
        
        # Main loop
        try:
            while self._running:
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            logger.info("Orchestrator cancelled")
        finally:
            await self.shutdown()
    
    async def shutdown(self) -> None:
        """Gracefully shut down all subsystems."""
        logger.info("Shutting down orchestrator")
        self._running = False
        
        # Stop subsystems
        if self.perception:
            await self.perception.stop()
        if self.dialogue:
            await self.dialogue.stop()
        if self.expression:
            for controller in self.expression.values():
                if hasattr(controller, "stop"):
                    await controller.stop()
        if self.simulator_bridge:
            await self.simulator_bridge.stop()
        
        # Cancel tasks
        for task in self._tasks:
            if not task.done():
                task.cancel()
        
        # Stop event bus
        await self.event_bus.stop()
        
        logger.info("Orchestrator shutdown complete")
    
    def _setup_event_subscriptions(self) -> None:
        """Subscribe orchestrator to perception and dialogue events."""
        
        # Face detection → NOTICE state
        self.event_bus.subscribe(
            "camera.face_detected",
            self._on_face_detected
        )
        
        # Face lost → DISENGAGE state
        self.event_bus.subscribe(
            "camera.face_lost",
            self._on_face_lost
        )
        
        # Object presented → prepare for OBSERVE
        self.event_bus.subscribe(
            "camera.object_presented",
            self._on_object_presented
        )
        
        # Speech received → trigger dialogue
        self.event_bus.subscribe(
            "audio.speech_received",
            self._on_speech_received
        )
        
        # LLM response → execute expression
        self.event_bus.subscribe(
            "llm.response_generated",
            self._on_llm_response
        )
        
        # VLM object analysis → store in memory
        self.event_bus.subscribe(
            "vlm.object_analyzed",
            self._on_vlm_response
        )
        
        logger.info("Event subscriptions configured")
    
    async def _on_face_detected(self, event: Event) -> None:
        """Handle face detection."""
        if self.fsm.is_in_state(RobotState.IDLE):
            logger.info("Face detected, transitioning to NOTICE")
            await self.fsm.transition_to(RobotState.NOTICE)
            
            # Set timeout to auto-transition to GREET if face sustained
            notice_timeout = self.config.get("fsm", {}).get("notice_timeout_sec", 2.0)
            await self.fsm.set_timeout(notice_timeout, RobotState.GREET)
    
    async def _on_face_lost(self, event: Event) -> None:
        """Handle face loss."""
        if self.fsm.current_state != RobotState.IDLE:
            logger.info("Face lost, transitioning to DISENGAGE")
            await self.fsm.transition_to(RobotState.DISENGAGE)
            
            # After disengage animation, return to IDLE
            disengage_timeout = self.config.get("fsm", {}).get("disengage_duration_sec", 2.0)
            await self.fsm.set_timeout(disengage_timeout, RobotState.IDLE)
    
    async def _on_object_presented(self, event: Event) -> None:
        """Handle object presentation."""
        if self.fsm.can_observe():
            logger.debug("Object presented during observation-ready state")
            self.fsm.set_state_data("pending_object_bbox", event.payload.get("bbox"))
            
            # Will trigger VLM analysis when in OBSERVE state
            if self.fsm.current_state != RobotState.OBSERVE:
                await self.fsm.transition_to(RobotState.OBSERVE)
    
    async def _on_speech_received(self, event: Event) -> None:
        """Handle speech input."""
        if self.fsm.can_listen():
            self.current_user_speech = event.payload.get("text", "")
            logger.info(f"Speech received: {self.current_user_speech}")
            
            # Transition to CONVERSE to process response
            await self.fsm.transition_to(RobotState.CONVERSE)
            
            # Trigger LLM dialogue
            if self.dialogue:
                await self.dialogue.generate_response(
                    user_text=self.current_user_speech,
                    scene_context={
                        "observed_objects": self.observed_objects,
                        "current_state": self.fsm.current_state.value
                    }
                )
    
    async def _on_llm_response(self, event: Event) -> None:
        """Handle LLM-generated response."""
        payload = event.payload
        
        logger.info(f"LLM response: {payload.get('speech', '')}")
        
        # Store response for expression
        self.fsm.set_state_data("llm_response", payload)
        
        # Trigger expression (gesture + light + sound + speech)
        if self.expression:
            gesture_name = payload.get("gesture", "neutral")
            light = payload.get("light", {"hue": 48, "saturation": 0.8, "brightness": 0.85})
            brightness = float(light.get("brightness", 0.85))
            state_name = self.fsm.current_state.value if self.fsm.current_state else "IDLE"
            await self.expression["gesture"].execute(gesture_name)
            await self.expression["lighting"].set_state_color(state_name, brightness)
            if payload.get("sfx"):
                await self.expression["sfx"].play(payload["sfx"])
            if payload.get("speech"):
                await self.text_to_speech.speak(payload["speech"])
        
        # Check if we need to observe an object
        if payload.get("observe_trigger", False):
            await self.fsm.transition_to(RobotState.OBSERVE)
        else:
            # Otherwise, return to listening or idle
            if self.fsm.current_state == RobotState.CONVERSE:
                listen_timeout = self.config.get("fsm", {}).get("listen_timeout_sec", 10.0)
                await self.fsm.transition_to(RobotState.LISTEN)
                await self.fsm.set_timeout(listen_timeout, RobotState.IDLE)
    
    async def _on_vlm_response(self, event: Event) -> None:
        """Handle VLM object analysis."""
        payload = event.payload
        object_label = payload.get("label", "unknown")
        description = payload.get("description", "")
        
        logger.info(f"Object analyzed: {object_label}")
        
        # Store in memory
        self.observed_objects.append({
            "label": object_label,
            "description": description,
            "timestamp": asyncio.get_event_loop().time()
        })
        
        if self.memory:
            await self.memory.store_object(object_label, description)
        
        # Transition back to listening for follow-up questions
        if self.fsm.current_state == RobotState.OBSERVE:
            await self.fsm.transition_to(RobotState.LISTEN)
    
    async def _initialize_subsystems(self) -> None:
        """Initialize all perception, dialogue, and expression subsystems."""
        logger.info("Initializing subsystems")
        if self.perception:
            await self.perception.start()
        if self.dialogue:
            logger.info("Conversation manager ready")
        if self.memory:
            logger.info("Scene memory ready")
        if self.speech_to_text:
            logger.info("STT service ready")
        if self.text_to_speech:
            logger.info("TTS service ready")
    
    async def _start_subsystems(self) -> None:
        """Start all subsystems."""
        logger.info("Starting subsystems")
        # Minimal no-op startup for the current MVP; real integrations can be
        # added here when their runtime backends are available.
    
    @property
    def state(self) -> RobotState:
        """Get current FSM state."""
        return self.fsm.current_state
