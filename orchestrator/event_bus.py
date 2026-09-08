"""
Message hub for the robot.

This file lets the camera, speech system, memory, and robot actions send short
messages to each other without having to know who will read them.
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Callable, Any, Dict, List, Optional


logger = logging.getLogger(__name__)


@dataclass
class Event:
    """A small message that says what happened and carries the details."""
    topic: str
    payload: Dict[str, Any]
    
    def __repr__(self) -> str:
        return f"Event(topic={self.topic}, payload={self.payload})"


class EventBus:
    """
    Message system for the robot.

    It carries events like "a face was seen," "speech was heard," or "the
    robot changed state" to any part of the app that wants to react.
    """
    
    def __init__(self):
        self._queue: asyncio.Queue[Event] = asyncio.Queue()
        self._subscribers: Dict[str, List[Callable]] = {}
        self._running = False
    
    def subscribe(self, topic: str, callback: Callable[[Event], None]) -> Callable:
        """Register a function that should run when a specific event happens."""
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
        """Send a message into the event system."""
        await self._queue.put(event)
    
    async def _dispatch_worker(self) -> None:
        """Background worker that forwards each message to the right listeners."""
        while self._running:
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                
                # Send the message to listeners who want to see everything.
                if "*" in self._subscribers:
                    for callback in self._subscribers["*"]:
                        try:
                            result = callback(event)
                            if asyncio.iscoroutine(result):
                                await result
                        except Exception as e:
                            logger.exception(f"Error in wildcard subscriber: {e}", exc_info=True)
                
                # Then send it to listeners who asked for this exact topic.
                if event.topic in self._subscribers:
                    for callback in self._subscribers[event.topic]:
                        try:
                            result = callback(event)
                            if asyncio.iscoroutine(result):
                                await result
                        except Exception as e:
                            logger.exception(
                                f"Error in subscriber for {event.topic}: {e}",
                                exc_info=True
                            )
                
                self._queue.task_done()
            
            except asyncio.TimeoutError:
                # No events, keep looping
                continue
            except Exception as e:
                logger.exception(f"Dispatch worker error: {e}", exc_info=True)
    
    async def start(self) -> None:
        """Turn on the message worker."""
        if self._running:
            return
        self._running = True
        self._dispatch_task = asyncio.create_task(self._dispatch_worker())
        logger.info("Event bus started")
    
    async def stop(self) -> None:
        """Shut down the message worker after queued work is handled."""
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
    """Get the shared message hub used by the whole app."""
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
