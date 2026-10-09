import json
import pathlib
import numpy as np
import rasterio
from scipy import ndimage as ndi

RAW = pathlib.Path("data/raw")
REF = ["placebo1", "placebo2", "placebo3"]
NEW = ["y25_0721", "y25_0802", "y25_0814", "y25_0826", "y24_0714",
       "y24_0726", "y24_0807", "y24_0819", "y24_0831"]
WIN = 21
MIN_SCORE = 0.05
KX, KY = 111320.0 * np.cos(np.radians(28.0)), 110574.0


def load(tag):
    with rasterio.open(RAW / f"diff_terrain_{tag}.tif") as s:
        return np.nan_to_num(s.read(1)), s.transform


ref = [load(t)[0] for t in REF]
_, tf = load("event")
H, W = ref[0].shape
cls = np.load(RAW / "geom_class.npy")
good = cls == 0
sigma = np.sqrt(ndi.uniform_filter(np.mean([r ** 2 for r in ref], axis=0), size=31))
sigma = np.maximum(sigma, np.percentile(sigma[good], 5))
good_frac = ndi.uniform_filter(good.astype(np.float32), size=WIN)

ways = json.loads((RAW / "osm_roads_raw.json").read_text())
wid, na, nb, lon, lat, ln, isb, hw = [], [], [], [], [], [], [], []
for w in ways:
    nodes, geom, tags = w.get("nodes", []), w.get("geometry", []), w.get("tags", {})
    if len(nodes) != len(geom) or len(nodes) < 2:
        continue
    b = tags.get("bridge", "no") not in ("no", "")
    for i in range(len(nodes) - 1):
        x0, y0, x1, y1 = geom[i]["lon"], geom[i]["lat"], geom[i + 1]["lon"], geom[i + 1]["lat"]
        wid.append(w["id"]); na.append(nodes[i]); nb.append(nodes[i + 1])
        lon.append((x0 + x1) / 2); lat.append((y0 + y1) / 2)
        ln.append(float(np.hypot((x1 - x0) * KX, (y1 - y0) * KY)))
        isb.append(b); hw.append(tags.get("highway", ""))
wid, na, nb = np.array(wid), np.array(na), np.array(nb)
lon, lat, ln, isb, hw = np.array(lon), np.array(lat), np.array(ln), np.array(isb), np.array(hw)
r = np.floor((lat - tf.f) / tf.e).astype(int)
c = np.floor((lon - tf.c) / tf.a).astype(int)
inside = (r >= 0) & (r < H) & (c >= 0) & (c < W)
rc, cc = np.clip(r, 0, H - 1), np.clip(c, 0, W - 1)
print("edges:", len(wid), "| inside aoi:", int(inside.sum()),
      "| road km inside:", round(float(ln[inside].sum()) / 1000, 1))


def sample(tag):
    d, _ = load(tag)
    z = ndi.uniform_filter(d / sigma, size=3)
    mask = (z < -3.0) & good
    lab, k = ndi.label(mask)
    sizes = ndi.sum(mask, lab, range(1, k + 1))
    keep = np.isin(lab, [i + 1 for i, s in enumerate(sizes) if s >= 30])
    return ndi.uniform_filter(keep.astype(np.float32), size=WIN)[rc, cc]


ev = sample("event")
pl = np.stack([sample(t) for t in NEW])
gf = good_frac[rc, cc]
assess = inside & (gf >= 0.5)
km = lambda m: round(float(ln[m].sum()) / 1000, 1)
print("assessable road km:", km(assess), "| unable to assess (poor geometry) km:", km(inside & (gf < 0.5)))

k_ev = (pl >= ev).sum(axis=0)
flag_ev = assess & (ev >= MIN_SCORE) & (k_ev == 0)
print("EVENT flagged km (above all 9 placebos, score >= 0.05):", km(flag_ev),
      "| share of assessable:", round(km(flag_ev) / km(assess), 4))
loo = []
for i in range(len(NEW)):
    others = np.delete(pl, i, axis=0)
    k_i = (others >= pl[i]).sum(axis=0)
    f = assess & (pl[i] >= MIN_SCORE) & (k_i == 0)
    loo.append(km(f))
    print("placebo", NEW[i], "flagged km vs the other 8:", km(f))
print("event flagged km:", km(flag_ev), "| placebo flagged km median / max:",
      round(float(np.median(loo)), 1), max(loo))

for name, m in (("bridges", isb), ("all other roads", ~isb)):
    sel = assess & m
    print(name, "| assessable km:", km(sel), "| flagged km:", km(flag_ev & m),
          "| share:", round(km(flag_ev & m) / max(km(sel), 1e-6), 4))

bw = {}
for i in np.nonzero(isb & inside)[0]:
    bw.setdefault(int(wid[i]), []).append(i)
rows = []
for w_, idx in bw.items():
    idx = np.array(idx)
    j = idx[np.argmax(ev[idx])]
    rows.append((float(ev[j]), int(k_ev[j]), w_, float(lat[j]), float(lon[j]), float(gf[j])))
rows.sort(reverse=True)
print("bridge ways in aoi:", len(bw), "| with event score >= 0.05 and above all placebos:",
      sum(1 for s, k_, *_ in rows if s >= MIN_SCORE and k_ == 0))
print("top 12 bridge ways: score, placebos at or above, way id, lat, lon, good geometry share")
for row in rows[:12]:
    print("  ", round(row[0], 3), row[1], row[2], round(row[3], 4), round(row[4], 4), round(row[5], 2))

np.savez(RAW / "edge_evidence.npz", wid=wid, na=na, nb=nb, lon=lon, lat=lat, length=ln,
         bridge=isb, hw=hw, inside=inside, assess=assess, ev=ev, k_ev=k_ev, pl=pl)