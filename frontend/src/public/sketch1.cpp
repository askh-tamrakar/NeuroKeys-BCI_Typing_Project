#include "FspTimer.h"
#include <Arduino.h>

// ================== CONFIG ====================
#define NUM_CHANNELS 3         // EMG + EEG + EOG
#define HEADER_LEN 3
#define PACKET_LEN (NUM_CHANNELS*2 + HEADER_LEN + 1)  // = 3*2 + 3 + 1 = 10 bytes
#define SAMP_RATE 256.0
#define BAUD_RATE 230400

// MARKERS
#define SYNC_BYTE_1 0xAB
#define SYNC_BYTE_2 0xCD
#define END_BYTE    0xEF

// ================== GLOBALS ====================
uint8_t packetBuffer[PACKET_LEN];
uint16_t adcValue = 0;
bool bufferReady = false;
uint8_t currentChannel;
bool timerStatus = false;

FspTimer BioTimer;
uint8_t dashboardMode = 0; // 0=EMG, 1=EEG, 2=EOG

// =====================================================
// HELPER: Decide mode based on latest readings
void detectGesture(uint16_t emg, uint16_t eeg, uint16_t eog) {
  static uint32_t lastSwitch = 0;
  if (millis() - lastSwitch < 500) return;

  if (emg > 12000) { dashboardMode = 0; lastSwitch = millis(); }
  else if (eeg > 11000) { dashboardMode = 1; lastSwitch = millis(); }
  else if (eog > 10000) { dashboardMode = 2; lastSwitch = millis(); }
}

// =====================================================
void updateDashboard() {
  if (dashboardMode == 0) Serial.println("[MODE] EMG Graph");
  else if (dashboardMode == 1) Serial.println("[MODE] EEG Graph");
  else if (dashboardMode == 2) Serial.println("[MODE] EOG Blink");
}

// ================= TIMER CALLBACK ====================
void timerCallback(timer_callback_args_t * unused) {
  for (currentChannel = 0; currentChannel < NUM_CHANNELS; currentChannel++) {
    adcValue = analogRead(currentChannel);
    packetBuffer[(currentChannel * 2) + HEADER_LEN] = highByte(adcValue);
    packetBuffer[(currentChannel * 2) + HEADER_LEN + 1] = lowByte(adcValue);
  }

  uint16_t emg = (packetBuffer[3] << 8) | packetBuffer[4];
  uint16_t eeg = (packetBuffer[5] << 8) | packetBuffer[6];
  uint16_t eog = (packetBuffer[7] << 8) | packetBuffer[8];

  detectGesture(emg, eeg, eog);

  packetBuffer[2]++;  
  bufferReady = true;
}

// ================= TIMER START ====================
bool timerBegin(float rate) {
  uint8_t t = GPT_TIMER;
  int8_t ch = FspTimer::get_available_timer(t);

  if (ch == -1) return false;
  BioTimer.begin(TIMER_MODE_PERIODIC, t, ch, rate, 0.0f, timerCallback);
  BioTimer.setup_overflow_irq();
  BioTimer.open();
  return true;
}

// ================== SEND PACKET ====================
void sendPacket() { Serial.write(packetBuffer, PACKET_LEN); }

// ================= COMMAND HANDLER ==================
void processCommand(String c) {
  c.trim(); c.toUpperCase();
  if (c == "START") { timerStatus = true; Serial.println("ACQ STARTED"); }
  else if (c == "STOP") { timerStatus = false; Serial.println("ACQ STOPPED"); }
  else if (c == "MODE") { updateDashboard(); }
  else if (c == "STATUS") { Serial.println(timerStatus ? "RUNNING" : "STOPPED"); }
}

// ===================== SETUP =======================
void setup() {
  Serial.begin(BAUD_RATE);
  while (!Serial) {}

  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, LOW);

  packetBuffer[0] = SYNC_BYTE_1;
  packetBuffer[1] = SYNC_BYTE_2;
  packetBuffer[2] = 0;
  packetBuffer[PACKET_LEN-1] = END_BYTE;

  analogReadResolution(14);
  timerBegin(SAMP_RATE);

  Serial.println("\n=== BIOSIGNAL DASHBOARD ===");
  Serial.println("[CH0] EMG  (Muscle)");
  Serial.println("[CH1] EEG  (Brain)");
  Serial.println("[CH2] EOG  (Eye)");
  Serial.println("===========================");
}

// ===================== LOOP ========================
void loop() {
  if (timerStatus && bufferReady) {
    sendPacket();
    bufferReady = false;
  }

  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    processCommand(cmd);
  }
}
