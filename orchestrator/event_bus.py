"""
Event Bus - In-process pub/sub for orchestrator state changes and perception events.

Uses asyncio.Queue for efficient inter-component communication.
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Callable, Any, Dict, List, Optional


logger = logging.getLogger(__name__)


@dataclass
class Event:
    """Generic event with topic and payload."""
    topic: str
    payload: Dict[str, Any]
    
    def __repr__(self) -> str:
        return f"Event(topic={self.topic}, payload={self.payload})"


class EventBus:
    """
    Simple pub/sub event bus using asyncio.Queue.
    
    Topics:
    - camera.face_detected: { confidence, head_pose: {yaw, pitch, roll}, bbox }
    - camera.face_lost: {}
    - camera.object_presented: { bbox, object_id }
    - audio.speech_started: {}
    - audio.speech_received: { text, confidence }
    - audio.listening_active: { active: bool }
    - llm.response_generated: { speech, gesture, light, sfx, observe_trigger }
    - vlm.object_analyzed: { label, description, object_id }
    - memory.object_stored: { object_id, label }
    - orchestrator.state_changed: { old_state, new_state }
    """
    
    def __init__(self):
        self._queue: asyncio.Queue[Event] = asyncio.Queue()
        self._subscribers: Dict[str, List[Callable]] = {}
        self._running = False
    
    def subscribe(self, topic: str, callback: Callable[[Event], None]) -> Callable:
        """
        Subscribe a callback to a topic.
        Callback should accept an Event argument.
        
        Returns an unsubscribe function.
        """
        if topic not in self._subscribers:
            self._subscribers[topic] = []
        
        self._subscribers[topic].append(callback)
        logger.debug(f"Subscribed to {topic}")
        
        def unsubscribe():
            if topic in self._subscribers and callback in self._subscribers[topic]:
                self._subscribers[topic].remove(callback)
                logger.debug(f"Unsubscribed from {topic}")
        
        return unsubscribe
    
    async def publish(self, event: Event) -> None:
        """Publish an event; will be dispatched to all subscribers."""
        await self._queue.put(event)
    
    async def _dispatch_worker(self) -> None:
        """Internal worker that pulls from queue and calls subscribers."""
        while self._running:
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                
                # Call wildcard subscribers (if any)
                if "*" in self._subscribers:
                    for callback in self._subscribers["*"]:
                        try:
                            result = callback(event)
                            if asyncio.iscoroutine(result):
                                await result
                        except Exception as e:
                            logger.error(f"Error in wildcard subscriber: {e}", exc_info=True)
                
                # Call topic-specific subscribers
                if event.topic in self._subscribers:
                    for callback in self._subscribers[event.topic]:
                        try:
                            result = callback(event)
                            if asyncio.iscoroutine(result):
                                await result
                        except Exception as e:
                            logger.error(
                                f"Error in subscriber for {event.topic}: {e}",
                                exc_info=True
                            )
                
                self._queue.task_done()
            
            except asyncio.TimeoutError:
                # No events, keep looping
                continue
            except Exception as e:
                logger.error(f"Dispatch worker error: {e}", exc_info=True)
    
    async def start(self) -> None:
        """Start the event dispatch worker."""
        if self._running:
            return
        self._running = True
        self._dispatch_task = asyncio.create_task(self._dispatch_worker())
        logger.info("Event bus started")
    
    async def stop(self) -> None:
        """Stop the event dispatch worker and wait for pending events."""
        self._running = False
        try:
            await asyncio.wait_for(self._dispatch_task, timeout=5.0)
        except asyncio.TimeoutError:
            logger.warning("Event bus dispatch worker did not stop in time")
        except asyncio.CancelledError:
            pass
        
        # Wait for remaining events to be processed
        try:
            await asyncio.wait_for(self._queue.join(), timeout=2.0)
        except asyncio.TimeoutError:
            logger.warning("Some events were not processed")
        
        logger.info("Event bus stopped")


# Singleton instance
_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """Get or create the global event bus instance."""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


# Common event helper functions
def event_face_detected(confidence: float, head_pose: Dict, bbox: tuple) -> Event:
    return Event(
        topic="camera.face_detected",
        payload={"confidence": confidence, "head_pose": head_pose, "bbox": bbox}
    )


def event_face_lost() -> Event:
    return Event(topic="camera.face_lost", payload={})


def event_object_presented(bbox: tuple, object_id: str = "new") -> Event:
    return Event(
        topic="camera.object_presented",
        payload={"bbox": bbox, "object_id": object_id}
    )


def event_speech_received(text: str, confidence: float = 1.0) -> Event:
    return Event(
        topic="audio.speech_received",
        payload={"text": text, "confidence": confidence}
    )


def event_listening_active(active: bool) -> Event:
    return Event(
        topic="audio.listening_active",
        payload={"active": active}
    )


def event_llm_response(speech: str, gesture: str, light: Dict, sfx: Optional[str], observe_trigger: bool) -> Event:
    return Event(
        topic="llm.response_generated",
        payload={
            "speech": speech,
            "gesture": gesture,
            "light": light,
            "sfx": sfx,
            "observe_trigger": observe_trigger
        }
    )


def event_vlm_object_analyzed(label: str, description: str, object_id: str = "0") -> Event:
    return Event(
        topic="vlm.object_analyzed",
        payload={"label": label, "description": description, "object_id": object_id}
    )


def event_state_changed(old_state: str, new_state: str) -> Event:
    return Event(
        topic="orchestrator.state_changed",
        payload={"old_state": old_state, "new_state": new_state}
    )
