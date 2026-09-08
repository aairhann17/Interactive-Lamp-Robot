/*
  Interactive Lamp Robot firmware sketch

  Purpose:
  - Receive JSON-over-serial commands from the Python app
  - Parse the shared protocol defined in hardware/device_protocol.py
  - Dispatch commands to actuator-specific handlers

  Protocol envelope:
  {
    "protocol": "lamp-robot-device-protocol-v1",
    "component": "motion" | "lighting" | "sfx" | "system",
    "command": "execute_gesture" | "set_state_color" | "play_sound" | "health_check",
    "payload": { ... }
  }

  This is a reference sketch. Replace the actuator stubs with your real motor,
  LED, and speaker drivers for the actual robot hardware.
*/

#include <ArduinoJson.h>

static const char* PROTOCOL_NAME = "lamp-robot-device-protocol-v1";
static const size_t MAX_JSON_BYTES = 256;

struct MotionCommand {
  String gesture;
  int durationMs;
};

struct LightingCommand {
  String stateName;
  int red;
  int green;
  int blue;
  float brightness;
};

struct SoundCommand {
  String soundName;
};

void setup() {
  Serial.begin(115200);
  while (!Serial) {
    delay(10);
  }

  // Initialize your motor controller, LED driver, and speaker output here.
  Serial.println("lamp-robot-firmware-ready");
}

void loop() {
  if (Serial.available() == 0) {
    delay(5);
    return;
  }

  String raw = Serial.readStringUntil('\n');
  raw.trim();
  if (raw.length() == 0) {
    return;
  }

  StaticJsonDocument<MAX_JSON_BYTES> doc;
  DeserializationError error = deserializeJson(doc, raw);
  if (error) {
    sendError("invalid_json", error.c_str());
    return;
  }

  const char* protocol = doc["protocol"] | "";
  if (String(protocol) != PROTOCOL_NAME) {
    sendError("invalid_protocol", "unexpected protocol name");
    return;
  }

  const char* component = doc["component"] | "";
  const char* command = doc["command"] | "";
  JsonObject payload = doc["payload"].as<JsonObject>();

  if (String(component) == "motion" && String(command) == "execute_gesture") {
    handleMotion(payload);
    sendOk("motion");
    return;
  }

  if (String(component) == "lighting" && String(command) == "set_state_color") {
    handleLighting(payload);
    sendOk("lighting");
    return;
  }

  if (String(component) == "sfx" && String(command) == "play_sound") {
    handleSound(payload);
    sendOk("sfx");
    return;
  }

  if (String(component) == "system" && String(command) == "health_check") {
    sendHealth();
    return;
  }

  sendError("unsupported_command", "component/command pair not recognized");
}

void handleMotion(JsonObject payload) {
  MotionCommand motion;
  motion.gesture = payload["gesture"] | "neutral";
  motion.durationMs = payload["duration_ms"] | 800;

  // TODO: map gesture names to your lamp's actual motor sequence.
  // Example mapping:
  // - neutral
  // - attention_grab
  // - warm_embrace
  // - curious_inspect
  // - confused_shrug
  // - farewell_wave

  Serial.print("motion:");
  Serial.print(motion.gesture);
  Serial.print(",duration_ms:");
  Serial.println(motion.durationMs);
}

void handleLighting(JsonObject payload) {
  LightingCommand lighting;
  lighting.stateName = payload["state"] | "IDLE";
  JsonArray rgb = payload["rgb"].as<JsonArray>();
  lighting.red = rgb.size() > 0 ? rgb[0] : 0;
  lighting.green = rgb.size() > 1 ? rgb[1] : 0;
  lighting.blue = rgb.size() > 2 ? rgb[2] : 0;
  lighting.brightness = payload["brightness"] | 1.0;

  // TODO: drive the LED strip or lamp lighting hardware here.
  Serial.print("lighting:");
  Serial.print(lighting.stateName);
  Serial.print(",rgb:");
  Serial.print(lighting.red);
  Serial.print("/");
  Serial.print(lighting.green);
  Serial.print("/");
  Serial.print(lighting.blue);
  Serial.print(",brightness:");
  Serial.println(lighting.brightness, 2);
}

void handleSound(JsonObject payload) {
  SoundCommand sound;
  sound.soundName = payload["sound"] | "";

  // TODO: trigger a buzzer, speaker, or audio cue here.
  Serial.print("sfx:");
  Serial.println(sound.soundName);
}

void sendOk(const char* subsystem) {
  StaticJsonDocument<128> response;
  response["status"] = "ok";
  response["subsystem"] = subsystem;
  serializeJson(response, Serial);
  Serial.println();
}

void sendHealth() {
  StaticJsonDocument<160> response;
  response["status"] = "ok";
  response["protocol"] = PROTOCOL_NAME;
  response["motion"] = "ready";
  response["lighting"] = "ready";
  response["sfx"] = "ready";
  serializeJson(response, Serial);
  Serial.println();
}

void sendError(const char* code, const char* message) {
  StaticJsonDocument<192> response;
  response["status"] = "error";
  response["code"] = code;
  response["message"] = message;
  serializeJson(response, Serial);
  Serial.println();
}
