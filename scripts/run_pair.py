import json
import pathlib
import sys
import numpy as np
import rasterio
from rasterio.features import rasterize
from rasterio.windows import Window
from scipy import ndimage as ndi
from scipy.ndimage import shift as nd_shift
from shapely.geometry import shape
from skimage.registration import phase_cross_correlation
from pystac_client import Client
from dor.acquire.s3_env import setup_cdse_s3

STAC = "https://stac.dataspace.copernicus.eu/v1"
BBOX = [85.10, 27.85, 85.45, 28.25]
PAD_DEG, PAD_PX, M = 0.25, 300, 1500
KX, KY = 111320.0 * np.cos(np.radians(28.0)), 110574.0
RAW = pathlib.Path("data/raw")

pre_day, post_day, tag = sys.argv[1], sys.argv[2], sys.argv[3]
setup_cdse_s3()
cat = Client.open(STAC)


def find_scene(day):
    res = cat.search(collections=["sentinel-1-grd"], bbox=BBOX,
                     datetime=f"{day}T00:00:00Z/{day}T23:59:59Z")
    for it in res.items():
        p = it.properties
        if p.get("sat:relative_orbit") == 85 and p.get("sat:orbit_state") == "ascending":
            return it
    raise SystemExit(f"no track 85 ascending scene on {day}")


def read_window(item):
    with rasterio.open(item.assets["vv"].href) as src:
        pts, _ = src.gcps
        loc = [g for g in pts if BBOX[0] - PAD_DEG <= g.x <= BBOX[2] + PAD_DEG
               and BBOX[1] - PAD_DEG <= g.y <= BBOX[3] + PAD_DEG]
        if len(loc) < 6:
            raise SystemExit("too few gcps near aoi")
        A = np.array([[g.x, g.y, 1.0] for g in loc])
        cx = np.linalg.lstsq(A, np.array([g.col for g in loc]), rcond=None)[0]
        ry = np.linalg.lstsq(A, np.array([g.row for g in loc]), rcond=None)[0]
        corners = [(BBOX[0], BBOX[1]), (BBOX[0], BBOX[3]), (BBOX[2], BBOX[1]), (BBOX[2], BBOX[3])]
        cc = [cx @ [x, y, 1.0] for x, y in corners]
        rr = [ry @ [x, y, 1.0] for x, y in corners]
        c0, c1 = max(int(min(cc)) - PAD_PX, 0), min(int(max(cc)) + PAD_PX, src.width)
        r0, r1 = max(int(min(rr)) - PAD_PX, 0), min(int(max(rr)) + PAD_PX, src.height)
        arr = src.read(1, window=Window(c0, r0, c1 - c0, r1 - r0))
    return arr, c0, r0, pts


pre_it, post_it = find_scene(pre_day), find_scene(post_day)
print("pre :", pre_it.id)
print("post:", post_it.id)
pre, c0, r0, pts = read_window(pre_it)
post, _, _, _ = read_window(post_it)
pre, post = pre.astype(np.float32), post.astype(np.float32)
h, w = min(pre.shape[0], post.shape[0]), min(pre.shape[1], post.shape[1])
pre, post = pre[:h, :w], post[:h, :w]
valid = (pre > 0) & (post > 0)


def to_db(a):
    return 20 * np.log10(np.clip(a, 1, None))


def smooth_db(a, k=7):
    return 10 * np.log10(np.clip(uniform_sq(a, k), 1, None))


def uniform_sq(a, k):
    return ndi.uniform_filter(a.astype(np.float32) ** 2, size=k)


cy, cx, s = h // 2, w // 2, 1024
a = to_db(pre)[cy - s:cy + s, cx - s:cx + s]
b = to_db(post)[cy - s:cy + s, cx - s:cx + s]
offset, perr, _ = phase_cross_correlation(a - a.mean(), b - b.mean(), upsample_factor=10)
print("coregistration offset (rows, cols):", offset)
post = nd_shift(post, offset, order=1, mode="constant", cval=0)
valid &= post > 0
diff = smooth_db(post) - smooth_db(pre)
diff = diff - float(np.median(diff[valid]))
diff[~valid] = 0
print("diff percentiles 1/5/50/95/99 (dB):", np.percentile(diff[valid], [1, 5, 50, 95, 99]).round(2))

# terrain-aware geocoding, model fitted on this pre scene's gcps
sel = [g for g in pts if c0 - M <= g.col <= c0 + w + M and r0 - M <= g.row <= r0 + h + M]
gx = np.array([g.x for g in sel]); gy = np.array([g.y for g in sel]); gz = np.array([g.z for g in sel])
gcol = np.array([g.col for g in sel]); grow = np.array([g.row for g in sel])
x0, y0, z0 = gx.mean(), gy.mean(), gz.mean()


