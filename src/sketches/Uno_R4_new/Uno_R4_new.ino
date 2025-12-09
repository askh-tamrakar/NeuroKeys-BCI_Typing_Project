// BioSignalDashboard.ino
// Target: Arduino UNO R4 (Minima / EK R4)
// Notes: Uses FspTimer (Renesas FSP wrapper used by R4 cores).
//       Make sure FspTimer.h / FspTimer.cpp are available in the sketch folder or installed as a library.

#include "FspTimer.h"
#include <Arduino.h>

// ================== CONFIG ====================
#define NUM_CHANNELS 3         // EMG + EEG + EOG
#define HEADER_LEN 3
#define PACKET_LEN (NUM_CHANNELS * 2 + HEADER_LEN + 1)  // = 3*2 + 3 + 1 = 10 bytes
#define SAMP_RATE 256.0f
#define BAUD_RATE 230400UL

// MARKERS
#define SYNC_BYTE_1 0xAB
#define SYNC_BYTE_2 0xCD
#define END_BYTE    0xEF

// ================== GLOBALS ====================
volatile uint8_t packetBuffer[PACKET_LEN];
volatile uint16_t adcValue = 0;
volatile bool bufferReady = false;
volatile uint8_t currentChannel = 0;
volatile bool timerStatus = false;

FspTimer BioTimer;
uint8_t dashboardMode = 0; // 0=EMG, 1=EEG, 2=EOG

// =====================================================
// HELPER: Decide mode based on latest readings
void detectGesture(uint16_t emg, uint16_t eeg, uint16_t eog) {
  static uint32_t lastSwitch = 0;
  uint32_t now = millis();
  if (now - lastSwitch < 500) return;

  if (emg > 12000) { dashboardMode = 0; lastSwitch = now; }
  else if (eeg > 11000) { dashboardMode = 1; lastSwitch = now; }
  else if (eog > 10000) { dashboardMode = 2; lastSwitch = now; }
}

// =====================================================
void updateDashboard() {
  if (dashboardMode == 0) Serial.println("[MODE] EMG Graph");
  else if (dashboardMode == 1) Serial.println("[MODE] EEG Graph");
  else if (dashboardMode == 2) Serial.println("[MODE] EOG Blink");
}

// ================= TIMER CALLBACK ====================
// Signature depends on FspTimer implementation; common pattern uses timer_callback_args_t *
void timerCallback(timer_callback_args_t * unused) {
  (void)unused;

  // Read all channels as quickly as possible
  for (currentChannel = 0; currentChannel < NUM_CHANNELS; currentChannel++) {
    // analogRead on R4 will respect analogReadResolution()
    adcValue = analogRead((int)currentChannel);
    // store MSB first
    uint8_t msb = highByte(adcValue);
    uint8_t lsb = lowByte(adcValue);
    packetBuffer[(currentChannel * 2) + HEADER_LEN]     = msb;
    packetBuffer[(currentChannel * 2) + HEADER_LEN + 1] = lsb;
  }

  // Extract latest 3-channel values (safe to read from volatile buffer here)
  uint16_t emg = ((uint16_t)packetBuffer[3] << 8) | packetBuffer[4];
  uint16_t eeg = ((uint16_t)packetBuffer[5] << 8) | packetBuffer[6];
  uint16_t eog = ((uint16_t)packetBuffer[7] << 8) | packetBuffer[8];

  detectGesture(emg, eeg, eog);

  packetBuffer[2]++;           // packet counter
  bufferReady = true;          // notify main loop
}

// ================= TIMER START ====================
bool timerBegin(float rateHz) {
  uint8_t t = GPT_TIMER; // request GPT timer group
  int8_t ch = FspTimer::get_available_timer(t);

  if (ch == -1) return false;
  // begin(mode, timer_group, channel, frequency_hz, duty, callback)
  BioTimer.begin(TIMER_MODE_PERIODIC, t, ch, rateHz, 0.0f, timerCallback);
  BioTimer.setup_overflow_irq();
  BioTimer.open();
  return true;
}

// ================== SEND PACKET ====================
void sendPacket() {
  // Serial.write from main loop only (not inside ISR)
  Serial.write((const uint8_t*)packetBuffer, PACKET_LEN);
}

// ================= COMMAND HANDLER ==================
void processCommand(String c) {
  c.trim();
  c.toUpperCase();
  if (c == "START") {
    timerStatus = true;
    Serial.println("ACQ STARTED");
  }
  else if (c == "STOP") {
    timerStatus = false;
    Serial.println("ACQ STOPPED");
  }
  else if (c == "MODE") {
    updateDashboard();
  }
  else if (c == "STATUS") {
    Serial.println(timerStatus ? "RUNNING" : "STOPPED");
  }
}

// ===================== SETUP =======================
void setup() {
  Serial.begin(BAUD_RATE);
  // Wait for Serial (only blocks when using native USB Serial)
  while (!Serial) { delay(1); }

  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, LOW);

  packetBuffer[0] = SYNC_BYTE_1;
  packetBuffer[1] = SYNC_BYTE_2;
  packetBuffer[2] = 0; // packet counter
  packetBuffer[PACKET_LEN - 1] = END_BYTE;

  // R4 supports up to 14-bit ADC resolution; set that for finer readings.
  analogReadResolution(14);

  bool timerOk = timerBegin(SAMP_RATE);
  if (!timerOk) {
    Serial.println("ERROR: Timer allocation failed. Check FspTimer availability.");
  }

  Serial.println("\n=== BIOSIGNAL DASHBOARD ===");
  Serial.println("[CH0] EMG  (Muscle)");
  Serial.println("[CH1] EEG  (Brain)");
  Serial.println("[CH2] EOG  (Eye)");
  Serial.println("===========================");
}

// ===================== LOOP ========================
void loop() {
  // If acquisition running and buffer ready, send packet
  if (timerStatus && bufferReady) {
    // briefly disable interrupts while reading bufferReady to avoid race
    noInterrupts();
    bufferReady = false;
    interrupts();

    sendPacket();
  }

  // Process incoming serial commands (non-blocking if nothing available)
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    processCommand(cmd);
  }
}
