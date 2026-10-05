import pathlib
import numpy as np
import rasterio
from rasterio.merge import merge
from rasterio.warp import reproject, Resampling
from scipy import ndimage as ndi
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

RAW = pathlib.Path("data/raw")
BASE = "https://copernicus-dem-30m.s3.amazonaws.com"
TILES = ["N27_00_E085_00", "N28_00_E085_00"]
SHIFT_E, SHIFT_N = -2162.0, -442.0   # metres, from estimate_shift.py


def url(t):
    name = f"Copernicus_DSM_COG_10_{t}_DEM"
    return f"{BASE}/{name}/{name}.tif"


srcs = []
for t in TILES:
    print("opening", url(t))
    srcs.append(rasterio.open(url(t)))

with rasterio.open(RAW / "diff_geo.tif") as g:
    diff = g.read(1)
    dst_tf = g.transform
    H, W = g.height, g.width
    bounds = g.bounds

mosaic, mtf = merge(srcs, bounds=(bounds.left - 0.01, bounds.bottom - 0.01,
                                  bounds.right + 0.01, bounds.top + 0.01))
nodata = srcs[0].nodata
print("dem mosaic shape:", mosaic.shape, "nodata:", nodata)

dem = np.full((H, W), np.nan, dtype=np.float32)
reproject(mosaic[0].astype(np.float32), dem, src_transform=mtf, src_crs="EPSG:4326",
          dst_transform=dst_tf, dst_crs="EPSG:4326", resampling=Resampling.bilinear,
          src_nodata=nodata, dst_nodata=np.nan)
print("dem valid fraction:", round(float(np.isfinite(dem).mean()), 3))
print("elevation m min/p5/median/p95/max:",
      np.nanpercentile(dem, [0, 5, 50, 95, 100]).round(0))

with rasterio.open(RAW / "dem_geo.tif", "w", driver="GTiff", height=H, width=W, count=1,
                   dtype="float32", crs="EPSG:4326", transform=dst_tf, nodata=np.nan) as o:
    o.write(dem, 1)

# valley-floor test: height above local minimum within about 2 km
filled = np.where(np.isfinite(dem), dem, np.nanmedian(dem))
win = 201
rel = filled - ndi.minimum_filter(filled, size=win)

smooth = ndi.uniform_filter(np.nan_to_num(diff), size=3)
mask = smooth < -3.0
lab, n = ndi.label(mask)
sizes = ndi.sum(mask, lab, range(1, n + 1))
keep = np.isin(lab, [i + 1 for i, s in enumerate(sizes) if s >= 30])
rows, cols = np.nonzero(keep)
print("strong-change pixels:", len(rows))

px_x = abs(dst_tf.a) * 111320.0 * np.cos(np.radians(28.0))
px_y = abs(dst_tf.e) * 110574.0
dc = int(round(SHIFT_E / px_x))
dr = int(round(-SHIFT_N / px_y))
print("shift in pixels (rows, cols):", dr, dc)


def sample(r, c):
    r = np.clip(r, 0, H - 1)
    c = np.clip(c, 0, W - 1)
    return rel[r, c]


for label, rr, cc in (("zero shift", rows, cols), ("best shift", rows + dr, cols + dc)):
    v = sample(rr, cc)
    print(label, "| height above local min (m) p25/median/p75:",
          np.percentile(v, [25, 50, 75]).round(0),
          "| share under 50 m:", round(float((v < 50).mean()), 3))

rng = np.random.default_rng(0)
rs = rng.integers(0, H, 20000)
cs = rng.integers(0, W, 20000)
vr = sample(rs, cs)
print("random pixels | median:", np.percentile(vr, 50).round(0),
      "| share under 50 m:", round(float((vr < 50).mean()), 3))

fig, ax = plt.subplots(figsize=(9, 10))
step = 4
ls = ndi.gaussian_filter(filled, 2)
gy, gx = np.gradient(ls, 30.0)
hs = np.clip(0.5 + 0.5 * (gx - gy) / (np.abs(gx - gy).max() + 1e-6) * 4, 0, 1)
ax.imshow(hs[::step, ::step], cmap="gray",
          extent=[bounds.left, bounds.right, bounds.bottom, bounds.top])
ax.set_title("hillshade from copernicus dem glo-30")
plt.savefig(RAW / "dem_hillshade.png", dpi=110, bbox_inches="tight")