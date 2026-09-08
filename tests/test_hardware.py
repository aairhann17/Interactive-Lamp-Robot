from hardware.robot_hardware import create_robot_hardware
from hardware.device_protocol import (
    PROTOCOL_NAME,
    build_health_command,
    build_lighting_command,
    build_motion_command,
    build_sfx_command,
)


def test_simulator_hardware_reports_null_camera_readiness():
    hardware = create_robot_hardware(mode="simulator")

    assert hardware.mode == "simulator"
    readiness = hardware.probe_startup()

    assert readiness["camera_available"] is False
    assert "camera is using the null driver" in readiness["details"]


def test_real_mode_without_serial_falls_back_to_simulator_stack():
    hardware = create_robot_hardware(mode="real", config={})

    assert hardware.mode == "real"
    readiness = hardware.probe_startup()

    assert readiness["serial_available"] is False


def test_real_mode_readiness_reports_missing_serial_port_details():
    hardware = create_robot_hardware(
        mode="real",
        config={"serial_port": "COM99", "serial_baudrate": 115200, "camera_index": 0},
    )

    readiness = hardware.probe_startup()

    assert readiness["serial_available"] is False
    assert any("serial port" in detail for detail in readiness["details"])


def test_device_protocol_envelopes_have_expected_shape():
    motion = build_motion_command("attention_grab", 800)
    lighting = build_lighting_command("NOTICE", [255, 255, 255], 0.9)
    sfx = build_sfx_command("engagement_chime")
    health = build_health_command()

    assert motion["protocol"] == PROTOCOL_NAME
    assert motion["component"] == "motion"
    assert motion["command"] == "execute_gesture"
    assert motion["payload"]["gesture"] == "attention_grab"

    assert lighting["component"] == "lighting"
    assert lighting["payload"]["state"] == "NOTICE"

    assert sfx["component"] == "sfx"
    assert sfx["payload"]["sound"] == "engagement_chime"

    assert health["component"] == "system"
    assert health["command"] == "health_check"