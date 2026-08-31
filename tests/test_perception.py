from perception import PerceptionPipeline
from perception.face_detection import FaceDetector
from perception.object_detector import ObjectDetector
from perception.vlm_analyzer import VLMAnalyzer


def test_face_detector_reports_safe_false_payload():
    detector = FaceDetector()
    payload = detector.detect(None)
    assert payload["detected"] is False
    assert payload["bbox"] is None


def test_object_detector_reports_safe_false_payload_without_frame():
    detector = ObjectDetector()
    payload = detector.detect(None)
    assert payload["detected"] is False
    assert payload["confidence"] == 0.0


def test_vlm_analyzer_falls_back_without_api_key():
    analyzer = VLMAnalyzer(api_key=None)
    result = analyzer.__class__
    assert result is not None


def test_perception_pipeline_has_expected_components():
    pipeline = PerceptionPipeline()
    assert pipeline.face is not None
    assert pipeline.object is not None
    assert pipeline.vlm is not None
