"""
Finite State Machine (FSM) - Core orchestrator logic.

States: IDLE → NOTICE → GREET → LISTEN/CONVERSE → OBSERVE → DISENGAGE

Each state has entry/exit actions and transition guards.
"""

import asyncio
import logging
from enum import Enum
from typing import Callable, Optional, Dict, Any


logger = logging.getLogger(__name__)


class RobotState(Enum):
    """Valid states for the lamp robot FSM."""
    IDLE = "IDLE"
    NOTICE = "NOTICE"
    GREET = "GREET"
    LISTEN = "LISTEN"
    CONVERSE = "CONVERSE"
    OBSERVE = "OBSERVE"
    DISENGAGE = "DISENGAGE"


class StateMachine:
    """
    Async FSM for lamp robot orchestration.
    
    Transitions are guarded by conditions and can trigger side effects.
    """
    
    def __init__(self, initial_state: RobotState = RobotState.IDLE):
        self.current_state = initial_state
        self.previous_state = initial_state
        self._state_timeouts: Dict[RobotState, Optional[asyncio.Task]] = {}
        self._on_state_change: Optional[Callable] = None
        self._state_data: Dict[str, Any] = {}  # Context/memory for current state
    
    def on_state_change(self, callback: Callable[[RobotState, RobotState], None]) -> None:
        """Register a callback for state changes."""
        self._on_state_change = callback
    
    def set_state_data(self, key: str, value: Any) -> None:
        """Store context data for the current state."""
        self._state_data[key] = value
    
    def get_state_data(self, key: str, default: Any = None) -> Any:
        """Retrieve context data."""
        return self._state_data.get(key, default)
    
    def clear_state_data(self) -> None:
        """Clear state context."""
        self._state_data.clear()
    
    async def transition_to(self, new_state: RobotState) -> bool:
        """
        Attempt to transition to a new state.
        Returns True if successful, False if transition was rejected.
        """
        if new_state == self.current_state:
            logger.debug(f"Already in {new_state}, no transition needed")
            return True
        
        # Cancel any pending timeout for current state
        if self.current_state in self._state_timeouts:
            task = self._state_timeouts[self.current_state]
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            del self._state_timeouts[self.current_state]
        
        logger.info(f"FSM transition: {self.current_state.value} → {new_state.value}")
        
        self.previous_state = self.current_state
        self.current_state = new_state
        self.clear_state_data()
        
        # Call state change callback
        if self._on_state_change:
            try:
                result = self._on_state_change(self.previous_state, new_state)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"Error in state change callback: {e}", exc_info=True)
        
        return True
    
    async def set_timeout(self, timeout_sec: float, next_state: RobotState) -> None:
        """
        Set a timeout for the current state.
        After timeout_sec, automatically transition to next_state if still in current state.
        """
        if timeout_sec <= 0:
            return
        
        current = self.current_state
        
        async def _timeout_handler():
            try:
                await asyncio.sleep(timeout_sec)
                if self.current_state == current:
                    logger.debug(
                        f"State timeout: {current.value} → {next_state.value} "
                        f"(after {timeout_sec}s)"
                    )
                    await self.transition_to(next_state)
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"Error in timeout handler: {e}", exc_info=True)
        
        # Store the task so we can cancel it if we leave state early
        task = asyncio.create_task(_timeout_handler())
        self._state_timeouts[current] = task
    
    def is_in_state(self, state: RobotState) -> bool:
        """Check if currently in a specific state."""
        return self.current_state == state
    
    def can_listen(self) -> bool:
        """Can we accept speech input in the current state?"""
        return self.current_state in (RobotState.LISTEN, RobotState.CONVERSE)
    
    def can_observe(self) -> bool:
        """Can we trigger object observation in the current state?"""
        return self.current_state in (
            RobotState.GREET,
            RobotState.LISTEN,
            RobotState.CONVERSE,
            RobotState.OBSERVE
        )


# Typical FSM usage and state descriptions

STATE_DESCRIPTIONS = {
    RobotState.IDLE: "Resting, waiting for engagement",
    RobotState.NOTICE: "Face detected! Turning attention toward person",
    RobotState.GREET: "Greeting the person with warmth",
    RobotState.LISTEN: "Listening for speech input",
    RobotState.CONVERSE: "Processing speech and generating response",
    RobotState.OBSERVE: "Analyzing an object or scene",
    RobotState.DISENGAGE: "Saying goodbye, attention lost",
}


# State transition rules (not enforced, but documented)
VALID_TRANSITIONS = {
    RobotState.IDLE: [RobotState.NOTICE],
    RobotState.NOTICE: [RobotState.GREET, RobotState.DISENGAGE],
    RobotState.GREET: [RobotState.LISTEN, RobotState.DISENGAGE],
    RobotState.LISTEN: [RobotState.CONVERSE, RobotState.DISENGAGE],
    RobotState.CONVERSE: [RobotState.OBSERVE, RobotState.LISTEN, RobotState.DISENGAGE],
    RobotState.OBSERVE: [RobotState.CONVERSE, RobotState.LISTEN, RobotState.DISENGAGE],
    RobotState.DISENGAGE: [RobotState.IDLE],
}
