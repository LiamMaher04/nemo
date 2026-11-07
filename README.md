# Nemo

HackUTD 2026. A clip-on camera for older people that remembers where things were last put down
and answers "where are my keys?" out loud. No app to learn: the person only talks to the clip.

The clip (DFRobot ESP32-S3 AI Camera) only takes photos and plays sound. A laptop does the
thinking: object detection (YOLOE), memory (Spacetime), the voice agent (NVIDIA Nemotron) and
messages to family (Photon).

Built in small chunks. What works so far:

- [x] **Chunk 1: live detection window.** Open the laptop webcam or receive photos from the clip, run YOLOE, show boxes live.

## Setup (Mac)

Needs Python 3.10 or newer (`python3 --version`).

```bash
git clone https://github.com/LiamMaher04/nemo.git
cd nemo
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Every new Terminal window: `cd nemo` then `source .venv/bin/activate`.

## Run

```bash
python live.py                  # laptop webcam
python live.py --source push    # wait for the clip to send photos
```

The first run downloads YOLOE (about 30 MB) and its text model (about 240 MB) into this folder.
macOS will ask to let Terminal use the camera: click Allow (or System Settings > Privacy & Security > Camera).

In the window: **Q** quit, **S** save the current photo to `data/captures/` (useful for labelling later), **+/-** change the confidence threshold.

What to look for is in `objects.yaml`. Edit it and restart.

### Testing the clip connection without the clip

In one Terminal: `python live.py --source push`. In another: `python tools/fake_board.py`.
The fake board sends webcam photos the same way the real firmware should. Firmware details: [docs/board-protocol.md](docs/board-protocol.md).

### If detection is slow or poor

- `--imgsz 800` finds small things like keys better, but is slower.
- `--conf 0.15` shows more boxes (including more wrong ones). Watch which mistakes it makes; later chunks fix them with our own photos.
- `--device cpu` if Apple's GPU (`mps`) gives errors.
