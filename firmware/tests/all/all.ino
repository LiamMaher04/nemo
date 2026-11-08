#include "esp_camera.h"
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <ESP_I2S.h>

// ---- camera pins (yours) ----
#define PWDN_GPIO_NUM -1
#define RESET_GPIO_NUM -1
#define XCLK_GPIO_NUM  5
#define SIOD_GPIO_NUM  8
#define SIOC_GPIO_NUM  9
#define Y9_GPIO_NUM 4
#define Y8_GPIO_NUM 6
#define Y7_GPIO_NUM 7
#define Y6_GPIO_NUM 14
#define Y5_GPIO_NUM 17
#define Y4_GPIO_NUM 21
#define Y3_GPIO_NUM 18
#define Y2_GPIO_NUM 16
#define VSYNC_GPIO_NUM 1
#define HREF_GPIO_NUM 2
#define PCLK_GPIO_NUM 15

// ---- audio pins (yours) ----
#define MIC_CLK  38
#define MIC_DATA 39
#define SPK_BCLK 45
#define SPK_LRCK 46
#define SPK_DOUT 42
#define GAIN 6            // speaker volume multiplier

Adafruit_SSD1306 oled(128, 64, &Wire, -1);
I2SClass i2s;

void msg(const char *a, const char *b = "") {
  oled.clearDisplay(); oled.setTextSize(1); oled.setTextColor(SSD1306_WHITE);
  oled.setCursor(0, 0);  oled.println(a);
  oled.setCursor(0, 16); oled.println(b);
  oled.display();
}

void setup() {
  Serial.begin(921600);

  // 1) SCREEN
  Wire.begin(43, 44);
  oled.begin(SSD1306_SWITCHCAPVCC, 0x3C);
  msg("Booting...", "screen OK");
  delay(800);

  // 2) MIC  (record 3 seconds)
  msg("Recording 3s", "say something!");
  i2s.setPinsPdmRx(MIC_CLK, MIC_DATA);
  i2s.begin(I2S_MODE_PDM_RX, 16000, I2S_DATA_BIT_WIDTH_16BIT, I2S_SLOT_MODE_MONO);
  size_t wav_size = 0;
  uint8_t *wav = i2s.recordWAV(3, &wav_size);
  i2s.end();

  // amplify so it's audible
  if (wav && wav_size > 44) {
    int16_t *s = (int16_t *)(wav + 44);
    size_t n = (wav_size - 44) / 2;
    for (size_t i = 0; i < n; i++) {
      int32_t v = (int32_t)s[i] * GAIN;
      if (v > 32767) v = 32767; if (v < -32768) v = -32768;
      s[i] = (int16_t)v;
    }
  }

  // 3) SPEAKER  (play it back)
  msg("Playing back", "listen!");
  i2s.setPins(SPK_BCLK, SPK_LRCK, SPK_DOUT);
  i2s.begin(I2S_MODE_STD, 16000, I2S_DATA_BIT_WIDTH_16BIT, I2S_SLOT_MODE_MONO);
  if (wav) { i2s.playWAV(wav, wav_size); free(wav); }
  i2s.end();
  msg("MIC + SPK OK", "starting camera");
  delay(800);

  // 4) CAMERA (init last = lowest power peak)
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0; config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM; config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM; config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM; config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM; config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM; config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM; config.pin_href = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM; config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM; config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.frame_size = FRAMESIZE_QVGA;
  config.pixel_format = PIXFORMAT_JPEG;
  config.grab_mode = CAMERA_GRAB_WHEN_EMPTY;
  config.fb_location = CAMERA_FB_IN_PSRAM;
  config.jpeg_quality = 12; config.fb_count = 1;
  if (esp_camera_init(&config) != ESP_OK) { msg("CAMERA FAIL", "check board"); while (1) delay(1000); }
  msg("LIVE", "camera streaming");
}

unsigned long lastScreen = 0;
long frames = 0;

void loop() {
  camera_fb_t *fb = esp_camera_fb_get();
  if (fb) { Serial.write(fb->buf, fb->len); esp_camera_fb_return(fb); frames++; }

  // update the status screen once a second (not every frame)
  if (millis() - lastScreen > 1000) {
    char line[24]; snprintf(line, sizeof(line), "frames: %ld", frames);
    msg("LIVE  (all 4 OK)", line);
    lastScreen = millis();
  }
  delay(100);
}
