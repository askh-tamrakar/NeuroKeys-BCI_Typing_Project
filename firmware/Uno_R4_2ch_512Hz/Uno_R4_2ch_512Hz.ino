
#include "FspTimer.h"
#include <Arduino.h>

// ===== CONFIGURATION =====
#define NUM_CHANNELS 2              // A0, A2
#define HEADER_LEN 3
#define PACKET_LEN (NUM_CHANNELS * 2 + HEADER_LEN + 1) // 8 bytes
#define SAMP_RATE 512.0             // 512 Hz
#define SYNC_BYTE_1 0xC7
#define SYNC_BYTE_2 0x7C
#define END_BYTE 0x01
#define BAUD_RATE 230400

// ===== LED & SWITCH CONFIG =====
#define LED_RED_1   13  // Top 1
#define LED_RED_2   12  // Top 2

#define LED_YELLOW_1  11  // Middle 1
#define LED_YELLOW_2  10  // Middle 2

#define LED_GREEN_1   9   // Bottom 1
#define LED_GREEN_2   8   // Bottom 2

#define SW_1  4   // Button 1
#define SW_2  7   // Button 2

bool sw1 = false;
bool sw2 = false;

// ===== GLOBALS =====
uint8_t packetBuffer[PACKET_LEN];  
uint8_t ch_A0 = 0;
uint8_t ch_A2 = 2;
uint16_t adcValue = 0;
bool timerStatus = false;
bool bufferReady = false;
FspTimer ChordsTimer;

// State Variabless
bool isConnected = false; 
bool isAcquiring = false;

// ===== HELPER FUNCTIONS =====
void updateLEDs() {
  if (!isConnected) {
    // Disconnected: Red ON
    digitalWrite(LED_RED_1, HIGH);
    digitalWrite(LED_RED_2, HIGH);
    digitalWrite(LED_YELLOW_1, LOW);
    digitalWrite(LED_YELLOW_2, LOW);
    digitalWrite(LED_GREEN_1, LOW);
    digitalWrite(LED_GREEN_2, LOW);
  } 
  else if (isConnected && !isAcquiring) {
    // Connected (Idle): Yellow ON
    digitalWrite(LED_RED_1, LOW);
    digitalWrite(LED_RED_2, LOW);
    digitalWrite(LED_YELLOW_1, HIGH);
    digitalWrite(LED_YELLOW_2, HIGH);
    digitalWrite(LED_GREEN_1, LOW);
    digitalWrite(LED_GREEN_2, LOW);
  }
  else if (isConnected && isAcquiring) {
    // Acquiring: Green ON
    digitalWrite(LED_RED_1, LOW);
    digitalWrite(LED_RED_2, LOW);
    digitalWrite(LED_YELLOW_1, LOW);
    digitalWrite(LED_YELLOW_2, LOW);
    digitalWrite(LED_GREEN_1, HIGH);
    digitalWrite(LED_GREEN_2, HIGH);
  }
}

// ===== TIMER FUNCTIONS =====
bool timerStart() {
  timerStatus = true;
  isAcquiring = true;
  isConnected = true;
  updateLEDs();
  return ChordsTimer.start();
}

bool timerStop() {
  timerStatus = false;
  bufferReady = false;
  isAcquiring = false;
  updateLEDs();
  return ChordsTimer.stop();
}

void timerCallback(timer_callback_args_t __attribute((unused)) * p_args) {
  if (!timerStatus) {
    return;
  }

  // Read 2 channels (A0, A2)
  adcValue = analogRead(ch_A0);
  packetBuffer[HEADER_LEN] = highByte(adcValue);
  packetBuffer[HEADER_LEN + 1] = lowByte(adcValue);

  adcValue = analogRead(ch_A2);
  packetBuffer[HEADER_LEN + 2] = highByte(adcValue);
  packetBuffer[HEADER_LEN + 3] = lowByte(adcValue);

  // Increment counter
  packetBuffer[2]++;
  bufferReady = true;
}

bool timerBegin(float sampling_rate) {
  uint8_t timer_type = GPT_TIMER;
  int8_t timer_channel = FspTimer::get_available_timer(timer_type);
  
  if (timer_channel != -1) {
    ChordsTimer.begin(TIMER_MODE_PERIODIC, timer_type, timer_channel, sampling_rate, 0.0f, timerCallback);
    ChordsTimer.setup_overflow_irq();
    ChordsTimer.open();
    return true;
  } else {
    return false;
  }
}

// ===== DATA TRANSMISSION =====
void sendBinaryPacket() {
  Serial.write(packetBuffer, PACKET_LEN); 
}

