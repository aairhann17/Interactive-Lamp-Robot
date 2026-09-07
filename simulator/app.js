const socket = new WebSocket("ws://127.0.0.1:8765");

const lamp = document.getElementById("lamp");
const head = document.getElementById("head");
const eye = document.getElementById("eye");
const statusEl = document.getElementById("status");
const stateEl = document.getElementById("state");
const speechEl = document.getElementById("speech");
const memoryEl = document.getElementById("memory");

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
  lamp.style.transform = `rotate(${styles.tilt})`;
}

function updateMotion(data) {
  const base = data.joints?.base_rotation ?? 0;
  const lift = data.joints?.lift ?? 20;
  const extension = data.joints?.extension ?? 10;
  const headTilt = data.joints?.head_tilt ?? 0;

  lamp.style.transform = `rotate(${base / 12}deg) skewY(${headTilt / 20}deg)`;
  head.style.translate = `${extension / 20}px ${-lift / 12}px`;
}

socket.addEventListener("open", () => {
  statusEl.textContent = "Connected to simulator bridge.";
});

socket.addEventListener("close", () => {
  statusEl.textContent = "Disconnected from simulator bridge.";
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
  }

  if (message.type === "speech") {
    speechEl.textContent = message.text;
  }

  if (message.type === "memory") {
    memoryEl.textContent = `${message.label}: ${message.description}`;
  }
});

setState("IDLE");
