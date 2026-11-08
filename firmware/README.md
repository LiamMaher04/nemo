# firmware

Arduino sketches for the Nemo device (DFRobot DFR1154 ESP32-S3 AI Camera + DFR0486 OLED).

- Board: "ESP32S3 Dev Module", PSRAM: "OPI PSRAM" (camera won't start otherwise). USB-C data cable.
- Copy `secrets.example.h` to `secrets.h` (gitignored) and fill in the hotspot details.
- The working sketch is `tests/camera_blink_audio` (Laura). It serves `GET /jpg`, `/rec/start`,
  `/rec/stop`, `POST /play` and `/play_last` on Nemo's own IP (shown on the OLED), and the BOOT
  button (IO0) records while held, POSTs the WAV to `BACKEND_ASK_URL` (the backend's `/ask`) and
  plays the reply. See `docs/interfaces.md` section 1.
- The backend pulls frames from `/jpg` (`FRAME_SOURCE=pull`), so the device doesn't POST frames.
- `WiFi.setSleep(false)`. OLED: `Wire.begin(43, 44)`, eyes only. Don't hold BOOT while plugging in.
- `tests/` also holds the single-part hardware tests (camera, mic and speaker, WiFi) and `talk.py`.