def design(x, y, z):
    u, v, t = (np.asarray(x) - x0) * 10.0, (np.asarray(y) - y0) * 10.0, (np.asarray(z) - z0) / 1000.0
    return np.stack([np.ones_like(u), u, v, t, u * v, u * u, v * v], axis=1)

def find_scene(day):
    res = cat.search(collections=["sentinel-1-grd"], bbox=BBOX,
                     datetime=f"{day}T00:00:00Z/{day}T23:59:59Z")
    hits = [it for it in res.items()
            if it.properties.get("sat:relative_orbit") == 85
            and it.properties.get("sat:orbit_state") == "ascending"]
    if not hits:
        raise SystemExit(f"no track 85 ascending scene on {day}")
    hits.sort(key=lambda i: i.id)
    if len(hits) > 1:
        print("duplicate products on", day, "using", hits[0].id)
    return hits[0]
    
Ag = design(gx, gy, gz)
cc = np.linalg.lstsq(Ag, gcol, rcond=None)[0]
rc = np.linalg.lstsq(Ag, grow, rcond=None)[0]
res = np.hypot(Ag @ cc - gcol, Ag @ rc - grow)
print("gcps used:", len(sel), "| fit residual px mean/max:", round(float(res.mean()), 1), round(float(res.max()), 1))

with rasterio.open(RAW / "dem_geo.tif") as d:
    dem = d.read(1)
    tf = d.transform
H, W = dem.shape
dem = np.where(np.isfinite(dem), dem, np.nanmedian(dem))
out = np.full((H, W), np.nan, np.float32)
lon = tf.c + (np.arange(W) + 0.5) * tf.a
for r in range(0, H, 500):
    r1 = min(r + 500, H)
    lat = tf.f + (np.arange(r, r1) + 0.5) * tf.e
    LON, LAT = np.meshgrid(lon, lat)
    A = design(LON.ravel(), LAT.ravel(), dem[r:r1].ravel())
    out[r:r1] = ndi.map_coordinates(diff, [(A @ rc).reshape(LON.shape) - r0,
                                           (A @ cc).reshape(LON.shape) - c0],
                                    order=1, mode="constant", cval=np.nan)
with rasterio.open(RAW / f"diff_terrain_{tag}.tif", "w", driver="GTiff", height=H, width=W, count=1,
                   dtype="float32", crs="EPSG:4326", transform=tf, nodata=np.nan) as o:
    o.write(out, 1)

# metrics, identical for every pair
cls = np.load(RAW / "geom_class.npy")
hand = np.load(RAW / "hand_500.npy")
px_x, px_y = abs(tf.a) * KX, abs(tf.e) * KY
sm = ndi.uniform_filter(np.nan_to_num(out), size=3)
mask = np.abs(sm) > 3.0
lab, k = ndi.label(mask)
sizes = ndi.sum(mask, lab, range(1, k + 1))
keep = np.isin(lab, [i + 1 for i, s_ in enumerate(sizes) if s_ >= 30]) & (cls == 0)
rows, cols = np.nonzero(keep)
good_km2 = float((cls == 0).sum()) * px_x * px_y / 1e6
neg = float((sm[keep] < 0).mean()) if len(rows) else float("nan")

feats = json.loads((RAW / "osm_rivers.geojson").read_text())["features"]
river = rasterio.features.rasterize([(shape(f["geometry"]), 1) for f in feats], out_shape=(H, W),
                                    transform=tf, all_touched=True).astype(bool)
dist = ndi.distance_transform_edt(~river, sampling=(px_y, px_x))
hv = hand[rows, cols]
lats = tf.f + (rows + 0.5) * tf.e
bands, _ = np.histogram(lats, bins=np.linspace(BBOX[1], BBOX[3], 5))
summary = {
    "tag": tag, "pre": pre_day, "post": post_day,
    "strong_cells": int(len(rows)),
    "strong_per_km2_good": round(len(rows) / good_km2, 2),
    "share_negative": round(neg, 3),
    "hand_under_20": round(float(np.nanmean(hv < 20)), 3),
    "within_200m_river": round(float((dist[rows, cols] < 200).mean()), 3),
    "south_to_north_counts": bands.tolist(),
}
print("SUMMARY", json.dumps(summary))
(RAW / f"summary_{tag}.json").write_text(json.dumps(summary, indent=2))