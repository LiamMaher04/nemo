"""Send one test carer text through the notifier and show the alerts row it wrote.

Start the notifier first (from notifier/:  bun run start), then from the repo root:
    backend\\.venv\\Scripts\\python.exe -m backend.test_alert
"""

from backend import alerts
from backend import spacetime_client as st

MESSAGE = "Nemo test: this is what a carer alert looks like"


def main() -> None:
    result = alerts.send_carer_alert("test", MESSAGE)
    print("send_carer_alert:", result)
    rows = sorted(st.sql("SELECT * FROM alerts"), key=lambda r: r["id"])
    if rows:
        r = rows[-1]
        print(f"alerts row #{r['id']}: type={r['type']} channel={r['channel']} sent={r['sent']} "
              f"message={r['message']!r}")


if __name__ == "__main__":
    main()
