import os

import pytest

from orchestrator.coordinator import RobotOrchestrator


def test_validate_startup_passes_when_not_strict():
    orchestrator = RobotOrchestrator()
    orchestrator.validate_startup(strict=False)


def test_validate_startup_fails_fast_when_required_keys_missing(tmp_path, monkeypatch):
    for key in ("DEEPGRAM_API_KEY", "ANTHROPIC_API_KEY", "ELEVENLABS_API_KEY"):
        monkeypatch.delenv(key, raising=False)

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "\n".join(
            [
                "startup:",
                "  strict: true",
                "  require_camera: false",
                "  required_api_keys:",
                "    - DEEPGRAM_API_KEY",
                "    - ANTHROPIC_API_KEY",
                "    - ELEVENLABS_API_KEY",
            ]
        )
    )

    orchestrator = RobotOrchestrator(config_path=str(config_path))

    with pytest.raises(RuntimeError, match="Missing API keys"):
        orchestrator.validate_startup()