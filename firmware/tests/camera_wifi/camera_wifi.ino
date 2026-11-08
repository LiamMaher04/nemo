// camera_wifi - Nemo device live camera over Wi-Fi (test / preview sketch)
//
// The board joins a phone hotspot, serves the current camera frame as a JPEG
// at http://<device-ip>/jpg, and shows its own web address on the OLED screen.
// A laptop on the same hotspot views it by polling that address (see the
// viewer.py in the team notes), or opens it in a browser for a single still.
//
// This is a PREVIEW sketch for eyeballing the camera. The real firmware pushes
// frames to the backend (POST /frame); that lives elsewhere.
//
// Hardware: DFRobot DFR1154 ESP32-S3 AI Camera + DFR0486 OLED (I2C on 43/44).
// Board "ESP32S3 Dev Module", PSRAM "OPI PSRAM" (camera will not start otherwise).
// Resolution is 1280x720 (HD): sharp enough that small objects like keys survive.
// HD frames are bigger, so the stream runs at a few fps over 2.4 GHz, which is fine.
//
// IMPORTANT: this repo is public. Do NOT commit real hotspot credentials.
// Put your own hotspot name and password in the two lines below, locally only.

#include "esp_camera.h"
#include <WiFi.h>
#include <WebServer.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

// ===== fill in locally, never commit real values =====
const char* SSID = "YOUR_HOTSPOT_NAME";   // exact hotspot name (watch spaces/caps)
const char* PASS = "YOUR_PASSWORD";       // hotspot password
// =====================================================

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

Adafruit_SSD1306 oled(128, 64, &Wire, -1);
WebServer server(80);

void handleJpg() {
  camera_fb_t *fb = esp_camera_fb_get();
  if (!fb) { server.send(503, "text/plain", "no frame"); return; }
  server.setContentLength(fb->len);
  server.send(200, "image/jpeg", "");
  server.client().write(fb->buf, fb->len);
  esp_camera_fb_return(fb);
}

void setup() {
  Wire.begin(43, 44);
  oled.begin(SSD1306_SWITCHCAPVCC, 0x3C);
  oled.clearDisplay(); oled.setTextSize(1); oled.setTextColor(SSD1306_WHITE);
  oled.setCursor(0, 0); oled.println("Starting WiFi..."); oled.display();

  // Wi-Fi first, full power, so the radio is not fighting the camera for current
  WiFi.mode(WIFI_STA);
  WiFi.begin(SSID, PASS);
  WiFi.setSleep(false);   // keep the radio awake so the power bank does not cut out
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

  // camera
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
  config.frame_size = FRAMESIZE_HD;        // 1280x720
  config.pixel_format = PIXFORMAT_JPEG;
  config.grab_mode = CAMERA_GRAB_LATEST;
  config.fb_location = CAMERA_FB_IN_PSRAM;
  config.jpeg_quality = 12;                // raise to 14-16 if the stream is slow
  config.fb_count = 2;
  esp_camera_init(&config);

  server.on("/jpg", handleJpg);
  server.begin();

  oled.clearDisplay();
  oled.setCursor(0, 0);  oled.println("Camera ready!");
  oled.setCursor(0, 20); oled.println("Open on laptop:");
  oled.setCursor(0, 40); oled.print("http://"); oled.print(WiFi.localIP());
  oled.setCursor(0, 52); oled.print("/jpg");
  oled.display();
}

void loop() { server.handleClient(); }
