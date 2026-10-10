import argparse
import json
from collections import defaultdict
from datetime import datetime, timedelta
import numpy as np

STAC = "https://stac.dataspace.copernicus.eu/v1"
GAPS = (6, 12, 24)
MIN_COV = 0.98


def local_scale(bbox):
    lat0 = (bbox[1] + bbox[3]) / 2
    return 111320.0 * float(np.cos(np.radians(lat0))), 110574.0


def _nominal(days):
    g = min(GAPS, key=lambda x: abs(x - days))
    return g if abs(g - days) <= 1 else None


def choose(scenes, ev, n_ref=3, n_val=3, years=3, max_post_lag=21):
    tracks = defaultdict(list)
    for s in scenes:
        tracks[s["track"]].append(s)
    for tr in tracks:
        tracks[tr].sort(key=lambda s: s["date"])
    events = []
    for tr, lst in tracks.items():
        best = None
        for a in lst:
            if a["date"] >= ev:
                continue
            for b in lst:
                g = _nominal((b["date"] - a["date"]).days)
                if g is None or b["date"] < ev or (b["date"] - ev).days > max_post_lag:
                    continue
                key = ((b["date"] - ev).days, g)
                if best is None or key < best[0]:
                    best = (key, a, b, g)
        if best:
            events.append({"track": tr, "pre": best[1], "post": best[2], "gap": best[3],
                           "post_lag_days": best[0][0], "pre_lag_days": (ev - best[1]["date"]).days})
    events.sort(key=lambda e: (e["post_lag_days"], e["gap"], e["track"]))
    out = {"events": events, "ref": [], "val": [], "notes": []}
    if not events:
        out["notes"].append("no same-track pair spans the date")
        return out
    top = events[0]
    lst, gap, pre = tracks[top["track"]], top["gap"], top["pre"]["date"]
    allp = [(a, b) for a in lst for b in lst
            if b["date"] > a["date"] and _nominal((b["date"] - a["date"]).days) == gap]
    out["ref"] = sorted([p for p in allp if p[1]["date"] <= pre and p[0]["date"] >= ev - timedelta(days=130)],
                        key=lambda p: -p[1]["date"].toordinal())[:n_ref]
    per_year = []
    for k in range(1, years + 1):
        c = ev - timedelta(days=365 * k)
        cand = [p for p in allp if abs((p[1]["date"] - c).days) <= 50]
        cand.sort(key=lambda p: abs((p[1]["date"] - c).days))
        per_year.append(cand)
    r = 0
    while len(out["val"]) < n_val and r < max((len(x) for x in per_year), default=0):
        for cand in per_year:
            if r < len(cand) and len(out["val"]) < n_val:
                out["val"].append(cand[r])
        r += 1
    if len(out["ref"]) < n_ref:
        out["notes"].append(f"only {len(out['ref'])} reference placebos found")
    if len(out["val"]) < n_val:
        out["notes"].append(f"only {len(out['val'])} validation placebos found")
    out["notes"].append("prior-year pairs are not certified flood free, check news before trusting a loud one")
    return out


def fetch(bbox, ev, years=3):
    from pystac_client import Client
    from pystac_client.stac_api_io import StacApiIO
    from shapely.geometry import box, shape
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    
    stac_io = StacApiIO()
    retry = Retry(total=5, backoff_factor=1.0, status_forcelist=[429, 502, 503, 504], allowed_methods=["GET", "POST", "HEAD"])
    stac_io.session.mount("https://", HTTPAdapter(max_retries=retry))
    cat = Client.open(STAC, stac_io=stac_io)
    aoi = box(*bbox)
    wins = [(ev - timedelta(days=130), ev + timedelta(days=40))]
    for k in range(1, years + 1):
        c = ev - timedelta(days=365 * k)
        wins.append((c - timedelta(days=50), c + timedelta(days=50)))
    seen = {}
    for a, b in wins:
        res = cat.search(collections=["sentinel-1-grd"], bbox=bbox,
                         datetime=f"{a}T00:00:00Z/{b}T23:59:59Z", max_items=2000)
        for it in sorted(res.items(), key=lambda i: i.id):
            p = it.properties
            ro, st = p.get("sat:relative_orbit"), p.get("sat:orbit_state")
            if ro is None or st is None or "vv" not in it.assets:
                continue
            cov = shape(it.geometry).intersection(aoi).area / aoi.area
            parts = it.id.split("_")
            dtk = "_".join(parts[6:8])
            if cov >= MIN_COV and dtk not in seen:
                seen[dtk] = {"id": it.id, "date": it.datetime.date(), "track": (int(ro), st),
                             "platform": p.get("platform"), "cov": round(cov, 3)}
    return list(seen.values())


def _ser(s):
    return {"date": str(s["date"]), "track": list(s["track"]), "platform": s["platform"], "id": s["id"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bbox", nargs=4, type=float, required=True, metavar=("LON0", "LAT0", "LON1", "LAT1"))
    ap.add_argument("--date", required=True)
    ap.add_argument("--n-ref", type=int, default=3)
    ap.add_argument("--n-val", type=int, default=3)
    a = ap.parse_args()
    ev = datetime.fromisoformat(a.date).date()
    scenes = fetch(a.bbox, ev)
    print("scenes with full coverage and VV:", len(scenes),
          "| tracks:", sorted({s["track"] for s in scenes}))
    res = choose(scenes, ev, a.n_ref, a.n_val)
    print("event pair candidates (best per track, shortest post lag first):")
    for e in res["events"]:
        print("  ", e["track"], e["pre"]["date"], "->", e["post"]["date"], "gap", e["gap"],
              "| pre lag", e["pre_lag_days"], "post lag", e["post_lag_days"],
              "|", e["pre"]["platform"], e["post"]["platform"])
    print("reference placebos:", [(str(p[0]["date"]), str(p[1]["date"])) for p in res["ref"]])
    print("validation placebos:", [(str(p[0]["date"]), str(p[1]["date"])) for p in res["val"]])
    print("notes:", res["notes"])
    if res["events"]:
        e = res["events"][0]
        print(json.dumps({"track": list(e["track"]), "event_pair": [str(e["pre"]["date"]), str(e["post"]["date"])],
                          "ref": [[str(p[0]["date"]), str(p[1]["date"])] for p in res["ref"]],
                          "val": [[str(p[0]["date"]), str(p[1]["date"])] for p in res["val"]]}))


if __name__ == "__main__":
    main()
