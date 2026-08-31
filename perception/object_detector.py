"""Heuristic object detection for objects presented to the robot."""

import logging
from typing import Any, Dict, Optional, Tuple

try:
    import cv2  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    cv2 = None


logger = logging.getLogger(__name__)


class ObjectDetector:
    """Detect large presented objects or motion events in camera frames."""

    def __init__(self, threshold: int = 5000, history_size: int = 5) -> None:
        self.threshold = threshold
        self.history_size = history_size
        self.background = None
        self.is_available = cv2 is not None

    async def start(self) -> None:
        if cv2 is not None:
            self.background = cv2.createBackgroundSubtractorMOG2(
                history=self.history_size,
                varThreshold=25,
                detectShadows=True,
            )

    async def stop(self) -> None:
        self.background = None

    def detect(self, frame=None) -> Dict[str, Any]:
        if cv2 is None or frame is None:
            return {
                "detected": False,
                "confidence": 0.0,
                "bbox": None,
                "source": "unavailable",
            }

        if self.background is None:
            self.background = cv2.createBackgroundSubtractorMOG2(
                history=self.history_size,
                varThreshold=25,
                detectShadows=True,
            )

        try:
            fgmask = self.background.apply(frame)
            _, thresh = cv2.threshold(fgmask, 200, 255, cv2.THRESH_BINARY)
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        except Exception as exc:  # pragma: no cover - runtime-dependent
            logger.warning("Object detection processing failed: %s", exc)
            return {
                "detected": False,
                "confidence": 0.0,
                "bbox": None,
                "source": "processing_failed",
            }

        if not contours:
            return {
                "detected": False,
                "confidence": 0.0,
                "bbox": None,
                "source": "processed",
            }

        best_contour = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(best_contour)

        if area < self.threshold:
            return {
                "detected": False,
                "confidence": 0.0,
                "bbox": None,
                "source": "processed",
            }

        x, y, w, h = cv2.boundingRect(best_contour)
        confidence = min(1.0, area / (self.threshold * 2.0))

        return {
            "detected": True,
            "confidence": float(confidence),
            "bbox": (x, y, w, h),
            "source": "opencv",
        }
