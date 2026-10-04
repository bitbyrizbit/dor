import json
import pathlib
import numpy as np
import requests
import rasterio
from scipy import ndimage as ndi
from shapely.geometry import shape, Point
from shapely.ops import unary_union, transform
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BBOX = [85.10, 27.85, 85.45, 28.25]
SNAPSHOT = "2026-07-27"
RAW = pathlib.Path("data/raw")

with rasterio.open(RAW / "diff_geo.tif") as src:
    diff = src.read(1)
    tf = src.transform


import time

HEADERS = {"User-Agent": "dor-hackathon-prototype (student project, contact: your_real_email)"}


def fetch_ohsome():
    r = requests.post(
        "https://api.ohsome.org/v1/elements/geometry",
        data={"bboxes": ",".join(map(str, BBOX)), "time": SNAPSHOT,
              "filter": "waterway=river and type:way", "properties": "tags"},
        headers=HEADERS, timeout=180)
    print("ohsome status:", r.status_code)
    if r.status_code != 200:
        return None
    return r.json().get("features", [])


def fetch_overpass(url):
    q = (f'[out:json][timeout:90][date:"{SNAPSHOT}T00:00:00Z"];'
         f'way["waterway"="river"]({BBOX[1]},{BBOX[0]},{BBOX[3]},{BBOX[2]});out geom qt;')
    r = requests.post(url, data={"data": q}, headers=HEADERS, timeout=150)
    print("overpass status:", url, r.status_code)
    if r.status_code != 200:
        return None
    els = r.json().get("elements", [])
    return [{"type": "Feature", "properties": {},
             "geometry": {"type": "LineString",
                          "coordinates": [[p["lon"], p["lat"]] for p in e["geometry"]]}}
            for e in els if "geometry" in e]


print("fetching osm rivers at", SNAPSHOT)
feats, source = None, None
for name, fn in [
    ("ohsome", fetch_ohsome),
    ("overpass-de", lambda: fetch_overpass("https://overpass-api.de/api/interpreter")),
    ("overpass-kumi", lambda: fetch_overpass("https://overpass.kumi.systems/api/interpreter")),
]:
    for attempt in (1, 2):
        try:
            feats = fn()
        except requests.RequestException as e:
            print(name, "error:", repr(e))
            feats = None
        if feats:
            source = name
            break
        time.sleep(10)
    if feats:
        break

if not feats:
    raise SystemExit("all osm sources failed, see plan b")
print("source:", source, "| river ways:", len(feats))
lines = unary_union([shape(f["geometry"]) for f in feats])

(RAW / "osm_rivers.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": feats}))

# strong negative change, connected blobs only
smooth = ndi.uniform_filter(np.nan_to_num(diff), size=3)
mask = smooth < -3.0
lab, n = ndi.label(mask)
sizes = ndi.sum(mask, lab, range(1, n + 1))
keep = np.isin(lab, [i + 1 for i, s in enumerate(sizes) if s >= 30])
rows, cols = np.nonzero(keep)
print("strong-change pixels in blobs >= 30 px:", len(rows))
if len(rows) < 50:
    raise SystemExit("too few strong pixels, lower the -3.0 threshold")

rng = np.random.default_rng(0)
idx = rng.choice(len(rows), size=min(3000, len(rows)), replace=False)
xs, ys = rasterio.transform.xy(tf, rows[idx], cols[idx])

KX, KY = 111320.0 * np.cos(np.radians(28.0)), 110574.0
to_m = lambda x, y, z=None: (np.asarray(x) * KX, np.asarray(y) * KY)
lines_m = transform(to_m, lines)
d = np.array([Point(x * KX, y * KY).distance(lines_m) for x, y in zip(xs, ys)])
print("distance to nearest osm river (m): p25/median/p75/p90:",
      np.percentile(d, [25, 50, 75, 90]).round(0))

fig, ax = plt.subplots(figsize=(9, 10))
ax.imshow(diff, cmap="RdBu", vmin=-4, vmax=4, extent=[BBOX[0], BBOX[2], BBOX[1], BBOX[3]])
geoms = lines.geoms if hasattr(lines, "geoms") else [lines]
for g in geoms:
    x, y = g.xy
    ax.plot(x, y, color="lime", lw=0.8)
ax.set_title("change map with pre-event osm rivers (green)")
plt.savefig(RAW / "diff_vs_osm.png", dpi=110, bbox_inches="tight")