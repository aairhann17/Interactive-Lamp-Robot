"""Local face detection using OpenCV and MediaPipe when available."""

import logging
from typing import Any, Dict, Optional

try:
    import cv2  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    cv2 = None

try:
    import mediapipe as mp  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    mp = None


logger = logging.getLogger(__name__)


class FaceDetector:
    """Minimal face detector used to detect engagement cues."""

    def __init__(
        self,
        device_index: int = 0,
        min_detection_confidence: float = 0.5,
    ) -> None:
        self.device_index = device_index
        self.min_detection_confidence = min_detection_confidence
        self.camera = None
        self.is_available = cv2 is not None and mp is not None
        self._face_detector = None
        self._face_mesh = None

        if self.is_available:
            try:
                self._face_detector = mp.solutions.face_detection.FaceDetection(
                    min_detection_confidence=min_detection_confidence
                )
            except Exception as exc:  # pragma: no cover - environment dependent
                logger.warning("MediaPipe face detection could not initialize: %s", exc)
                self.is_available = False

    async def start(self) -> None:
        if not self.is_available:
            return
        if self.camera is None:
            self.camera = cv2.VideoCapture(self.device_index)

    async def stop(self) -> None:
        if self.camera is not None:
            self.camera.release()
            self.camera = None

    def detect(self, frame=None) -> Dict[str, Any]:
        """Return a structured face-detection payload.

        When the camera or dependency stack is unavailable, this returns a safe
        false-positive-free payload that allows orchestration code to degrade
        gracefully.
        """
        if not self.is_available:
            return {
                "detected": False,
                "confidence": 0.0,
                "head_pose": {"yaw": 0.0, "pitch": 0.0, "roll": 0.0},
                "bbox": None,
                "source": "unavailable",
            }

        if frame is None:
            if self.camera is None:
                return {
                    "detected": False,
                    "confidence": 0.0,
                    "head_pose": {"yaw": 0.0, "pitch": 0.0, "roll": 0.0},
                    "bbox": None,
                    "source": "camera_unavailable",
                }
            ok, frame = self.camera.read()
            if not ok or frame is None:
                return {
                    "detected": False,
                    "confidence": 0.0,
                    "head_pose": {"yaw": 0.0, "pitch": 0.0, "roll": 0.0},
                    "bbox": None,
                    "source": "read_failed",
                }

        try:
            results = self._face_detector.process(frame)
        except Exception as exc:  # pragma: no cover - runtime-dependent
            logger.warning("Face detection processing failed: %s", exc)
            return {
                "detected": False,
                "confidence": 0.0,
                "head_pose": {"yaw": 0.0, "pitch": 0.0, "roll": 0.0},
                "bbox": None,
                "source": "processing_failed",
            }

        if not results or not results.detections:
            return {
                "detected": False,
                "confidence": 0.0,
                "head_pose": {"yaw": 0.0, "pitch": 0.0, "roll": 0.0},
                "bbox": None,
                "source": "processed",
            }

        best = results.detections[0]
        score = best.score[0].value if best.score else 0.0
        bbox = best.location_data.relative_bounding_box
        relative_bbox = (
            bbox.xmin,
            bbox.ymin,
            bbox.width,
            bbox.height,
        )

        # Head pose is approximated from relative face placement in frame.
        head_pose = {
            "yaw": round((bbox.xmin - 0.5) * 90.0, 2),
            "pitch": round((bbox.ymin - 0.5) * 60.0, 2),
            "roll": 0.0,
        }

        return {
            "detected": True,
            "confidence": float(score),
            "head_pose": head_pose,
            "bbox": relative_bbox,
            "source": "mediapipe",
        }
