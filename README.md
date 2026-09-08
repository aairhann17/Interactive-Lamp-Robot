# Interactive Lamp Robot Architecture

## Overview
A 5-DOF expressive lamp robot character that engages with humans through vision, voice, motion, light, and sound. The system uses a local finite-state machine (FSM) as the orchestrator, with selective cloud APIs for specialized perception and language tasks.

## System Architecture

### 1. **Orchestrator / Core Logic** (`orchestrator.py`)
**Role:** Central state machine and event coordinator

**State Machine:**
```
IDLE
  ↓ (face detected)
NOTICE (play attention sfx, eye brightens)
  ↓ (face sustained, body orient toward)
GREET (friendly gesture + voice greeting)
  ↓ (success OR timeout)
LISTEN/CONVERSE (microphone active, streaming STT)
  ↓ (user speech received)
CONVERSE (Claude LLM generates response)
  ↓ (response includes observation cue)
OBSERVE (VLM triggered if object/hand detected)
  ↓ (object analyzed, memory updated)
DISENGAGE (face lost OR timer expires)
  ↓ (farewell gesture, light dim)
IDLE
```

**Event Bus:**
- `asyncio.Queue`-based pub/sub
- Topics: `camera.face_detected`, `camera.object_presented`, `audio.speech_received`, `llm.response`, `memory.updated`
- Subscribers: perception modules, response generator, output executors

### 2. **Perception Pipeline**

#### 2.1 Local Perception (MediaPipe Face Landmarker)
**Module:** `perception/face_detection.py`
- **Input:** Laptop camera (continuous 30 FPS)
- **Output:** Face presence, head pose (yaw, pitch, roll), confidence
- **Decision:** Engagement trigger (face appears → NOTICE), Disengagement (face absent > 5 sec → DISENGAGE)
- **Processing:** Local-only, CPU or GPU via MediaPipe

#### 2.2 Object Presentation Heuristic
**Module:** `perception/object_detector.py`
- **Input:** Camera frame
- **Logic:** Detect new large object, hand approach, or voice cue ("look at this")
- **Output:** `{ object_bbox, presentation_confidence }`
- **Decision:** Triggers OBSERVE state if confidence > threshold

#### 2.3 Cloud Vision-Language Model
**Module:** `perception/vlm_analyzer.py`
- **Trigger:** OBSERVE state, only when object detected
- **Input:** Single cropped frame (object ROI) + optional user context ("what is this?")
- **API:** Claude vision or GPT-4V
- **Output:** Object label, attributes, function/purpose
- **Data Privacy:** Only the cropped object frame sent to cloud; raw camera never leaves device
- **Caching:** Store results in memory to avoid duplicate API calls

### 3. **Speech System**

#### 3.1 Speech-to-Text (STT)
**Module:** `speech/stt.py`
- **API:** Deepgram (low-latency streaming) or OpenAI Whisper API
- **Activation:** Only when FSM is in `LISTEN` state
- **Input:** Microphone stream (local buffering)
- **Output:** Transcribed text, optional confidence
- **Data Privacy:** Audio streamed only during LISTEN; no recording stored

#### 3.2 Speech-to-Gesture-to-Text (LLM Dialogue)
**Module:** `dialogue/conversation.py`
- **API:** Claude 3.5 Sonnet
- **Input:** Transcribed user text + scene context + memory
- **Output:** Structured JSON
  ```json
  {
    "speech": "Sure! That's a coffee mug. I love how warm colors make me feel...",
    "gesture": "warm_embrace",
    "light": { "hue": 45, "saturation": 0.8, "brightness": 0.9 },
    "sfx": "subtle_chime",
    "observe_trigger": false
  }
  ```
- **Key Design:** Single LLM call drives all modalities → cohesive, coordinated expression

#### 3.3 Text-to-Speech (TTS)
**Module:** `speech/tts.py`
- **Primary API:** ElevenLabs (expressive voices, emotion control)
- **Fallback:** Piper (offline, Mozilla-trained, runs locally)
- **Input:** Speech text + optional emotional tone
- **Output:** Audio stream queued to speaker

### 4. **Expression Outputs**

