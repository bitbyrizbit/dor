import json
import pathlib
import numpy as np
import rasterio
from rasterio.features import rasterize
from scipy import ndimage as ndi
from shapely.geometry import shape

RAW = pathlib.Path("data/raw")
KX, KY = 111320.0 * np.cos(np.radians(28.0)), 110574.0
REF = ["placebo1", "placebo2", "placebo3"]
NEW = ["y25_0721", "y25_0802", "y25_0814", "y25_0826", "y24_0714",
       "y24_0726", "y24_0807", "y24_0819", "y24_0831"]
POS = "pos2025"
FLOOR = 0.1


def load(tag):
    with rasterio.open(RAW / f"diff_terrain_{tag}.tif") as s:
        return np.nan_to_num(s.read(1)), s.transform


ref = [load(t)[0] for t in REF]
_, tf = load("event")
H, W = ref[0].shape
cls = np.load(RAW / "geom_class.npy")
px_x, px_y = abs(tf.a) * KX, abs(tf.e) * KY
good_km2 = float((cls == 0).sum()) * px_x * px_y / 1e6
sigma = np.sqrt(ndi.uniform_filter(np.mean([r ** 2 for r in ref], axis=0), size=31))
sigma = np.maximum(sigma, np.percentile(sigma[cls == 0], 5))
feats = json.loads((RAW / "osm_rivers.geojson").read_text())["features"]
river = rasterize([(shape(f["geometry"]), 1) for f in feats], out_shape=(H, W),
                  transform=tf, all_touched=True).astype(bool)
dist = ndi.distance_transform_edt(~river, sampling=(px_y, px_x))


def density(tag):
    d, _ = load(tag)
    z = ndi.uniform_filter(d / sigma, size=3)
    mask = z < -3.0
    lab, k = ndi.label(mask)
    sizes = ndi.sum(mask, lab, range(1, k + 1))
    keep = np.isin(lab, [i + 1 for i, s in enumerate(sizes) if s >= 30]) & (cls == 0)
    r, c = np.nonzero(keep)
    near = dist[r, c] < 200
    return {"dark_per_km2": round(len(r) / good_km2, 2),
            "aligned_per_km2": round(float(near.sum()) / good_km2, 2)}


out = {"event": density("event")}
print("event", out["event"])
print("--- in-sample 2026 placebos (they built sigma, so flattering, shown for reference)")
for t in REF:
    out[t] = density(t)
    print(t, out[t])
print("--- new placebos")
ev = out["event"]["aligned_per_km2"]
ratios = []
for t in NEW:
    if not (RAW / f"diff_terrain_{t}.tif").exists():
        print(t, "MISSING")
        continue
    out[t] = density(t)
    ratio = ev / max(out[t]["aligned_per_km2"], FLOOR)
    ratios.append((t, ratio))
    print(t, out[t], "| event/placebo:", round(ratio, 1), "| pass" if ratio >= 3 else "| FAIL")
if ratios:
    vals = [r for _, r in ratios]
    print("pairs run:", len(vals), "| min ratio:", round(min(vals), 1),
          "| median ratio:", round(float(np.median(vals)), 1),
          "| failures:", [t for t, r in ratios if r < 3])
if (RAW / f"diff_terrain_{POS}.tif").exists():
    out[POS] = density(POS)
    med = float(np.median([out[t]["aligned_per_km2"] for t, _ in ratios])) if ratios else float("nan")
    print("positive control", POS, out[POS], "| vs median placebo:",
          round(out[POS]["aligned_per_km2"] / max(med, FLOOR), 1))
(RAW / "frozen_rule.json").write_text(json.dumps(out, indent=2))