// ===== COMMAND PROCESSING =====
void processCommand(String command) {
  command.trim();
  command.toUpperCase();

  // If we receive ANY command, we ensure we are marked connected
  if (!isConnected) {
    isConnected = true;
    updateLEDs();
  }

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
    Serial.println("CH0 = A0");
    Serial.println("CH1 = A2");
    Serial.println("PACKET_SIZE = 8 bytes");
  } 
  else {
    Serial.println("UNKNOWN_COMMAND");
  }
}

// ===== SETUP =====
void setup() {
  Serial.begin(BAUD_RATE);
  
  // LED Setup
  pinMode(LED_RED_1, OUTPUT);
  pinMode(LED_YELLOW_1, OUTPUT);
  pinMode(LED_GREEN_1, OUTPUT);
  
  pinMode(LED_RED_2, OUTPUT);
  pinMode(LED_YELLOW_2, OUTPUT);
  pinMode(LED_GREEN_2, OUTPUT);
  
  // Switch Setup
  pinMode(SW_1, INPUT);
  pinMode(SW_2, INPUT);

  // Initialize packet buffer
  packetBuffer[0] = SYNC_BYTE_1;
  packetBuffer[1] = SYNC_BYTE_2;
  packetBuffer[2] = 0;
  packetBuffer[PACKET_LEN - 1] = END_BYTE;

  timerBegin(SAMP_RATE);
  analogReadResolution(14);

  // Initial State: Disconnected (Red)
  isConnected = false;
  isAcquiring = false;
  updateLEDs();
  
  // Print banner
  Serial.println("\n=== 2-CHANNEL BCI @ 512 Hz ===");
}

// ===== LED ANIMATION =====
void runChaserAnimation() {
  static unsigned long lastUpdate = 0;
  static int currentLedIdx = 0;
  const int ledPins[] = {LED_RED_1, LED_RED_2, LED_YELLOW_1, LED_YELLOW_2, LED_GREEN_1, LED_GREEN_2};
  const int numLeds = 6;
  
  if (millis() - lastUpdate > 100) { // Speed: 100ms
    lastUpdate = millis();
    
    // Turn off all
    for (int i=0; i<numLeds; i++) {
      digitalWrite(ledPins[i], LOW);
    }
    
    // Turn on current
    digitalWrite(ledPins[currentLedIdx], HIGH);
    
    // Move next
    currentLedIdx++;
    if (currentLedIdx >= numLeds) currentLedIdx = 0;
  }
}

// ===== MAIN LOOP =====
void loop() {
  // 1. LED Handling
  if (isAcquiring) {
    runChaserAnimation();
  } else {
    // If not acquiring, ensure static state is maintained (Red/Yellow)
    // We call this periodically or just rely on state transitions. 
    // To be safe against animation leftovers, we can just let updateLEDs handle transition.
  }

  // 2. Data Sending
  if (timerStatus and bufferReady) {
    sendBinaryPacket();
    bufferReady = false;
  }

  // 3. Command Processing
  if (Serial.available()) {
    String command = Serial.readStringUntil('\n');
    processCommand(command);
  }

  // 4. Switch Handling (Robust Debounce)
  static bool sw1State = LOW;
  static bool sw2State = LOW;
  static bool lastReading1 = LOW;
  static bool lastReading2 = LOW;
  static unsigned long lastDebounceTime1 = 0;
  static unsigned long lastDebounceTime2 = 0;
  unsigned long debounceDelay = 50; // 50ms stability required

  // --- Switch 1 ---
  bool reading1 = digitalRead(SW_1);
  if (reading1 != lastReading1) {
    lastDebounceTime1 = millis();
  }
  if ((millis() - lastDebounceTime1) > debounceDelay) {
    // Reading has been stable for > 50ms
    if (reading1 != sw1State) {
      sw1State = reading1;
      if (sw1State == HIGH) {
        Serial.println("MSG:SWITCH_1_PRESSED");
      }
    }
  }
  lastReading1 = reading1;

  // --- Switch 2 ---
  bool reading2 = digitalRead(SW_2);
  if (reading2 != lastReading2) {
    lastDebounceTime2 = millis();
  }
  if ((millis() - lastDebounceTime2) > debounceDelay) {
    // Reading has been stable for > 50ms
    if (reading2 != sw2State) {
      sw2State = reading2;
      if (sw2State == HIGH) {
        // Trigger handled by text message only now (App logic fixed)
        Serial.println("MSG:SWITCH_2_PRESSED"); 
      }
    }
  }
  lastReading2 = reading2;
}
