import json
import pathlib
import numpy as np
import rasterio
from scipy import ndimage as ndi
from PIL import Image

RAW, OUT = pathlib.Path("data/raw"), pathlib.Path("outputs")
REF = ["placebo1", "placebo2", "placebo3"]
NEW = ["y25_0721", "y25_0802", "y25_0814", "y25_0826", "y24_0714", "y24_0726", "y24_0807", "y24_0819", "y24_0831"]
WIN = 21
KX, KY = 111320.0 * np.cos(np.radians(28.0)), 110574.0


def load(tag):
    with rasterio.open(RAW / f"diff_terrain_{tag}.tif") as s:
        return np.nan_to_num(s.read(1)), s.transform


ref = [load(t)[0] for t in REF]
_, tf = load("event")
cls = np.load(RAW / "geom_class.npy")
good = cls == 0
sigma = np.sqrt(ndi.uniform_filter(np.mean([r ** 2 for r in ref], axis=0), size=31))
sigma = np.maximum(sigma, np.percentile(sigma[good], 5))
good_frac = ndi.uniform_filter(good.astype(np.float32), size=WIN)


def smap(tag):
    d, _ = load(tag)
    z = ndi.uniform_filter(d / sigma, size=3)
    mask = (z < -3.0) & good
    lab, k = ndi.label(mask)
    sizes = ndi.sum(mask, lab, range(1, k + 1))
    keep = np.isin(lab, [i + 1 for i, s in enumerate(sizes) if s >= 30])
    return ndi.uniform_filter(keep.astype(np.float32), size=WIN)


ev_map = smap("event")
k_map = np.zeros(ev_map.shape, np.uint8)
for t in NEW:
    k_map += (smap(t) >= ev_map).astype(np.uint8)
    print("placebo done:", t)
np.savez_compressed(RAW / "score_maps.npz", ev_map=ev_map, k_map=k_map, good_frac=good_frac.astype(np.float32))

# consistency check against the per-edge evidence
EV = np.load(RAW / "edge_evidence.npz", allow_pickle=True)
H, W = ev_map.shape
r = np.floor((EV["lat"] - tf.f) / tf.e).astype(int)
c = np.floor((EV["lon"] - tf.c) / tf.a).astype(int)
ok = (r >= 0) & (r < H) & (c >= 0) & (c < W)
print("max abs difference vs edge_evidence score:", float(np.abs(ev_map[r[ok], c[ok]] - EV["ev"][ok]).max()),
      "| edges where k differs:", int((k_map[r[ok], c[ok]] != EV["k_ev"][ok]).sum()))

# evidence zone overlay and areas
gok = good_frac >= 0.5
strict = gok & (ev_map >= 0.05) & (k_map <= 0)
loose = gok & (ev_map >= 0.02) & (k_map <= 2)
rgba = np.zeros((H, W, 4), np.uint8)
rgba[loose] = (230, 126, 34, 110)
rgba[strict] = (192, 57, 43, 170)
OUT.mkdir(exist_ok=True)
Image.fromarray(rgba).save(OUT / "footprint.png", optimize=True)
px_km2 = abs(tf.a) * KX * abs(tf.e) * KY / 1e6
info = {"bounds": {"west": tf.c, "north": tf.f, "east": tf.c + W * tf.a, "south": tf.f + H * tf.e},
        "km2_strict": round(float(strict.sum()) * px_km2, 1), "km2_loose": round(float(loose.sum()) * px_km2, 1),
        "km2_assessable": round(float(gok.sum()) * px_km2, 1), "km2_total": round(H * W * px_km2, 1)}
(RAW / "footprint.json").write_text(json.dumps(info, indent=1), encoding="utf-8")
print("evidence zone km2:", info)
