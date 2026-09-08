from hardware.robot_hardware import create_robot_hardware


def test_simulator_hardware_reports_null_camera_readiness():
    hardware = create_robot_hardware(mode="simulator")

    assert hardware.mode == "simulator"
    readiness = hardware.probe_startup()

    assert readiness["camera_available"] is False
    assert "camera is using the null driver" in readiness["details"]


def test_real_mode_without_serial_falls_back_to_simulator_stack():
    hardware = create_robot_hardware(mode="real", config={})

    assert hardware.mode == "simulator"