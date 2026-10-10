import json
import pathlib
import time
import numpy as np
import requests
import rasterio

RAW, OUT = pathlib.Path("data/raw"), pathlib.Path("outputs")
BBOX = [85.10, 27.85, 85.45, 28.25]
SNAP = "2026-07-27T00:00:00Z"
HEADERS = {"User-Agent": "dor-hackathon-prototype (student project, github.com/bitbyrizbit)"}
URLS = ["https://overpass-api.de/api/interpreter", "https://overpass.private.coffee/api/interpreter", "https://overpass.kumi.systems/api/interpreter"]
NX, NY = 3, 3
STRICT, LOOSE = (0.05, 0), (0.02, 2)


def tile(i, j):
    f = RAW / f"osm_bld_{i}_{j}.json"
    if f.exists():
        return json.loads(f.read_text())
    w0 = BBOX[0] + (BBOX[2] - BBOX[0]) * i / NX
    w1 = BBOX[0] + (BBOX[2] - BBOX[0]) * (i + 1) / NX
    s0 = BBOX[1] + (BBOX[3] - BBOX[1]) * j / NY
    s1 = BBOX[1] + (BBOX[3] - BBOX[1]) * (j + 1) / NY
    q = f'[out:json][timeout:300][date:"{SNAP}"];way["building"]({s0},{w0},{s1},{w1});out meta center qt;'
    for url in URLS:
        for attempt in (1, 2):
            try:
                r = requests.post(url, data={"data": q}, headers=HEADERS, timeout=320)
                print("tile", i, j, url, r.status_code)
                if r.status_code == 200:
                    slim = [{"id": e["id"], "lat": e["center"]["lat"], "lon": e["center"]["lon"],
                             "ts": e.get("timestamp", "")} for e in r.json().get("elements", []) if "center" in e]
                    f.write_text(json.dumps(slim))
                    return slim
            except requests.RequestException as ex:
                print("tile", i, j, "error", repr(ex)[:120])
            time.sleep(20)
    raise SystemExit(f"tile {i},{j} failed on all servers, rerun to resume, finished tiles are cached")


seen = {}
for i in range(NX):
    for j in range(NY):
        for b in tile(i, j):
            if BBOX[0] <= b["lon"] <= BBOX[2] and BBOX[1] <= b["lat"] <= BBOX[3]:
                seen[b["id"]] = b
bl = list(seen.values())
newest = max(b["ts"] for b in bl)
print("buildings:", len(bl), "| newest edit timestamp:", newest)
if newest > SNAP:
    raise SystemExit("DATA RULE: element newer than the snapshot, do not use these files")

S = np.load(RAW / "score_maps.npz")
ev_map, k_map, gf = S["ev_map"], S["k_map"], S["good_frac"]
with rasterio.open(RAW / "dem_geo.tif") as d:
    tf, H, W = d.transform, d.height, d.width
lon = np.array([b["lon"] for b in bl])
lat = np.array([b["lat"] for b in bl])
r = np.floor((lat - tf.f) / tf.e).astype(int)
c = np.floor((lon - tf.c) / tf.a).astype(int)
ok = (r >= 0) & (r < H) & (c >= 0) & (c < W)
e, k, g = np.zeros(len(bl)), np.full(len(bl), 99), np.zeros(len(bl))
e[ok], k[ok], g[ok] = ev_map[r[ok], c[ok]], k_map[r[ok], c[ok]], gf[r[ok], c[ok]]
assess = ok & (g >= 0.5)
strict = assess & (e >= STRICT[0]) & (k <= STRICT[1])
loose = assess & (e >= LOOSE[0]) & (k <= LOOSE[1])
summ = {"snapshot": SNAP[:10], "total": len(bl), "assessable": int(assess.sum()), "unassessed": int((~assess).sum()),
        "strict": int(strict.sum()), "loose": int(loose.sum()), "newest_edit": newest}
print(summ)
(RAW / "buildings_summary.json").write_text(json.dumps(summ, indent=1), encoding="utf-8")
OUT.mkdir(exist_ok=True)
with open(OUT / "buildings_flagged.csv", "w", encoding="utf-8") as f:
    f.write("osm_id,lat,lon,zone\n")
    for i in np.nonzero(loose)[0]:
        f.write(f"{bl[i]['id']},{lat[i]:.5f},{lon[i]:.5f},{'strict' if strict[i] else 'loose'}\n")