#### 4.1 Motion (5-DOF Gestures)
**Module:** `expression/gestures.py`
- **Gesture Library:** Named actions
  - `neutral` — idle pose
  - `attention_grab` — rapid base rotation + lift pulse
  - `warm_embrace` — slow arm extension + tilt
  - `curious_inspect` — head tilt + extension (approach object)
  - `confused_shrug` — oscillate head
  - `farewell_wave` — extended base rotation
- **Representation:** Joint target angles (5 DOF) + duration + easing function
- **Output:** Serial protocol (USB/TCP) to simulator or real hardware
- **Interpolation:** Smooth cubic spline over duration

#### 4.2 Light Expression
**Module:** `expression/lighting.py`
- **State → Color Mapping:**
  - `IDLE` → dim, cool blue
  - `NOTICE` → bright white (alert)
  - `GREET` → warm yellow/orange
  - `LISTEN` → animated pulse (listening state)
  - `OBSERVE` → saturated, focused color
  - `CONVERSE` → responsive color shift per emotion
  - `DISENGAGE` → fade to dark
- **Implementation:** RGB LED or WebGL lighting in simulator
- **Sync:** Timed to gesture start for emotional coherence

#### 4.3 Sound Effects
**Module:** `expression/sfx.py`
- **Library:** Short clips (<2 sec) via `pygame.mixer`
  - `engagement_chime` — ascending bell tone (NOTICE → GREET)
  - `thinking_beep` — soft processing sound (waiting for STT)
  - `success_ding` — confirmation tone (object recognized)
  - `confused_chirp` — uncertain sound
- **Trigger:** Per orchestrator state or LLM output

#### 4.4 Music / Emotional Stings
**Module:** `expression/music.py`
- **Stings:** Short (4–8 bar) musical phrases for key emotional moments
  - Warm greeting sting
  - Curious exploration sting
  - Confident/understanding sting
- **Library:** Pre-composed or AI-generated via Suno/Udio, cached locally
- **Playback:** Overlaid under dialogue or during transitions

### 5. **Memory & Scene Understanding**

**Module:** `memory/scene_graph.py`
- **Storage:** SQLite table or in-session dict
  ```sql
  CREATE TABLE objects (
    id INTEGER PRIMARY KEY,
    label TEXT,
    description TEXT,
    first_observed TIMESTAMP,
    last_observed TIMESTAMP,
    visual_features TEXT -- JSON: {color, shape, size, position}
  );
  ```
- **Update:** After VLM analysis, before CONVERSE state
- **Query:** Dialogue module can retrieve "have you seen a red object?" → searches memory
- **Lifecycle:** Persist across session; clear on restart
- **Future Scale:** Vector embeddings + similarity search (not implemented at MVP)

### 6. **Simulated Robot Body (Three.js + URDF)**

#### 6.1 Browser Simulator
**Files:**
- `simulator/index.html` — entry point
- `simulator/app.js` — Three.js scene, camera, lighting, controls
- `simulator/urdf_model.urdf` — 5-DOF lamp kinematic chain

**Features:**
- Load URDF model
- 5-DOF joint control sliders
- Real-time gesture playback
- Synchronized LED lighting visualization
- WebSocket connection to Python orchestrator

#### 6.2 Python ↔ Browser WebSocket
**Module:** `sim_bridge/websocket_server.py`
- **Protocol:**
  ```json
  // Python → Browser (joint command)
  {
    "type": "motion",
    "joints": {
      "base_rotation": 45.0,
      "lift": 30.0,
      "extension": 20.0,
      "head_tilt": -15.0,
      "eye_pan": 0.0
    },
    "duration_ms": 1000,
    "easing": "cubic-inout"
  }
  
  // Python → Browser (lighting)
  {
    "type": "lighting",
    "rgb": [255, 150, 50],
    "duration_ms": 500,
    "breathing": false
  }
  ```

**Run modes:**
- Persistent bridge server: `python -m sim_bridge.run_server`
- Demo publisher against an external bridge: `python demo/interaction_demo.py --bridge-url ws://127.0.0.1:8765`
- Default demo mode still starts its own local bridge when `--bridge-url` is omitted

### 7. **Gesture Choreography & Trajectory Planning**

**Module:** `choreography/interpolation.py`
- Accepts gesture name + duration
- Looks up joint targets from gesture library
- Generates smooth spline from current joint state → target state
- Evaluates spline at 30 Hz → stream to simulator
- Supports parallel execution (e.g., light + motion at same time)

