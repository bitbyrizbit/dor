import json
import pathlib
import numpy as np
import rasterio
from rasterio.features import rasterize
from scipy import ndimage as ndi
from shapely.geometry import shape

RAW = pathlib.Path("data/raw")
KX, KY = 111320.0 * np.cos(np.radians(28.0)), 110574.0
PLAC = ["placebo1", "placebo2", "placebo3"]
THRS = (2.5, 3.0, 3.5, 4.0)


def load(tag):
    with rasterio.open(RAW / f"diff_terrain_{tag}.tif") as s:
        return np.nan_to_num(s.read(1)), s.transform


data = {t: load(t)[0] for t in PLAC + ["event"]}
_, tf = load("event")
H, W = data["event"].shape
cls = np.load(RAW / "geom_class.npy")
px_x, px_y = abs(tf.a) * KX, abs(tf.e) * KY
good_km2 = float((cls == 0).sum()) * px_x * px_y / 1e6
feats = json.loads((RAW / "osm_rivers.geojson").read_text())["features"]
river = rasterize([(shape(f["geometry"]), 1) for f in feats], out_shape=(H, W),
                  transform=tf, all_touched=True).astype(bool)
dist = ndi.distance_transform_edt(~river, sampling=(px_y, px_x))


def make_sigma(refs):
    ms = np.mean([data[t] ** 2 for t in refs], axis=0)
    s = np.sqrt(ndi.uniform_filter(ms, size=31))
    return np.maximum(s, np.percentile(s[cls == 0], 5))


def stats(d, sigma, thr):
    z = ndi.uniform_filter(d / sigma, size=3)
    mask = np.abs(z) > thr
    lab, k = ndi.label(mask)
    sizes = ndi.sum(mask, lab, range(1, k + 1))
    keep = np.isin(lab, [i + 1 for i, s in enumerate(sizes) if s >= 30]) & (cls == 0)
    r, c = np.nonzero(keep)
    near = dist[r, c] < 200
    neg = float((z[r, c][near] < 0).mean()) if near.any() else float("nan")
    return {"n": int(len(r)), "per_km2": len(r) / good_km2,
            "aligned": float(near.sum()) / good_km2, "neg_aligned": neg}


rows = []
for held in PLAC:
    refs = [t for t in PLAC if t != held]
    sigma = make_sigma(refs)
    for thr in THRS:
        p = stats(data[held], sigma, thr)
        e = stats(data["event"], sigma, thr)
        rows.append({"held": held, "thr": thr,
                     "p_per_km2": round(p["per_km2"], 2), "p_aligned": round(p["aligned"], 2),
                     "p_n": p["n"], "p_neg_aligned": round(p["neg_aligned"], 2),
                     "e_per_km2": round(e["per_km2"], 2), "e_aligned": round(e["aligned"], 2),
                     "e_neg_aligned": round(e["neg_aligned"], 2),
                     "ratio_total": round(e["per_km2"] / max(p["per_km2"], 1e-6), 1),
                     "ratio_aligned": round(e["aligned"] / max(p["aligned"], 1e-6), 1)})
        print(rows[-1])

print("--- worst fold per threshold (lowest ratio, held-out placebo cell count)")
for thr in THRS:
    rr = [r for r in rows if r["thr"] == thr]
    wt = min(rr, key=lambda r: r["ratio_total"])
    wa = min(rr, key=lambda r: r["ratio_aligned"])
    print("z", thr, "| worst total ratio:", wt["ratio_total"], "held", wt["held"],
          "| worst aligned ratio:", wa["ratio_aligned"], "held", wa["held"],
          "| min held-out cells:", min(r["p_n"] for r in rr))
(RAW / "zscore_loo.json").write_text(json.dumps(rows, indent=2))