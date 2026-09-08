"""
Robot control center.

This file watches what the robot sees and hears, then decides what it should
do next: move, light up, speak, remember, or wait.
"""

import asyncio
import os
import logging
from typing import Optional

import yaml

from hardware import create_robot_hardware
from dialogue.conversation import ConversationManager
from memory.scene_memory import SceneMemory
from orchestrator.fsm import StateMachine, RobotState
from orchestrator.event_bus import get_event_bus, Event
from perception import PerceptionPipeline
from sim_bridge.publisher import SimulatorBridgePublisher
from sim_bridge.websocket_server import SimulatorBridge
from speech.stt import SpeechToText
from speech.tts import TextToSpeech


logger = logging.getLogger(__name__)


class RobotOrchestrator:
    """
    Main controller for the robot.

    It keeps the robot's behavior organized and makes sure the camera,
    speech, memory, and expression parts stay in sync.
    """
    
    def __init__(self, config_path: str = "config.yaml", simulator_bridge_url: Optional[str] = None):
        """Initialize orchestrator with config."""
        self.config = self._load_config(config_path)
        self.startup_strict = bool(self.config.get("startup", {}).get("strict", False))
        self.fsm = StateMachine(initial_state=RobotState.IDLE)
        self.event_bus = get_event_bus()
        self._simulator_bridge_url = simulator_bridge_url or self.config.get("simulator", {}).get("bridge_url")
        self.hardware = create_robot_hardware(
            self.config.get("hardware", {}).get("mode", "simulator"),
            self.config.get("hardware", {}),
        )
        
        # Initialize subsystems
        self.perception = PerceptionPipeline(
            camera_index=0,
            min_detection_confidence=self.config.get("perception", {}).get("face_detection", {}).get("min_confidence", 0.5),
            object_threshold=self.config.get("perception", {}).get("object_detection", {}).get("present_object_min_area_px", 5000),
        )
        self.dialogue = ConversationManager()
        self.speech_to_text = self.hardware.microphone
        self.text_to_speech = self.hardware.speaker
        self.expression = {
            "gesture": self.hardware.motion,
            "lighting": self.hardware.lighting,
            "sfx": self.hardware.sfx,
        }
        self.memory = SceneMemory()
        if self._simulator_bridge_url:
            self.simulator_bridge = SimulatorBridgePublisher(self._simulator_bridge_url)
        else:
            self.simulator_bridge = SimulatorBridge(
                host=self.config.get("simulator", {}).get("host", "127.0.0.1"),
                port=int(self.config.get("simulator", {}).get("port", 8765)),
            )
            self.simulator_bridge.set_command_handler(self._handle_bridge_command)
        self.fsm.on_state_change(self._on_state_changed)
        
        # Current context
        self.current_user_speech = ""
        self.observed_objects = []
        
        self._running = False
        self._tasks = []

    def validate_startup(self, strict: Optional[bool] = None) -> None:
        """Validate deploy-time prerequisites before the app starts."""
        strict_mode = self.startup_strict if strict is None else strict
        if not strict_mode:
            return

        errors: list[str] = []
        startup_config = self.config.get("startup", {})
        errors.extend(self._validate_required_api_keys(startup_config))
        errors.extend(self._validate_hardware_startup(startup_config))

        if errors:
            raise RuntimeError("Startup validation failed: " + "; ".join(errors))

    def _validate_required_api_keys(self, startup_config: dict) -> list[str]:
        required_api_keys = startup_config.get(
            "required_api_keys",
            ["DEEPGRAM_API_KEY", "ANTHROPIC_API_KEY", "ELEVENLABS_API_KEY"],
        )
        missing_api_keys = [name for name in required_api_keys if not os.getenv(name)]
        if missing_api_keys:
            return [f"Missing API keys: {', '.join(missing_api_keys)}"]
        return []

    def _validate_hardware_startup(self, startup_config: dict) -> list[str]:
        errors: list[str] = []
        hardware_mode = getattr(self.hardware, "mode", "simulator")

        if hardware_mode == "real":
            readiness = self.hardware.probe_startup()
            if not readiness.get("camera_available", True) or not readiness.get("serial_available", True):
                errors.extend(readiness.get("details", []))
            return errors

        if not startup_config.get("require_camera", False):
            return errors

        if self.config.get("hardware", {}).get("camera_index", 0) < 0:
            errors.append("Invalid camera index")

        return errors
    
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
        self.validate_startup()
        
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
            raise
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
        if self.hardware:
            await self.hardware.stop()
        
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

    async def _on_state_changed(self, old_state: RobotState, new_state: RobotState) -> None:
        """Publish state changes to the simulator bridge and event bus."""
        await self.event_bus.publish(Event(
            topic="orchestrator.state_changed",
            payload={"old_state": old_state.value, "new_state": new_state.value},
        ))

        if self.simulator_bridge:
            await self.simulator_bridge.send_state(old_state.value, new_state.value)

        if self.simulator_bridge and new_state in (RobotState.NOTICE, RobotState.GREET, RobotState.DISENGAGE):
            await self._publish_state_expression(new_state)

    async def _publish_state_expression(self, state: RobotState) -> None:
        """Send a simple state-specific expression to the simulator."""
        gesture_name = {
            RobotState.NOTICE: "attention_grab",
            RobotState.GREET: "warm_embrace",
            RobotState.DISENGAGE: "farewell_wave",
        }.get(state, "neutral")

        motion = await self.expression["gesture"].execute(gesture_name)
        await self.simulator_bridge.send_motion(motion)

        brightness = 0.9 if state != RobotState.DISENGAGE else 0.5
        light = await self.expression["lighting"].set_state_color(state.value, brightness)
        await self.simulator_bridge.send_lighting(light)
    
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
        self.current_user_speech = event.payload.get("text", "")
        logger.info(f"Speech received: {self.current_user_speech}")

        if self.simulator_bridge and self.current_user_speech:
            await self.simulator_bridge.send_speech(self.current_user_speech)

        if self.fsm.can_listen():
            
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

        self.fsm.set_state_data("llm_response", payload)

        if self.expression:
            await self._execute_expression_payload(payload)
        
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

        if self.simulator_bridge:
            await self.simulator_bridge.send_memory({"label": object_label, "description": description})

    async def _execute_expression_payload(self, payload: dict) -> None:
        """Execute the multimodal response payload and mirror it to the simulator."""
        gesture_name = payload.get("gesture", "neutral")
        light = payload.get("light", {"hue": 48, "saturation": 0.8, "brightness": 0.85})
        brightness = float(light.get("brightness", 0.85))
        state_name = self.fsm.current_state.value if self.fsm.current_state else "IDLE"

        motion = await self.expression["gesture"].execute(gesture_name)
        lighting = await self.expression["lighting"].set_state_color(state_name, brightness)

        if payload.get("sfx"):
            await self.expression["sfx"].play(payload["sfx"])
        if payload.get("speech"):
            await self.text_to_speech.speak(payload["speech"])

        if self.simulator_bridge:
            await self.simulator_bridge.send_motion(motion)
            await self.simulator_bridge.send_lighting(lighting)
            if payload.get("speech"):
                await self.simulator_bridge.send_speech(payload["speech"])

    async def _handle_bridge_command(self, payload: dict) -> None:
        """Apply manual control commands coming from the simulator UI."""
        if payload.get("type") != "control":
            return

        command = payload.get("command")
        if command == "set_state":
            state_name = payload.get("state")
            if not state_name:
                return

            try:
                target_state = RobotState[state_name]
            except KeyError:
                logger.warning("Ignoring unknown manual state request: %s", state_name)
                return

            await self.fsm.transition_to(target_state)
            return

        if command == "run_demo":
            await self._run_demo_sequence()

    async def _run_demo_sequence(self) -> None:
        """Run a reusable scripted sequence for the showcase."""
        demo_steps = [
            (RobotState.NOTICE, "Hi there. I noticed you.", "notice_entry", "A person entered the room."),
            (RobotState.GREET, "Hello! I’m glad you’re here.", "greet_entry", "Warm greeting sequence."),
            (RobotState.LISTEN, "I’m listening.", "listen_entry", "Waiting for user speech."),
            (RobotState.CONVERSE, "Tell me about the object you’re holding.", "dialogue_entry", "Conversational response in progress."),
            (RobotState.OBSERVE, "That looks like a coffee mug.", "observe_entry", "Object observation recalled."),
            (RobotState.DISENGAGE, "Goodbye for now.", "disengage_entry", "Leaving the conversation."),
            (RobotState.IDLE, "Standing by.", "idle_entry", "Returning to rest."),
        ]

        for state, speech_text, memory_label, memory_description in demo_steps:
            await self.fsm.transition_to(state)
            if self.simulator_bridge and speech_text:
                await self.simulator_bridge.send_speech(speech_text)
            if self.simulator_bridge:
                await self.simulator_bridge.send_memory({"label": memory_label, "description": memory_description})
            await asyncio.sleep(1.0)
        
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
        if self.simulator_bridge:
            await self.simulator_bridge.start()
    
    @property
    def state(self) -> RobotState:
        """Get current FSM state."""
        return self.fsm.current_state