## Data Flow Diagram

```
┌─────────────┐
│   Camera    │
└──────┬──────┘
       │ (30 FPS)
       ▼
┌──────────────────────┐      ┌───────────────┐
│ MediaPipe Face       │────→ │ Orchestrator  │
│ Detection            │      │ FSM           │
└──────────────────────┘      │               │
                               │ (event bus)   │
┌──────────────────┐      ┌───┴──────────┬────┘
│ Object Detection │─────→│              │
│ (heuristic)      │      │              │
└──────────────────┘      │              │
                          │              │
┌──────────────────┐      │              │
│  Microphone      │──────→  LISTEN      │
│  (STT stream)    │      │  state       │
└──────────────────┘      │              │
        │                 │              │
        └─ [DEEPGRAM] ────→│              │
                          │              │
                   [CLAUDE VLM] ◄────────│ (object frame)
                        │               │
                   [CLAUDE LLM] ◄────────│ (dialogue)
                        │               │
                        └───────┬───────┘
                                │
                    ┌───────────┼───────────┐
                    ▼           ▼           ▼
              ┌─────────┐ ┌─────────┐ ┌─────────┐
              │ Gesture │ │ Lighting│ │  TTS    │
              │ Executor│ │ Executor│ │ Executor│
              └────┬────┘ └────┬────┘ └────┬────┘
                   │           │           │
                   └───────┬───┴───┬───────┘
                           │       │
                   ┌───────▼─┐   ┌─▼──────┐
                   │WebSocket│   │Speaker │
                   │(Browser)│   │(Audio) │
                   └────┬────┘   └────────┘
                        │
                   ┌────▼─────┐
                   │Three.js   │
                   │Simulator  │
                   │(URDF)     │
                   └──────────┘
```

## Data Privacy & Cloud Decisions

| Component | Local? | Cloud? | Reasoning |
|-----------|--------|--------|-----------|
| Face detection | ✓ | — | MediaPipe runs locally; always-on low-latency |
| Object detection | ✓ | — | Simple heuristic (motion, hand detection) |
| Gesture planning | ✓ | — | FSM + kinematics; no ML needed |
| STT | — | ✓ (Deepgram) | Streaming required; local Whisper slower |
| VLM (object analyze) | — | ✓ (Claude) | One-shot, triggered only; complex reasoning |
| LLM (dialogue) | — | ✓ (Claude) | Conversational; state-of-art not worth local |
| TTS | ⚪ | ✓ (ElevenLabs primary) | Expressive voices; fallback to Piper |
| Memory storage | ✓ | — | SQLite local; no sync across devices |
| Motion output | ✓ | — | Local interpolation → simulator/hardware |

**Key Principle:** Minimize cloud data leakage. Audio only during LISTEN; camera only sends object ROI to VLM; all orchestration decisions made locally.

## Future Extensions (not MVP)

1. **Vector Search Memory:** Embed object descriptions; allow fuzzy retrieval ("red thing from before")
2. **Multi-modal Gesture Synthesis:** Learn new gestures from video or user demonstration
3. **Real Robot Hardware:** Replace WebSocket simulator with actual motor control (e.g., ROS 2)
4. **Persistent State:** Save memory/learned preferences across sessions
5. **Multi-agent Collaboration:** Multiple robots interacting with each other
6. **Fine-tuned Local LLM:** Use a smaller model (Mistral, Phi) for dialogue to reduce cloud dependency

## Completion Checklist

Use this as the definition of "ready to deploy":

- Hardware layer exists for motion, lighting, audio input, audio output, and camera selection.
- Simulator mode and real-device mode can be selected from config without changing application code.
- Manual state controls work end to end in the browser simulator.
- Full demo preset runs through notice, greet, listen, converse, observe, disengage, and idle.
- Face detection, object detection, STT, TTS, and VLM all have deterministic fallback behavior.
- Startup checks fail fast when a required device, API key, or service is missing.
- Configuration is documented and all secrets come from environment variables.
- Tests pass in CI and cover the main state transitions and fallback paths.
- Logging is structured enough to debug a failed demo run quickly.
- Packaging and launch instructions are repeatable from a clean machine.
- Deployment target is defined, including ports, process supervision, and restart policy.
- The app has one documented smoke test that a human can run before a release.

