"""Perception package for local and cloud vision analysis."""

from perception.face_detection import FaceDetector
from perception.object_detector import ObjectDetector
from perception.vlm_analyzer import VLMAnalyzer


class PerceptionPipeline:
    """Convenience wrapper that groups the robot's perception subsystems."""

    def __init__(
        self,
        camera_index: int = 0,
        min_detection_confidence: float = 0.5,
        object_threshold: int = 5000,
    ) -> None:
        self.face = FaceDetector(
            device_index=camera_index,
            min_detection_confidence=min_detection_confidence,
        )
        self.object = ObjectDetector(threshold=object_threshold)
        self.vlm = VLMAnalyzer()

    async def start(self) -> None:
        await self.face.start()
        await self.object.start()

    async def stop(self) -> None:
        await self.face.stop()
        await self.object.stop()

    def detect_face(self, frame=None):
        return self.face.detect(frame)

    def detect_object(self, frame=None):
        return self.object.detect(frame)

    async def analyze_object(self, frame=None, user_prompt: str = ""):
        return await self.vlm.analyze_object(frame=frame, user_prompt=user_prompt)


__all__ = ["PerceptionPipeline", "FaceDetector", "ObjectDetector", "VLMAnalyzer"]
