# How the clip sends photos to the laptop

This is the contract between the clip's firmware (ESP32-S3, DFRobot DFR1154) and Nemo on the laptop.
The laptop side is `live.py --source push` (later, the full hub). `tools/fake_board.py` does
exactly what the firmware should do, so you can compare against it.

## The one rule

Send each photo as **one HTTP POST**:

```
POST http://<laptop-ip>:8000/frame
Content-Type: image/jpeg
Content-Length: <size>

<the raw JPEG bytes, nothing else>
```

- The body is the JPEG straight from the camera's frame buffer (`fb->buf`, `fb->len`). No base64, no form fields.
- Reply: `200 {"ok": true}`. Anything else is an error with a reason in `{"error": "..."}`.
- Photos bigger than 2 MB are rejected (a VGA JPEG is about 30 to 60 KB).

## Before sending

- `GET http://<laptop-ip>:8000/ping` returns `200 {"ok": true, "service": "nemo"}`. Use it at startup to check the laptop is reachable, and show the result on the OLED.
- The laptop prints its address when it starts: `Waiting for the clip to send photos to http://192.168.x.x:8000/frame`.
- Don't hardcode that IP in the sketch if you can avoid it. Options, easiest first: a `#define` at the top that's easy to change; a fixed IP for the laptop on the phone hotspot; later, a setting saved on the board.

## Recommended camera settings (ESP32 `esp_camera`)

| Setting | Value | Why |
|---|---|---|
| `frame_size` | `FRAMESIZE_VGA` (640x480) | Plenty for detection, small to send. Drop to `FRAMESIZE_QVGA` if Wi-Fi is struggling. |
| `jpeg_quality` | 12 (lower = better quality, bigger file) | Good balance. Try 15 if slow. |
| `fb_count` | 2 | Capture the next photo while sending this one. |
| `grab_mode` | `CAMERA_GRAB_LATEST` | Always send the newest photo, not a stale one. |
| `fb_location` | `CAMERA_FB_IN_PSRAM` | Needs PSRAM enabled in the Arduino board settings ("OPI PSRAM"). |
| Rate | start at 1 photo per second | Go up to 2 to 4 if it keeps up and the board stays cool. |

## Making it fast enough

- **Reuse one connection.** Keep a single `HTTPClient` with `setReuse(true)` (keep-alive) instead of opening a new connection for every photo. Opening connections is often the slowest part.
- `WiFi.setSleep(false)` (also stops the power bank switching off).
- No `Serial.print` inside the send loop, apart from errors.
- Keep the board close to the phone hotspot (iPhone: turn on "Maximise Compatibility" so it uses 2.4 GHz).
- Time three things separately and print them once a second: camera capture, the POST, and the gap between photos. That tells us whether the camera or the Wi-Fi is the slow part. The laptop shows the photo rate it receives in the window's status line.

## Coming later (not needed for chunk 1)

- The talk button and voice: probably `POST /ask` with the recorded audio plus one fresh full-quality photo.
- Things for the OLED and speaker to show or say: the laptop will reply with them.
- We'll add these to this file before anyone has to build them.
