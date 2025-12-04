#include "FspTimer.h"
#include <Arduino.h>

// Definitions
#define NUM_CHANNELS 6                                  // Number of channels supported
#define HEADER_LEN 3                                    // Header = SYNC_BYTE_1 + SYNC_BYTE_2 + Counter
#define PACKET_LEN (NUM_CHANNELS * 2 + HEADER_LEN + 1)  // Packet length = Header + Data + END_BYTE
#define SAMP_RATE 500.0                                 // Sampling rate (250/500 for UNO R4)
#define SYNC_BYTE_1 0xC7                                // Packet first byte
#define SYNC_BYTE_2 0x7C                                // Packet second byte
#define END_BYTE 0x01                                   // Packet last byte
#define BAUD_RATE 230400                                // Serial connection baud rate

// Global constants and variables
uint8_t packetBuffer[PACKET_LEN];  // The transmission packet
uint8_t currentChannel;            // Current channel being sampled
uint16_t adcValue = 0;             // ADC current value
bool timerStatus = false;          // Timer status bit
bool bufferReady = false;          // Buffer ready status bit

FspTimer ChordsTimer;

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
  // Read 6ch ADC inputs and store current values in packetBuffer
  for (currentChannel = 0; currentChannel < NUM_CHANNELS; currentChannel++) {
    adcValue = analogRead(currentChannel);                                      // Read Analog input
    packetBuffer[((2 * currentChannel) + HEADER_LEN)] = highByte(adcValue);     // Write High Byte
    packetBuffer[((2 * currentChannel) + HEADER_LEN + 1)] = lowByte(adcValue);  // Write Low Byte
  }

  // Increment the packet counter
  packetBuffer[2]++;

  // Set bufferReady status bit to true
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

void setup() {
  Serial.begin(BAUD_RATE);
  while (!Serial) {
    ;  // Wait for serial port to connect. Needed for native USB
  }

  // Status LED
  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, LOW);

  // Initialize packetBuffer
  packetBuffer[0] = SYNC_BYTE_1;            // Sync 0
  packetBuffer[1] = SYNC_BYTE_2;            // Sync 1
  packetBuffer[2] = 0;                      // Packet counter
  packetBuffer[PACKET_LEN - 1] = END_BYTE;  // End Byte

  // Setup timer
  timerBegin(SAMP_RATE);

  // Set ADC resolution to 14bit
  analogReadResolution(14);
}

void loop() {
  // Send data if the buffer is ready and the timer is activ
  if (timerStatus and bufferReady) {
    Serial.write(packetBuffer, PACKET_LEN);
    bufferReady = false;
  }

  if (Serial.available()) {
    String command = Serial.readStringUntil('\n');
    command.trim();         // Remove extra spaces or newline characters
    command.toUpperCase();  // Normalize to uppercase for case-insensitivity

    if (command == "WHORU")  // Who are you?
    {
      Serial.println("UNO-R4");
    } else if (command == "START")  // Start data acquisition
    {
      timerStart();
    } else if (command == "STOP")  // Stop data acquisition
    {
      timerStop();
    } else if (command == "STATUS")  // Get status
    {
      Serial.println(timerStatus ? "RUNNING" : "STOPPED");
    } else {
      Serial.println("UNKNOWN COMMAND");
    }
  }
}
