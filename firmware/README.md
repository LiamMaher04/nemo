# firmware

Arduino sketches for the Nemo device (DFRobot DFR1154 ESP32-S3 AI Camera + DFR0486 OLED).

- Board: "ESP32S3 Dev Module", PSRAM: "OPI PSRAM" (camera won't start otherwise). USB-C data cable.
- Copy `secrets.example.h` to `secrets.h` (gitignored) and fill in the hotspot and laptop address.
- First goal: POST one JPEG per second to `http://<BACKEND_HOST>:<PORT>/frame` (see docs/interfaces.md).
- Then: button (BOOT, IO0) records audio, POSTs to `/ask`, plays the WAV reply on the speaker.
- `WiFi.setSleep(false)`. OLED: `Wire.begin(43, 44)`. Don't hold BOOT while plugging in.
- Put the working hardware test sketches (mic, speaker, camera) in `firmware/tests/`.
