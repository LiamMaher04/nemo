"""Test carer alerts decided in Spacetime and sent by the backend's alert sender loop.

Needs the notifier running (from notifier/:  bun run start). Then from the repo root:
    backend\\.venv\\Scripts\\python.exe -m backend.test_check_alerts
This sends ONE real text to CARER_PHONE. WARNING: calls reset_memory first.
"""

import time

import httpx
from fastapi.testclient import TestClient

from backend import seed_spacetime, settings
from backend import spacetime_client as st
from backend import test_memory as tm
from backend.main import app

LOCAL_UTC_OFFSET_HOURS = -6  # same as the Spacetime module


def local_minute(ts_ms: float) -> int:
    return int((ts_ms / 60000 + LOCAL_UTC_OFFSET_HOURS * 60) % 1440)


def check_time_ms() -> float:
    """Now, unless it's before 10:00 local (PILL_DUE_HOUR 9 + 60 min grace): then 12:00 local today."""
    now = time.time() * 1000
    if local_minute(now) >= 10 * 60:
        return now
    return now + (12 * 60 - local_minute(now)) * 60000


def carer_alerts() -> list[dict]:
    rows = st.sql("SELECT * FROM alerts WHERE channel = 'carer'")
    return sorted(rows, key=lambda r: r["id"])


def show(title: str) -> None:
    print(f"\n=== {title}")
    rows = carer_alerts()
    if not rows:
        print("  alerts: none")
    for r in rows:
        print(f"  alert #{r['id']} {r['type']} sent={r['sent']} message={r['message']!r}")


def wait_until_sent(timeout_s: float = 25) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        rows = carer_alerts()
        if rows and all(r["sent"] for r in rows):
            return True
        time.sleep(1)
    return False


def main() -> None:
    if not settings.CARER_ALERTS:
        print("CARER_ALERTS is off in .env, so this test can't text anyone. Set CARER_ALERTS=on to run it.")
        return
    try:
        httpx.post(f"{settings.NOTIFIER_URL}/alert", json={}, timeout=5)
    except Exception:
        print(f"The notifier isn't running at {settings.NOTIFIER_URL}. Start it: cd notifier; bun run start")
        return

    st.call("reset_memory")
    seed_spacetime.main()

    # Pill box on the desk 30 minutes ago, and no "used" event today.
    tm.clock_ms = time.time() * 1000 - 30 * 60 * 1000
    tm.sight("pill_box", "desk", "desk")
    tm.sight("pill_box", "desk", "desk")
    show("after seeding: pill box on the desk, not used today")

    when = check_time_ms()
    print(f"\nchecking as of local {local_minute(when) // 60:02d}:{local_minute(when) % 60:02d} "
          f"(pills due by 10:00: PILL_DUE_HOUR 9 + 60 min grace, no routine yet)")

    with TestClient(app):  # starts the app's alert sender loop (every 5 s)
        st.call("run_alert_checks_now", when)
        show("1st run_alert_checks_now -> one pills_not_taken alert raised")
        print(f"  sender loop texted it: {wait_until_sent()}")
        show("after the sender loop")

        st.call("run_alert_checks_now", when)
        time.sleep(12)  # give the sender loop two rounds, in case something new appeared
        show("2nd run_alert_checks_now -> no duplicate")
        n = sum(1 for r in carer_alerts() if r["type"] == "pills_not_taken")
        print(f"  pills_not_taken alerts: {n} (expected 1)")


if __name__ == "__main__":
    main()
