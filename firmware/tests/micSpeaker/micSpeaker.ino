#include <Arduino.h>
#include "ESP_I2S.h"

#define SAMPLE_RATE 16000
#define DATA_PIN  GPIO_NUM_39
#define CLOCK_PIN GPIO_NUM_38
#define REC_TIME 5
#define GAIN 8          // <-- volume. Raise for louder, lower if it distorts

void setup() {
  uint8_t *wav_buffer;
  size_t wav_size;
  I2SClass i2s;
  I2SClass i2s1;
  Serial.begin(115200);
  pinMode(3, OUTPUT);
  i2s.setPinsPdmRx(CLOCK_PIN, DATA_PIN);
  i2s.begin(I2S_MODE_PDM_RX, SAMPLE_RATE, I2S_DATA_BIT_WIDTH_16BIT, I2S_SLOT_MODE_MONO);
  i2s1.setPins(45, 46, 42);
  i2s1.begin(I2S_MODE_STD, SAMPLE_RATE, I2S_DATA_BIT_WIDTH_16BIT, I2S_SLOT_MODE_MONO);

  Serial.println("start REC");
  digitalWrite(3, HIGH);
  wav_buffer = i2s.recordWAV(REC_TIME, &wav_size);
  digitalWrite(3, LOW);

  // Turn up the volume: boost each audio sample (skip 44-byte WAV header)
  int16_t *samples = (int16_t *)(wav_buffer + 44);
  size_t n = (wav_size - 44) / 2;
  for (size_t i = 0; i < n; i++) {
    int32_t v = (int32_t)samples[i] * GAIN;
    if (v >  32767) v =  32767;      // clip so it doesn't wrap around
    if (v < -32768) v = -32768;
    samples[i] = (int16_t)v;
  }

  i2s1.playWAV(wav_buffer, wav_size);
}
void loop() {}