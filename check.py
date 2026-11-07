"""Did teaching help? Scores detection on the TEST photos (every 5th saved photo, never learned from).

    python check.py
    python check.py --conf 0.15 --imgsz 800

Compares "words only" (objects.yaml) with "words + learning" (what teach.py learned).
Scored the way Nemo uses detection: for each item in each photo, is its best box on the right thing?
  found  = the item's box is on the item
  missed = the item was in the photo but not found
  wrong  = a box for an item where that item isn't (e.g. calling the AirPods case a mug)
"""
import argparse

from nemo.detector import Detector, load_objects
from nemo.learning import Learned, TeachStore, is_test_photo


def iou(a, b):
    x1, y1, x2, y2 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / max(union, 1e-6)


def score(detector, photos, names, conf, imgsz):
    totals = {n: {"found": 0, "missed": 0, "wrong": 0} for n in names}
    mixups = {}
    for image, truth in photos:
        dets = detector.detect(image, conf, imgsz)
        best = {}
        for d in dets:   # one box per item, like Nemo uses it
            if d["kind"] == "item" and d["name"] not in best:
                best[d["name"]] = d["box"]
        for name in names:
            mine = [t["box"] for t in truth if t["label"] == name]
            box = best.get(name)
            if box is not None and any(iou(box, t) >= 0.5 for t in mine):
                totals[name]["found"] += 1
                continue
            if box is not None:
                totals[name]["wrong"] += 1
                hit = max(truth, key=lambda t: iou(box, t["box"]), default=None)
                if hit and iou(box, hit["box"]) >= 0.5:
                    k = f"{name} -> was {hit['label']}"
                    mixups[k] = mixups.get(k, 0) + 1
            if mine:
                totals[name]["missed"] += 1
    return totals, mixups


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--objects", default="objects.yaml")
    ap.add_argument("--data", default="data/teach")
    ap.add_argument("--conf", type=float, default=0.2)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--device", default=None)
    args = ap.parse_args()

    objects = load_objects(args.objects)
    names = [o["name"] for o in objects]
    store = TeachStore(args.data)
    tests = [n for n in store.numbers() if is_test_photo(n)]
    if not tests:
        raise SystemExit("No test photos yet: every 5th photo saved in teach.py is one. Save at least 5.")
    photos = [store.load(n) for n in tests]
    detector = Detector(device=args.device)
    learned = Learned.load(store.learned_path, detector.model_name)
    print(f"\n{len(tests)} test photos. Learned from: {learned.summary()}\n")

    results = {}
    for title, extra in (("Words only", None), ("Words + learning", learned.for_detector())):
        detector.set_objects(objects, extra)
        results[title] = score(detector, photos, names, args.conf, args.imgsz)

    print(f"{'':18}" + "".join(f"{t:>28}" for t in results))
    print(f"{'item':18}" + "".join(f"{'found':>13}{'missed':>8}{'wrong':>7}" for _ in results))
    for name in names:
        row = "".join(f"{r[0][name]['found']:>13}{r[0][name]['missed']:>8}{r[0][name]['wrong']:>7}"
                      for r in results.values())
        print(f"{name[:18]:18}{row}")
    for title, (totals, mixups) in results.items():
        f = sum(t["found"] for t in totals.values())
        m = sum(t["missed"] for t in totals.values())
        w = sum(t["wrong"] for t in totals.values())
        right = f / max(f + m + w, 1)
        print(f"\n{title}: right {right:.0%} (found {f}, missed {m}, wrong {w})"
              + (f"\n  mix-ups: " + ", ".join(f"{k} x{v}" for k, v in mixups.items()) if mixups else ""))


if __name__ == "__main__":
    main()
