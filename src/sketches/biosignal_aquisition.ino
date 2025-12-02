/*
 * Arduino Uno R4 - Biosignal Acquisition Sketch
 * Reads 6 channels of analog sensors and streams via Serial
 * Designed for EEG/EMG/EOG signals
 */

#define NUM_CHANNELS 6
#define SAMPLING_RATE 500  // Hz
const unsigned long SAMPLE_INTERVAL = 1000000UL / SAMPLING_RATE;  // microseconds

unsigned long lastSampleTime = 0;
int channelPins[NUM_CHANNELS] = {A0, A1, A2, A3, A4, A5};

// Correct type for array of string literals
const char* channelNames[NUM_CHANNELS] = {
  "EEG_Fp1", "EEG_Fp2", "EMG_1", "EMG_2", "EOG_H", "EOG_V"
};

void setup() {
  Serial.begin(115200);
  delay(500);

  // Configure analog pins (not strictly required on many Arduinos, but harmless)
  for (int i = 0; i < NUM_CHANNELS; i++) {
    pinMode(channelPins[i], INPUT);
  }

  // Send header info (helpful for host to detect and parse stream)
  Serial.println("BIOSIGNAL_SYSTEM_READY");
  Serial.print("CHANNELS: ");
  for (int i = 0; i < NUM_CHANNELS; i++) {
    Serial.print(channelNames[i]);
    if (i < NUM_CHANNELS - 1) Serial.print(",");
  }
  Serial.println();
  Serial.print("SAMPLING_RATE: ");
  Serial.println(SAMPLING_RATE);
  delay(100);
}

void loop() {
  unsigned long currentTime = micros();

  if ((currentTime - lastSampleTime) >= SAMPLE_INTERVAL) {
    // keep cadence steady (avoid large jumps if loop is delayed)
    lastSampleTime += SAMPLE_INTERVAL;

    if (currentTime - lastSampleTime > SAMPLE_INTERVAL) {
      // We've fallen behind; resync to avoid cumulative error
      lastSampleTime = currentTime;
    }


    // Print CSV line: timestamp_ms,ch1,ch2,...ch6
    unsigned long timestamp_ms = currentTime / 1000UL;
    Serial.print(timestamp_ms);

    for (int i = 0; i < NUM_CHANNELS; i++) {
      int sensorValue = analogRead(channelPins[i]);
      Serial.print(',');
      Serial.print(sensorValue);
    }

    Serial.println(); // terminate packet
  }
}
