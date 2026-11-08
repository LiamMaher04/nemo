"""Laura's live viewer: shows what Nemo's camera sees. ESC to quit.
Run: backend\\.venv\\Scripts\\python.exe viewer.py http://172.20.10.9/jpg
"""
import sys

import cv2
import numpy as np
import requests

URL = sys.argv[1] if len(sys.argv) > 1 else "http://172.20.10.9/jpg"  # address on Nemo's screen
print("Live over WiFi - press ESC in the window to quit")
s = requests.Session()
while True:
    try:
        r = s.get(URL, timeout=2)
        img = cv2.imdecode(np.frombuffer(r.content, np.uint8), cv2.IMREAD_COLOR)
        if img is not None:
            cv2.imshow("Nemo (WiFi)", img)
    except Exception:
        pass
    if cv2.waitKey(1) == 27:
        break
cv2.destroyAllWindows()
