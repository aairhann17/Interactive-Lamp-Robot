from hardware.robot_hardware import create_robot_hardware


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