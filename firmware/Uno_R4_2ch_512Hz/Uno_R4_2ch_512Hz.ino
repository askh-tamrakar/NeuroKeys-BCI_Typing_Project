
#include "FspTimer.h"
#include <Arduino.h>

// ===== CONFIGURATION =====
#define NUM_CHANNELS 2              // REDUCED to 2 channels
#define HEADER_LEN 3
#define PACKET_LEN (NUM_CHANNELS * 2 + HEADER_LEN + 1)  // = 10 bytes (was 16)
#define SAMP_RATE 512.0             // INCREASED to 512 Hz (was 500)
#define SYNC_BYTE_1 0xC7
#define SYNC_BYTE_2 0x7C
#define END_BYTE 0x01
#define BAUD_RATE 230400

// ===== GLOBALS =====
uint8_t packetBuffer[PACKET_LEN];   // Now only 10 bytes
uint8_t currentChannel;
uint16_t adcValue = 0;
bool timerStatus = false;
bool bufferReady = false;
FspTimer ChordsTimer;

// ===== TIMER FUNCTIONS =====
bool timerStart() {
  timerStatus = true;
  digitalWrite(LED_BUILTIN, HIGH);
  return ChordsTimer.start();
}

bool timerStop() {
  timerStatus = false;
  bufferReady = false;
  digitalWrite(LED_BUILTIN, LOW);
  return ChordsTimer.stop();
}

void timerCallback(timer_callback_args_t __attribute((unused)) * p_args) {
  if (!timerStatus or Serial.available()) {
    timerStop();
    return;
  }

  // Read ONLY 2 channels (A0, A1)
  for (currentChannel = 0; currentChannel < NUM_CHANNELS; currentChannel++) {
    adcValue = analogRead(currentChannel);
    packetBuffer[((2 * currentChannel) + HEADER_LEN)] = highByte(adcValue);
    packetBuffer[((2 * currentChannel) + HEADER_LEN + 1)] = lowByte(adcValue);
  }

  // Increment counter
  packetBuffer[2]++;
  bufferReady = true;
}

bool timerBegin(float sampling_rate) {
  uint8_t timer_type = GPT_TIMER;
  int8_t timer_channel = FspTimer::get_available_timer(timer_type);
  
  if (timer_channel != -1) {
    ChordsTimer.begin(TIMER_MODE_PERIODIC, timer_type, timer_channel, 
                      sampling_rate, 0.0f, timerCallback);
    ChordsTimer.setup_overflow_irq();
    ChordsTimer.open();
    return true;
  } else {
    return false;
  }
}

// ===== DATA TRANSMISSION =====
void sendBinaryPacket() {
  Serial.write(packetBuffer, PACKET_LEN);  // Send 10 bytes (was 16)
}

// ===== COMMAND PROCESSING =====
void processCommand(String command) {
  command.trim();
  command.toUpperCase();

  if (command == "WHORU") {
    Serial.println("UNO-R4-2CH-512HZ");
  }
  else if (command == "START") {
    timerStart();
    Serial.println("ACQUISITION_STARTED");
  }
  else if (command == "STOP") {
    timerStop();
    Serial.println("ACQUISITION_STOPPED");
  }
  else if (command == "STATUS") {
    Serial.println(timerStatus ? "RUNNING" : "STOPPED");
  }
  else if (command == "CONFIG") {
    Serial.println("2 CHANNELS @ 512 Hz");
    Serial.println("CH0 = A0 (Fp1)");
    Serial.println("CH1 = A1 (Fp2)");
    Serial.println("PACKET_SIZE = 10 bytes");
  }
  else {
    Serial.println("UNKNOWN_COMMAND");
  }
}

// ===== SETUP =====
void setup() {
  Serial.begin(BAUD_RATE);
  while (!Serial) { }

  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, LOW);

  // Initialize packet buffer
  packetBuffer[0] = SYNC_BYTE_1;
  packetBuffer[1] = SYNC_BYTE_2;
  packetBuffer[2] = 0;
  packetBuffer[PACKET_LEN - 1] = END_BYTE;

  timerBegin(SAMP_RATE);
  analogReadResolution(14);

  Serial.println("\n=== 2-CHANNEL BCI @ 512 Hz ===");
  Serial.println("Channels: 2 (A0, A1)");
  Serial.println("Sampling: 512 Hz");
  Serial.println("Packet Size: 10 bytes");
  Serial.println("Data Rate: 5120 bytes/sec");
  Serial.println("Ready for brain typing!");
}

// ===== MAIN LOOP =====
void loop() {
  if (timerStatus and bufferReady) {
    sendBinaryPacket();  // Send 10 bytes
    bufferReady = false;
  }

  if (Serial.available()) {
    String command = Serial.readStringUntil('\n');
    processCommand(command);
  }
}
