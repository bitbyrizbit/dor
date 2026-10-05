import json
import pathlib
import numpy as np
import rasterio
from scipy import ndimage as ndi
from shapely.geometry import shape, Point
from shapely.ops import unary_union, transform
from pystac_client import Client
from dor.acquire.s3_env import setup_cdse_s3

STAC = "https://stac.dataspace.copernicus.eu/v1"
PRE = "S1D_IW_GRDH_1SDV_20260816T122141_20260816T122206_004151_007980_B091_COG"
RAW = pathlib.Path("data/raw")

diff = np.load(RAW / "diff_db.npy")
meta = json.loads((RAW / "pre_meta.json").read_text())
c0, r0 = meta["col_off"], meta["row_off"]
h, w = diff.shape

setup_cdse_s3()
it = next(Client.open(STAC).search(collections=["sentinel-1-grd"], ids=[PRE]).items())
with rasterio.open(it.assets["vv"].href) as src:
    pts, _ = src.gcps

M = 1500
sel = [g for g in pts if c0 - M <= g.col <= c0 + w + M and r0 - M <= g.row <= r0 + h + M]
x = np.array([g.x for g in sel])
y = np.array([g.y for g in sel])
z = np.array([g.z for g in sel])
col = np.array([g.col for g in sel])
row = np.array([g.row for g in sel])
n = len(x)
print("gcps used:", n, "| z range m:", z.min().round(0), z.max().round(0))
x0, y0, z0 = x.mean(), y.mean(), z.mean()


def design(x, y, z, kind):
    u = (x - x0) * 10.0
    v = (y - y0) * 10.0
    t = (z - z0) / 1000.0
    cols = [np.ones_like(u), u, v]
    if kind in ("xyz", "xyz2"):
        cols.append(t)
    if kind == "xyz2":
        cols += [u * v, u * u, v * v]
    return np.stack(cols, axis=1)


def fit(kind, idx):
    A = design(x[idx], y[idx], z[idx], kind)
    return (np.linalg.lstsq(A, col[idx], rcond=None)[0],
            np.linalg.lstsq(A, row[idx], rcond=None)[0])


allidx = np.arange(n)
loo_mean = {}
for kind in ("xy", "xyz", "xyz2"):
    cc, rc = fit(kind, allidx)
    A = design(x, y, z, kind)
    res = np.hypot(A @ cc - col, A @ rc - row)
    loo = []
    for i in range(n):
        idx = np.delete(allidx, i)
        c_, r_ = fit(kind, idx)
        a = design(x[i:i + 1], y[i:i + 1], z[i:i + 1], kind)
        loo.append(np.hypot((a @ c_)[0] - col[i], (a @ r_)[0] - row[i]))
    loo_mean[kind] = float(np.mean(loo))
    print(kind, "fit residual px mean/max:", round(float(res.mean()), 1), round(float(res.max()), 1),
          "| leave-one-out px mean/max:", round(float(np.mean(loo)), 1), round(float(np.max(loo)), 1))

kind = min(("xyz", "xyz2"), key=lambda k: loo_mean[k])
print("model chosen:", kind)
cc, rc = fit(kind, allidx)

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
    A = design(LON.ravel(), LAT.ravel(), dem[r:r1].ravel(), kind)
    cpos = (A @ cc).reshape(LON.shape) - c0
    rpos = (A @ rc).reshape(LON.shape) - r0
    out[r:r1] = ndi.map_coordinates(diff, [rpos, cpos], order=1, mode="constant", cval=np.nan)
print("terrain-geocoded valid fraction:", round(float(np.isfinite(out).mean()), 3))

with rasterio.open(RAW / "diff_terrain.tif", "w", driver="GTiff", height=H, width=W, count=1,
                   dtype="float32", crs="EPSG:4326", transform=tf, nodata=np.nan) as o:
    o.write(out, 1)

# same checks as before, no shift applied
smooth = ndi.uniform_filter(np.nan_to_num(out), size=3)
mask = smooth < -3.0
lab, k = ndi.label(mask)
sizes = ndi.sum(mask, lab, range(1, k + 1))
keep = np.isin(lab, [i + 1 for i, s in enumerate(sizes) if s >= 30])
rows, cols = np.nonzero(keep)
print("strong-change pixels:", len(rows))
rng = np.random.default_rng(0)
idx = rng.choice(len(rows), size=min(3000, len(rows)), replace=False)
xs, ys = rasterio.transform.xy(tf, rows[idx], cols[idx])

KX, KY = 111320.0 * np.cos(np.radians(28.0)), 110574.0
to_m = lambda xx, yy, zz=None: (np.asarray(xx) * KX, np.asarray(yy) * KY)
gj = json.loads((RAW / "osm_rivers.geojson").read_text())["features"]
lines_m = transform(to_m, unary_union([shape(f["geometry"]) for f in gj]))
dist = np.array([Point(a * KX, b * KY).distance(lines_m) for a, b in zip(xs, ys)])
print("distance to osm river (m) p25/median/p75/p90:", np.percentile(dist, [25, 50, 75, 90]).round(0))
print("share within 200 m of a river:", round(float((dist < 200).mean()), 3))

rel = dem - ndi.minimum_filter(dem, size=201)
v = rel[rows, cols]
print("height above local min (m) p25/median/p75:", np.percentile(v, [25, 50, 75]).round(0),
      "| share under 50 m:", round(float((v < 50).mean()), 3))