// camera_blink_audio - camera_blink (camera + eyes) PLUS laptop-controlled audio.
//
// Everything from camera_blink is unchanged: camera served at /jpg, and the
// blinking-eyes face on the OLED. Added on top, controlled from the laptop over
// the same Wi-Fi:
//   GET  /rec/start   -> start recording the mic
//   GET  /rec/stop    -> stop, returns the recording as a 16 kHz mono WAV
//   POST /play        -> play an uploaded WAV on the speaker (the spoken reply)
//   GET  /play_last   -> play the last recording back (mic+speaker echo test)
//
// The idea: laptop records a question ("where are my glasses?"), some other program
// (not built here) turns it into speech-to-text + an answer WAV, then POSTs that WAV
// to /play so Nemo speaks it. This sketch is only the mic-in and speaker-out plumbing.
// Drive it from firmware/tests/talk.py.
//
// Audio uses the same proven calls as the micSpeaker test: PDM mic on 38/39, MAX98357
// speaker on 45/46/42, two separate I2S instances. Mic is read a small chunk at a time
// in loop() ONLY while recording, so the camera and eyes are untouched when idle.
//
// IMPORTANT: this repo is public. Do NOT commit real hotspot credentials.

#include "esp_camera.h"
#include <WiFi.h>
#include <WebServer.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <ESP_I2S.h>

const char* SSID = "YOUR_HOTSPOT_NAME";
const char* PASS = "YOUR_PASSWORD";

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

// ---- audio pins / settings (same as the micSpeaker test) ----
#define MIC_CLK  38
#define MIC_DATA 39
#define SPK_BCLK 45
#define SPK_LRCK 46
#define SPK_DOUT 42
#define SAMPLE_RATE 16000
#define MAX_REC_SECONDS 15
#define ECHO_GAIN 8          // volume boost for the /play_last echo (mic is quiet)

Adafruit_SSD1306 oled(128, 64, &Wire, -1);
WebServer server(80);

// camera/eyes state (unchanged)
unsigned long lastFrameMs = 0;
unsigned long bootMs = 0;
int shownEye = -1;
unsigned long nextBlinkMs = 0, blinkUntilMs = 0;

// audio state (new)
I2SClass i2sMic;
I2SClass i2sSpk;
uint8_t *recBuf = nullptr;  size_t recCap = 0;  volatile size_t recLen = 0;
volatile bool recording = false;
uint8_t *playBuf = nullptr; size_t playCap = 0;  size_t playLen = 0;

// ---------- camera (unchanged) ----------
void handleJpg() {
  camera_fb_t *fb = esp_camera_fb_get();
  if (!fb) { server.send(503, "text/plain", "no frame"); return; }
  lastFrameMs = millis();
  server.setContentLength(fb->len);
  server.send(200, "image/jpeg", "");
  server.client().write(fb->buf, fb->len);
  esp_camera_fb_return(fb);
}

// ---------- eyes (unchanged) ----------
void drawFace(bool open) {
  oled.clearDisplay();
  int cy = 32; int xs[2] = {42, 86};
  for (int i = 0; i < 2; i++) {
    int cx = xs[i];
    if (open) oled.fillRoundRect(cx - 14, cy - 18, 28, 36, 11, SSD1306_WHITE);
    else      oled.fillRoundRect(cx - 14, cy - 3, 28, 6, 3, SSD1306_WHITE);
  }
  oled.display();
}
void updateFace() {
  unsigned long now = millis();
  if (lastFrameMs == 0 && (now - bootMs) < 30000UL) return;
  bool rec = (lastFrameMs != 0) && (now - lastFrameMs < 1500UL);
  int want;
  if (rec) {
    if (nextBlinkMs == 0) nextBlinkMs = now + 2500;
    if (blinkUntilMs > now) want = 0;
    else if (now >= nextBlinkMs) { blinkUntilMs = now + 130; nextBlinkMs = now + random(2200, 3800); want = 0; }
    else want = 1;
  } else { want = 0; nextBlinkMs = 0; }
  if (want != shownEye) { drawFace(want == 1); shownEye = want; }
}

// ---------- audio (new) ----------
void writeWavHeader(uint8_t* h, uint32_t dataBytes) {
  uint32_t sr = SAMPLE_RATE, byteRate = SAMPLE_RATE * 2, chunk = 36 + dataBytes, sub1 = 16;
  uint16_t ch = 1, fmt = 1, blockAlign = 2, bits = 16;
  memcpy(h, "RIFF", 4);     memcpy(h + 4, &chunk, 4);   memcpy(h + 8, "WAVE", 4);
  memcpy(h + 12, "fmt ", 4); memcpy(h + 16, &sub1, 4);  memcpy(h + 20, &fmt, 2);
  memcpy(h + 22, &ch, 2);    memcpy(h + 24, &sr, 4);     memcpy(h + 28, &byteRate, 4);
  memcpy(h + 32, &blockAlign, 2); memcpy(h + 34, &bits, 2);
  memcpy(h + 36, "data", 4); memcpy(h + 40, &dataBytes, 4);
}

void handleRecStart() { if (!recording) { recLen = 0; recording = true; } server.send(200, "text/plain", "rec"); }