## Deployment Target

The current deployment target is a supervised Python process that listens on the simulator bridge port configured in `config.yaml`.

- Local development: `python main.py`
- Deploy-oriented startup check: `python main.py --strict-startup`
- Browser simulator bridge: `8080` by default
- Process supervision: run the Python process under a restart-capable supervisor such as `systemd` on Linux or NSSM on Windows
- Restart policy: restart on crash, restart on boot, and keep logs for postmortem inspection

## Release Smoke Test

Run this before tagging a release:

1. Start the app in strict mode: `python main.py --strict-startup`
2. Open the browser simulator at `simulator/index.html`.
3. Confirm the bridge shows `Connected to simulator bridge.`
4. Click `Notice`, then verify the `State`, `Motion`, and `Light` cards update.
5. Click `Run Full Demo`, then verify the sequence completes through `IDLE` and the `Speech` and `Memory` cards change during the run.

## Repository Structure

```
Interactive-Lamp-Robot/
├── ARCHITECTURE.md (this file)
├── requirements.txt
├── config.yaml
├── main.py (entry point)
│
├── orchestrator/
│   ├── __init__.py
│   ├── fsm.py (state machine)
│   ├── event_bus.py (pub/sub)
│   └── coordinator.py (tie everything together)
│
├── perception/
│   ├── face_detection.py (MediaPipe)
│   ├── object_detector.py (heuristic)
│   └── vlm_analyzer.py (cloud vision)
│
├── speech/
│   ├── stt.py (Deepgram/Whisper)
│   └── tts.py (ElevenLabs/Piper)
│
├── dialogue/
│   └── conversation.py (Claude)
│
├── expression/
│   ├── gestures.py (gesture library + interpolation)
│   ├── lighting.py (color mappings)
│   ├── sfx.py (sound effects)
│   └── music.py (emotional stings)
│
├── memory/
│   └── scene_graph.py (object storage)
│
├── sim_bridge/
│   └── websocket_server.py (Python → Browser)
│
├── simulator/
│   ├── index.html
│   ├── app.js
│   ├── style.css
│   └── urdf_model.urdf
│
└── demo/
    └── demo_interaction.py (full end-to-end demo)
```

## Design Decisions & Tradeoffs

### 1. **FSM over Event Sourcing**
- ✓ **Simple, auditable:** State is explicit; easy to debug
- ✓ **Real-time responsiveness:** Immediate state transitions
- ✗ **Limited history:** No full replay; mitigated by logging

### 2. **Cloud LLM + Local FSM**
- ✓ **Best of both:** Cloud for reasoning, local for immediate decisions
- ✗ **Latency:** ~500ms STT + 1s LLM = ~1.5s response time (acceptable for character)
- ✗ **Dependency:** No cloud = robot silent; Piper TTS fallback helps

### 3. **Gesture Library vs. IK Solver**
- ✓ **Simplicity:** Pre-defined gestures easy to author and test
- ✗ **Flexibility:** Can't reach arbitrary point in space
- ✓ **For 5-DOF lamp:** Named poses sufficient; IK adds complexity

### 4. **Browser Simulator over ROS/Gazebo**
- ✓ **Accessibility:** No ROS installation; works on any laptop
- ✓ **Visual fidelity:** Three.js WebGL good for real-time viz
- ✗ **Physics:** No realistic dynamics; acceptable for character demo
- *Note:* WebSocket bridge makes ROS/Gazebo swap-in feasible later

### 5. **Deepgram STT over Local Whisper**
- ✓ **Latency:** 0.3s vs. 2s for local Whisper
- ✗ **Cloud dependency:** No offline fallback
- ✓ **Cost:** ~$0.01–0.02 per minute; affordable for demo

### 6. **Single LLM Output (`{ speech, gesture, light, sfx }`)**
- ✓ **Coherence:** One neural network decides all modalities
- ✓ **Latency:** Single API call vs. three separate calls
- ✗ **Control:** Less granular per-output tuning
- ✓ **Prompting:** Clear structured output format with examples

## Configuration & Environment Variables

See `config.yaml` for:
- API keys (Deepgram, Claude, ElevenLabs)
- FSM state timeouts
- Gesture interpolation smoothness
- Camera/audio device selection
- WebSocket server port
- Log level

