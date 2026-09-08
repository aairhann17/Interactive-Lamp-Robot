"""Face detection for the robot.

This file helps the lamp notice when a person is in front of it.
"""

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
    """Look for a face so the robot knows when to pay attention."""

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
        self._fallback_cascade = None

        if self.is_available:
            try:
                if hasattr(mp, "solutions") and hasattr(mp.solutions, "face_detection"):
                    self._face_detector = mp.solutions.face_detection.FaceDetection(
                        min_detection_confidence=min_detection_confidence
                    )
                else:
                    logger.warning(
                        "MediaPipe 'solutions.face_detection' is unavailable; using OpenCV cascade fallback"
                    )
            except Exception as exc:  # pragma: no cover - environment dependent
                logger.warning("MediaPipe face detection could not initialize: %s", exc)

        if cv2 is not None:
            try:
                cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
                self._fallback_cascade = cv2.CascadeClassifier(cascade_path)
                if self._fallback_cascade.empty():
                    self._fallback_cascade = None
            except Exception:  # pragma: no cover - environment dependent
                self._fallback_cascade = None

        self.is_available = self._face_detector is not None or self._fallback_cascade is not None

    @staticmethod
    def _empty_payload(source: str) -> Dict[str, Any]:
        return {
            "detected": False,
            "confidence": 0.0,
            "head_pose": {"yaw": 0.0, "pitch": 0.0, "roll": 0.0},
            "bbox": None,
            "source": source,
        }

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
            return self._empty_payload("unavailable")

        if frame is None:
            if self.camera is None:
                return self._empty_payload("camera_unavailable")
            ok, frame = self.camera.read()
            if not ok or frame is None:
                return self._empty_payload("read_failed")

        # Fallback path when MediaPipe detection is unavailable in this build.
        if self._face_detector is None and self._fallback_cascade is not None:
            try:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = self._fallback_cascade.detectMultiScale(
                    gray,
                    scaleFactor=1.1,
                    minNeighbors=5,
                    minSize=(40, 40),
                )
            except Exception as exc:  # pragma: no cover - runtime-dependent
                logger.warning("OpenCV fallback face detection failed: %s", exc)
                return self._empty_payload("fallback_processing_failed")

            if len(faces) == 0:
                return self._empty_payload("opencv_fallback")

            x, y, w, h = faces[0]
            frame_h, frame_w = gray.shape[:2]
            xmin = x / frame_w
            ymin = y / frame_h
            width = w / frame_w
            height = h / frame_h
            head_pose = {
                "yaw": round((xmin - 0.5) * 90.0, 2),
                "pitch": round((ymin - 0.5) * 60.0, 2),
                "roll": 0.0,
            }
            return {
                "detected": True,
                "confidence": 0.6,
                "head_pose": head_pose,
                "bbox": (xmin, ymin, width, height),
                "source": "opencv_fallback",
            }

        try:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self._face_detector.process(rgb)
        except Exception as exc:  # pragma: no cover - runtime-dependent
            logger.warning("Face detection processing failed: %s", exc)
            return self._empty_payload("processing_failed")

        if not results or not results.detections:
            return self._empty_payload("processed")

        best = results.detections[0]
        score = float(best.score[0]) if best.score else 0.0
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
