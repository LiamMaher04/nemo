# Vision on a Brev GPU box

Optional. Josie's vision pipeline (gates, face blur, YOLOE, DINOv2) runs on a Brev GPU instead of
the laptop. Everything else stays on the laptop: fetching frames from Nemo, Spacetime, Super VL,
the agent, speech and the live page. The laptop sends each frame to Brev through an SSH tunnel
and gets the same result back. No API keys go on the Brev box.

Brev can't reach Nemo (Nemo is on the phone hotspot), so this is the only way round.

Commands checked against the Brev docs (docs.nvidia.com/brev, CLI pages) on 8 Nov 2026. The Brev
CLI only runs on Windows inside WSL, so every `brev`, `ssh` and `scp` line below is typed in the
WSL Ubuntu terminal unless it says PowerShell.

Cost: a GPU box bills by the hour while it's running (an A10G was about $1/hr). Step 11 stops it.

## 1. WSL (once)

PowerShell, as administrator:

```bash
wsl --install -d Ubuntu-22.04
```

Restart if asked, open "Ubuntu 22.04" from the Start menu and make a user.

## 2. Install the Brev CLI (WSL)

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/brevdev/brev-cli/main/bin/install-latest.sh)"
```

```bash
brev --version
```

Don't use `sudo`. If it says `Failed to fetch release info from GitHub API`, the hotspot or venue
has hit GitHub's rate limit: try again on another network.

## 3. Log in

```bash
brev login
```

It opens the browser. Use the Brev account with the hackathon credits.

## 4. Make a GPU box

See what's available, cheapest first:

```bash
brev search --gpu-name A10G
```

Make one (an A10G with 24 GB is plenty; `--type` takes a fallback list, and any TYPE from the
search works):

```bash
brev create nemo-vision --type g5.xlarge,g5.2xlarge
```

```bash
brev ls
```

Wait until it says it's running, then:

```bash
brev refresh
```

## 5. Get the code on it

```bash
brev shell nemo-vision
```

You're now on the Brev box. The repo is public, so no login is needed:

```bash
mkdir -p ~/workspace && cd ~/workspace && git clone https://github.com/LiamMaher04/nemo.git && cd nemo
```

## 6. Python and the requirements (on the Brev box)

The requirements need Python 3.11 or newer. `uv` brings its own, whatever the box has:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh && source $HOME/.local/bin/env
```

```bash
uv venv --python 3.11 .venv && source .venv/bin/activate
```

```bash
uv pip install -r backend/requirements.txt -r backend/vision/requirements.txt
```

If a laptop-only package (`pynput`, `piper-tts`) won't build there, the vision server doesn't
need them. Install just what it does need instead:

```bash
uv pip install fastapi==0.115.6 "uvicorn[standard]==0.34.0" -r backend/vision/requirements.txt
```

Check the GPU is seen. It should print `True` and the GPU's name:

```bash
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

Type `exit` to leave the Brev box.

## 7. Copy the settings and reference photos (WSL, on the laptop)

The vision settings must match the laptop's, or the results differ (for example the default
`SHARPNESS_GATE` of 40 drops almost every hotel frame). This copies only the vision lines of the
laptop's `.env`, no keys:

```bash
grep -E '^(SHARPNESS_GATE|DETECT_CONF|DETECT_IMGSZ|DETECTOR_WEIGHTS|DUPLICATE_DIFF_MAX|KEEPALIVE_S|REFS_DIR|DINO_MODEL|DINO_REVISION|AREA_[A-Z_]+|ITEM_[A-Z_]+)=' /mnt/c/HackUTD/Nemo/.env > /tmp/nemo-vision.env && cat /tmp/nemo-vision.env
```

```bash
scp /tmp/nemo-vision.env nemo-vision:~/workspace/nemo/.env
```

The reference photos are gitignored, so they aren't in the clone. They live wherever `REFS_DIR`
points (the hotel set is `captures/grab/sorted`, about 7 MB). They're photos of the room, so this
puts them on the Brev box until it's deleted.

```bash
ssh nemo-vision "mkdir -p ~/workspace/nemo/captures/grab"
```

```bash
scp -r /mnt/c/HackUTD/Nemo/captures/grab/sorted nemo-vision:~/workspace/nemo/captures/grab/
```

If `REFS_DIR` is something else, copy that folder to the same path under `~/workspace/nemo/`.

## 8. Start the vision server (on the Brev box)

```bash
brev shell nemo-vision
```

```bash
cd ~/workspace/nemo && source .venv/bin/activate && nohup uvicorn backend.vision_server:app --host 127.0.0.1 --port 8001 > vision.log 2>&1 &
```

The first start downloads YOLOE and DINOv2, so give it a minute. Watch for
`vision ready on cuda` (Ctrl+C only stops the watching, not the server):

```bash
tail -f vision.log
```

```bash
curl -s localhost:8001/health
```

It should say `"loaded": true`, `"device": "cuda"`, the GPU's name, every area and item folder,
and the same settings as the laptop. Then `exit`. The server keeps running.

## 9. Tunnel it to the laptop (WSL, leave it running)

```bash
brev port-forward nemo-vision --port 8001:8001
```

Leave that terminal open. Check from Windows, in PowerShell:

```bash
curl.exe http://localhost:8001/health
```

## 10. Point the backend at it

In the laptop's `.env`:

```
VISION_URL=http://localhost:8001
```

Restart the backend. Its log should say `vision is REMOTE at http://localhost:8001: loaded=True on
cuda`, and `http://localhost:8000/health` shows `"mode": "remote"` under `vision`. Each frame's
log line now reads `vision 300 ms (server 60 ms, network 240 ms)`.

If `network` is about 2000 ms on most frames, try `VISION_URL=http://127.0.0.1:8001`. On Windows,
`localhost` tries IPv6 first and waits about 2 s before IPv4 whenever a connection has gone idle.
Tested on the laptop: `localhost` gave about 2050 ms network, `127.0.0.1` gave 4 to 14 ms. (Check
`curl.exe http://127.0.0.1:8001/health` works first, since the tunnel comes through WSL.)

If a frame isn't answered within 3 s it's skipped, with one warning line at most every 30 s. The
backend doesn't switch back to the laptop on its own.

## 11. Stop it when you're done (WSL)

```bash
brev stop nemo-vision
```

Next time: `brev start nemo-vision`, `brev refresh`, then steps 8, 9 and 10 again. The code,
venv, settings and photos are kept.

After the hackathon, `brev delete nemo-vision` removes it for good, photos included. It can't be
undone.

## Switching back to the laptop

Blank it in `.env`:

```
VISION_URL=
```

Restart the backend. Vision runs on the laptop exactly as before (its log says
`YOLOE ... loaded on cpu`, and `/health` shows `"mode": "local"`).
