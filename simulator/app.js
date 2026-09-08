let socket;
let reconnectTimer = null;
let reconnectAttempts = 0;
let connectionIndex = 0;
const bridgeUrls = ["ws://127.0.0.1:8080", "ws://127.0.0.1:8765"];

const lamp = document.getElementById("lamp");
const head = document.getElementById("head");
const eye = document.getElementById("eye");
const bridgeBadge = document.getElementById("bridgeBadge");
const statusEl = document.getElementById("status");
const lastUpdateEl = document.getElementById("lastUpdate");
const stateEl = document.getElementById("state");
const motionEl = document.getElementById("motion");
const lightEl = document.getElementById("light");
const speechEl = document.getElementById("speech");
const memoryEl = document.getElementById("memory");
const stateControls = document.getElementById("stateControls");
const presetControls = document.getElementById("presetControls");

const stateStyles = {
  IDLE: { glow: "rgba(122, 215, 255, 0.18)", eye: "#07131f", tilt: "0deg" },
  NOTICE: { glow: "rgba(255, 245, 210, 0.42)", eye: "#1a1205", tilt: "-2deg" },
  GREET: { glow: "rgba(255, 193, 102, 0.42)", eye: "#2d1604", tilt: "4deg" },
  LISTEN: { glow: "rgba(101, 255, 188, 0.36)", eye: "#052116", tilt: "0deg" },
  CONVERSE: { glow: "rgba(255, 200, 120, 0.42)", eye: "#1d1004", tilt: "-5deg" },
  OBSERVE: { glow: "rgba(183, 128, 255, 0.44)", eye: "#12061e", tilt: "8deg" },
  DISENGAGE: { glow: "rgba(91, 122, 160, 0.18)", eye: "#091019", tilt: "-8deg" },
};

function setState(state) {
  const styles = stateStyles[state] || stateStyles.IDLE;
  stateEl.textContent = state;
  lamp.style.filter = `drop-shadow(0 0 26px ${styles.glow})`;
  head.style.boxShadow = `0 0 42px ${styles.glow}`;
  eye.style.background = styles.eye;
  lamp.dataset.stateTilt = styles.tilt;
  applyLampTransform();
}

function setBridgeStatus(isLive, message) {
  bridgeBadge.textContent = isLive ? "Live" : "Connecting";
  bridgeBadge.classList.toggle("is-live", isLive);
  statusEl.textContent = message;
}

function markUpdate() {
  lastUpdateEl.textContent = `Last update: ${new Date().toLocaleTimeString()}`;
}

function sendControl(state) {
  if (!socket || socket.readyState !== WebSocket.OPEN) {
    setBridgeStatus(false, "Bridge is offline, cannot send manual control.");
    return;
  }

  socket.send(JSON.stringify({ type: "control", command: "set_state", state }));
}

function sendPreset(preset) {
  if (!socket || socket.readyState !== WebSocket.OPEN) {
    setBridgeStatus(false, "Bridge is offline, cannot run a preset.");
    return;
  }

  socket.send(JSON.stringify({ type: "control", command: preset === "full" ? "run_demo" : "set_state", state: presetStateMap[preset], preset }));
}

const presetStateMap = {
  engage: "NOTICE",
  greet: "GREET",
  listen: "LISTEN",
  observe: "OBSERVE",
  disengage: "DISENGAGE",
  full: "IDLE",
};

function applyLampTransform() {
  const stateTilt = lamp.dataset.stateTilt || "0deg";
  const motionTilt = lamp.dataset.motionTilt || "0deg";
  const motionShift = lamp.dataset.motionShift || "translate(0px, 0px)";
  lamp.style.transform = `rotate(${stateTilt}) rotate(${motionTilt}) ${motionShift}`;
}

function connect() {
  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }

  const bridgeUrl = bridgeUrls[connectionIndex % bridgeUrls.length];
  socket = new WebSocket(bridgeUrl);

  socket.addEventListener("open", () => {
    reconnectAttempts = 0;
    setBridgeStatus(true, "Connected to simulator bridge.");
  });

  socket.addEventListener("close", () => {
    setBridgeStatus(false, "Disconnected from simulator bridge.");
    connectionIndex = (connectionIndex + 1) % bridgeUrls.length;
    const delay = Math.min(1000 + reconnectAttempts * 1000, 5000);
    reconnectAttempts += 1;
    reconnectTimer = window.setTimeout(connect, delay);
  });

  socket.addEventListener("error", () => {
    setBridgeStatus(false, "Simulator bridge unavailable, retrying…");
  });

  socket.addEventListener("message", (event) => {
    const message = JSON.parse(event.data);

    if (message.type === "state") {
      setState(message.new_state);
    }

    if (message.type === "motion") {
      updateMotion(message);
    }

    if (message.type === "lighting" && Array.isArray(message.rgb)) {
      const [r, g, b] = message.rgb;
      lamp.style.filter = `drop-shadow(0 0 28px rgba(${r}, ${g}, ${b}, 0.42))`;
      lightEl.textContent = `${message.state || "unknown"}: rgb(${r}, ${g}, ${b})`;
    }

    if (message.type === "speech") {
      speechEl.textContent = message.text;
    }

    if (message.type === "memory") {
      memoryEl.textContent = `${message.label}: ${message.description}`;
    }

    markUpdate();
  });
}

function updateMotion(data) {
  const base = data.joints?.base_rotation ?? 0;
  const lift = data.joints?.lift ?? 20;
  const extension = data.joints?.extension ?? 10;
  const headTilt = data.joints?.head_tilt ?? 0;

  lamp.dataset.motionTilt = `${base / 12}deg`;
  lamp.dataset.motionShift = `translate(${extension / 20}px, ${-lift / 12}px)`;
  head.style.transform = `translateX(-50%) rotate(${headTilt / 2}deg)`;
  motionEl.textContent = `${data.gesture || "gesture"} · base ${base.toFixed(1)}° · lift ${lift.toFixed(1)} · ext ${extension.toFixed(1)}`;
  applyLampTransform();
}

setState("IDLE");
setBridgeStatus(false, "Waiting for a websocket connection.");
connect();

stateControls.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-state]");
  if (!button) {
    return;
  }

  sendControl(button.dataset.state);
});

presetControls.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-preset]");
  if (!button) {
    return;
  }

  sendPreset(button.dataset.preset);
});

window.addEventListener("keydown", (event) => {
  const keyMap = {
    "1": "IDLE",
    "2": "NOTICE",
    "3": "GREET",
    "4": "LISTEN",
    "5": "CONVERSE",
    "6": "OBSERVE",
    "7": "DISENGAGE",
    i: "IDLE",
    n: "NOTICE",
    g: "GREET",
    l: "LISTEN",
    c: "CONVERSE",
    o: "OBSERVE",
    d: "DISENGAGE",
  };

  const state = keyMap[event.key.toLowerCase()];
  if (state) {
    sendControl(state);
  }
});
