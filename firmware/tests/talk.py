# talk.py - laptop driver for the camera_blink_audio test sketch.
#
# Hold SPACE to record the mic, release to stop (saves question.wav).
#   'p' = play your last recording back on Nemo's speaker (mic + speaker echo test)
#   's' = send reply.wav to Nemo to speak it (where a future speech-to-text + answer
#         program would plug in: question.wav -> text -> answer -> reply.wav -> /play)
#   ESC = quit
#
# Needs: pip install pynput requests
# macOS: allow your terminal under System Settings -> Privacy & Security -> Accessibility,
# or the SPACE key will not be detected.

import requests
from pynput import keyboard

DEVICE = "http://172.20.10.x"   # the IP the Nemo screen shows (no /jpg)

recording = False


def on_press(key):
    global recording
    if key == keyboard.Key.space and not recording:
        recording = True
        try:
            requests.get(DEVICE + "/rec/start", timeout=2)
            print("recording... (release SPACE to stop)")
        except Exception as e:
            print("start error:", e)
    if key == keyboard.Key.esc:
        return False   # quit


def on_release(key):
    global recording
    if key == keyboard.Key.space and recording:
        recording = False
        try:
            r = requests.get(DEVICE + "/rec/stop", timeout=15)
            with open("question.wav", "wb") as f:
                f.write(r.content)
            print("saved question.wav (%d bytes)" % len(r.content))
        except Exception as e:
            print("stop error:", e)
    try:
        c = key.char
    except AttributeError:
        return
    if c == "p":      # echo: play back what you just said
        try:
            requests.get(DEVICE + "/play_last", timeout=15)
            print("played your recording on the speaker")
        except Exception as e:
            print(e)
    if c == "s":      # the reply: send reply.wav for Nemo to speak
        try:
            with open("reply.wav", "rb") as f:
                requests.post(DEVICE + "/play", files={"file": f}, timeout=20)
            print("sent reply.wav to the speaker")
        except Exception as e:
            print(e)


print("Hold SPACE = record, release = stop (saves question.wav)")
print("'p' = hear your recording on Nemo | 's' = send reply.wav | ESC = quit")
with keyboard.Listener(on_press=on_press, on_release=on_release) as L:
    L.join()
