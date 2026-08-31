"""Scene memory for object tracking and recall."""

import asyncio
import json
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class ObjectRecord:
    label: str
    description: str
    first_seen: str
    last_seen: str
    notes: Optional[Dict[str, Any]] = None


class SceneMemory:
    """In-memory object store with JSON-friendly persistence."""

    def __init__(self) -> None:
        self._objects: List[Dict[str, Any]] = []

    async def store_object(self, label: str, description: str, notes: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        now = datetime.utcnow().isoformat(timespec="seconds")
        record = {
            "label": label,
            "description": description,
            "first_seen": now,
            "last_seen": now,
            "notes": notes or {},
        }
        existing = next((item for item in self._objects if item.get("label") == label), None)
        if existing:
            existing["description"] = description
            existing["last_seen"] = now
            existing["notes"] = notes or existing.get("notes", {})
            return existing

        self._objects.append(record)
        return record

    async def recall(self, label: Optional[str] = None) -> List[Dict[str, Any]]:
        await asyncio.sleep(0)
        if label:
            return [obj for obj in self._objects if obj.get("label", "").lower() == label.lower()]
        return list(self._objects)

    async def clear(self) -> None:
        self._objects.clear()
