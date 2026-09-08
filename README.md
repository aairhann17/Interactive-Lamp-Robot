# Interactive Lamp Robot

A 5-DOF lamp robot character that reacts to people with vision, voice, motion, light, and sound. The project is built for a live demo and for portfolio review, so it has a simple local run path, a browser simulator, and a documented path to real hardware.

## What It Does

The robot is designed to do four things well:

1. Notice a person with the camera.
2. Respond with movement, light, and sound.
3. Listen and speak back in a short conversation.
4. Remember an object it saw earlier and refer to it later.

The app keeps those actions coordinated through a small state machine. In practice, that means the robot can move from waiting, to greeting, to listening, to observing, and back to idle in a way that feels intentional.

## How It Works

The camera and microphone feed the robot's control center. That control center decides what state the robot should be in, then tells the rest of the system what to do.

- Face detection decides when the robot should pay attention.
- Speech-to-text turns spoken words into text.
- A dialogue model turns the text into a coordinated reply.
- The output layer drives motion, light, sound, and the browser simulator.

If you switch to real hardware, the same robot commands are sent over serial to the microcontroller instead of only being shown in the browser.

## Quick Start

The default setup is meant to run cleanly on a fresh Windows machine.

1. Open the repo in VS Code.
2. Create and activate a Python virtual environment.
3. Install dependencies with `pip install -r requirements.txt`.
4. Run `run.ps1` on Windows, or run `python main.py` directly.
5. Open the simulator in your browser if it does not open automatically.
6. Use the simulator buttons to trigger a single state or run the full demo.

If you want the app to fail fast when a required API key or device is missing, run:

```powershell
python main.py --strict-startup
```

## Simulator

The browser simulator is the easiest way to see the project working end to end.

- `simulator/index.html` opens the visual demo.
- `simulator/app.js` updates the lamp based on messages from Python.
- `sim_bridge/websocket_server.py` sends the robot state into the browser.

The simulator includes manual controls and a full demo sequence, so it can show the robot's behavior even on a machine without real hardware.

## Real Hardware Path

Real hardware uses a small JSON-over-serial protocol defined in [hardware/device_protocol.py](hardware/device_protocol.py).

The message includes:

- `protocol`: the version name for the device contract
- `component`: which part of the robot should act
- `command`: what that part should do
- `payload`: any details needed for the command

The repo also includes a starter firmware sketch at [firmware/lamp_robot_firmware.ino](firmware/lamp_robot_firmware.ino). It shows how the microcontroller can read those commands and route them to motion, lighting, and sound handlers.

## Project Layout

- [main.py](main.py): app entry point
- [orchestrator/](orchestrator): robot control flow and state machine
- [perception/](perception): face and object detection plus visual analysis
- [speech/](speech): speech-to-text and text-to-speech helpers
- [dialogue/](dialogue): builds the robot's spoken reply
- [expression/](expression): motion, light, and sound output helpers
- [memory/](memory): remembers objects the robot has seen
- [sim_bridge/](sim_bridge): browser bridge for the simulator
- [simulator/](simulator): visual front end for the demo
- [demo/](demo): scripted end-to-end interaction demo
- [firmware/](firmware): starter code for the device side

## Deployment Target

The current deployment target is a supervised Python process that talks to the simulator bridge port in `config.yaml`.

- Local development: `python main.py`
- Startup check for deployment: `python main.py --strict-startup`
- Default browser bridge port: `8080`
- Recommended supervision: `systemd` on Linux or NSSM on Windows
- Restart policy: restart on crash, restart on boot, and keep logs for troubleshooting

## Release Smoke Test

Run this before tagging a release:

1. Start the app in strict mode.
2. Open `simulator/index.html`.
3. Confirm the browser says it is connected to the bridge.
4. Click `Notice` and verify the state, motion, and light panels change.
5. Click `Run Full Demo` and confirm the sequence reaches `IDLE` again.

## Notes

- The default mode is simulator-first so the repo is easy to demo on a fresh machine.
- Real hardware mode should only be enabled when the serial device is connected.
- `config.yaml` holds the runtime settings, while environment variables should hold secrets.
