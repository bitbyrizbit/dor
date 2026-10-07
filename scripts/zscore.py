import json
import pathlib
import numpy as np
import rasterio
from rasterio.features import rasterize
from scipy import ndimage as ndi
from shapely.geometry import shape

RAW = pathlib.Path("data/raw")
KX, KY = 111320.0 * np.cos(np.radians(28.0)), 110574.0


def load(tag):
    with rasterio.open(RAW / f"diff_terrain_{tag}.tif") as s:
        return np.nan_to_num(s.read(1)), s.transform


REF = ["placebo2", "placebo3"]
TEST = ["placebo1", "event", "post"]
ref = [load(t)[0] for t in REF]
_, tf = load("event")
H, W = ref[0].shape
cls = np.load(RAW / "geom_class.npy")
hand = np.load(RAW / "hand_500.npy")
px_x, px_y = abs(tf.a) * KX, abs(tf.e) * KY
good_km2 = float((cls == 0).sum()) * px_x * px_y / 1e6

ms = np.mean([r ** 2 for r in ref], axis=0)
sigma = np.sqrt(ndi.uniform_filter(ms, size=31))
sigma = np.maximum(sigma, np.percentile(sigma[cls == 0], 5))
print("sigma dB p5/p50/p95 (good geometry):", np.percentile(sigma[cls == 0], [5, 50, 95]).round(2))

feats = json.loads((RAW / "osm_rivers.geojson").read_text())["features"]
river = rasterize([(shape(f["geometry"]), 1) for f in feats], out_shape=(H, W),
                  transform=tf, all_touched=True).astype(bool)
dist = ndi.distance_transform_edt(~river, sampling=(px_y, px_x))

results = {}
for thr in (2.5, 3.0, 4.0):
    for tag in TEST:
        d, _ = load(tag)
        z = ndi.uniform_filter(d / sigma, size=3)
        mask = np.abs(z) > thr
        lab, k = ndi.label(mask)
        sizes = ndi.sum(mask, lab, range(1, k + 1))
        keep = np.isin(lab, [i + 1 for i, s in enumerate(sizes) if s >= 30]) & (cls == 0)
        r, c = np.nonzero(keep)
        n = len(r)
        near = float((dist[r, c] < 200).mean()) if n else float("nan")
        low = float(np.nanmean(hand[r, c] < 20)) if n else float("nan")
        results[f"{tag}@{thr}"] = {
            "per_km2": round(n / good_km2, 2),
            "within_200m": round(near, 3),
            "hand_under_20": round(low, 3),
            "aligned_per_km2": round(n * near / good_km2, 2) if n else 0.0,
        }
    print("--- z threshold", thr)
    for tag in TEST:
        print(tag, results[f"{tag}@{thr}"])
    e, p = results[f"event@{thr}"], results[f"placebo1@{thr}"]
    print("event / held-out placebo | total:", round(e["per_km2"] / max(p["per_km2"], 1e-6), 1),
          "| river-aligned:", round(e["aligned_per_km2"] / max(p["aligned_per_km2"], 1e-6), 1))

(RAW / "zscore_summary.json").write_text(json.dumps(results, indent=2))