void handleRecStop() {
  recording = false;
  uint8_t hdr[44]; writeWavHeader(hdr, recLen);
  server.setContentLength(44 + recLen);
  server.send(200, "audio/wav", "");
  WiFiClient c = server.client();
  c.write(hdr, 44);
  size_t sent = 0;
  while (sent < recLen) { size_t n = (recLen - sent > 1460) ? 1460 : (recLen - sent); c.write(recBuf + sent, n); sent += n; }
}

void handlePlayUpload() {
  HTTPUpload& up = server.upload();
  if (up.status == UPLOAD_FILE_START) playLen = 0;
  else if (up.status == UPLOAD_FILE_WRITE) {
    if (playLen + up.currentSize <= playCap) { memcpy(playBuf + playLen, up.buf, up.currentSize); playLen += up.currentSize; }
  }
}
void handlePlay() {
  if (playLen > 44) i2sSpk.playWAV(playBuf, playLen);   // laptop sends a full WAV
  server.send(200, "text/plain", "played");
}

void handlePlayLast() {
  if (recLen < 2 || 44 + recLen > playCap) { server.send(200, "text/plain", "nothing to play"); return; }
  writeWavHeader(playBuf, recLen);
  memcpy(playBuf + 44, recBuf, recLen);
  int16_t* s = (int16_t*)(playBuf + 44); size_t n = recLen / 2;
  for (size_t i = 0; i < n; i++) { int32_t v = (int32_t)s[i] * ECHO_GAIN; if (v > 32767) v = 32767; if (v < -32768) v = -32768; s[i] = (int16_t)v; }
  i2sSpk.playWAV(playBuf, 44 + recLen);
  server.send(200, "text/plain", "played");
}

void setup() {
  Wire.begin(43, 44);
  oled.begin(SSD1306_SWITCHCAPVCC, 0x3C);
  oled.clearDisplay(); oled.setTextSize(1); oled.setTextColor(SSD1306_WHITE);
  oled.setCursor(0, 0); oled.println("Starting WiFi..."); oled.display();

  WiFi.mode(WIFI_STA);
  WiFi.begin(SSID, PASS);
  WiFi.setSleep(false);
  int tries = 0;
  while (WiFi.status() != WL_CONNECTED && tries < 40) {
    delay(500); tries++;
    oled.clearDisplay(); oled.setCursor(0, 0);
    oled.print("WiFi try "); oled.print(tries);
    oled.setCursor(0, 16); oled.print("code "); oled.print(WiFi.status());
    oled.display();
  }
  if (WiFi.status() != WL_CONNECTED) {
    oled.clearDisplay(); oled.setCursor(0, 0);
    oled.println("WiFi FAILED"); oled.setCursor(0, 16);
    oled.println("check name/pass"); oled.display();
    while (1) delay(1000);
  }

  // camera (unchanged)
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
  config.frame_size = FRAMESIZE_XGA;
  config.pixel_format = PIXFORMAT_JPEG;
  config.grab_mode = CAMERA_GRAB_LATEST;
  config.fb_location = CAMERA_FB_IN_PSRAM;
  config.jpeg_quality = 16;
  config.fb_count = 2;
  esp_camera_init(&config);

  // audio buffers + I2S (new) - two separate instances, both running
  recCap = (size_t)MAX_REC_SECONDS * SAMPLE_RATE * 2;
  recBuf  = (uint8_t*)ps_malloc(recCap);
  playCap = recCap + 44;
  playBuf = (uint8_t*)ps_malloc(playCap);
  i2sMic.setPinsPdmRx(MIC_CLK, MIC_DATA);
  i2sMic.begin(I2S_MODE_PDM_RX, SAMPLE_RATE, I2S_DATA_BIT_WIDTH_16BIT, I2S_SLOT_MODE_MONO);
  i2sMic.setTimeout(60);
  i2sSpk.setPins(SPK_BCLK, SPK_LRCK, SPK_DOUT);
  i2sSpk.begin(I2S_MODE_STD, SAMPLE_RATE, I2S_DATA_BIT_WIDTH_16BIT, I2S_SLOT_MODE_MONO);

  server.on("/jpg", handleJpg);
  server.on("/rec/start", handleRecStart);
  server.on("/rec/stop", handleRecStop);
  server.on("/play", HTTP_POST, handlePlay, handlePlayUpload);
  server.on("/play_last", handlePlayLast);
  server.begin();

  oled.clearDisplay();
  oled.setCursor(0, 0);  oled.println("Ready!");
  oled.setCursor(0, 20); oled.println("Open on laptop:");
  oled.setCursor(0, 40); oled.print("http://"); oled.print(WiFi.localIP());
  oled.setCursor(0, 52); oled.print("/jpg");
  oled.display();
  bootMs = millis();
}

void loop() {
  server.handleClient();
  updateFace();
  // capture mic only while recording; camera/eyes untouched when idle
  if (recording && recLen < recCap) {
    size_t want = recCap - recLen; if (want > 640) want = 640;   // ~20 ms chunk
    size_t got = i2sMic.readBytes((char*)(recBuf + recLen), want);
    recLen += got;
    if (recLen >= recCap) recording = false;                     // hit the max length
  }
}
