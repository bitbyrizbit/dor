import sys
import json
import pathlib
import numpy as np
import rasterio
from rasterio.features import rasterize
from scipy import ndimage as ndi
from shapely.geometry import shape

RAW = pathlib.Path("data/raw")
F = 5          # downsample factor, about 50 m cells
CAP_M = 1500.0
SEARCH = 60    # cells each way, about 3 km

with rasterio.open(RAW / (sys.argv[1] if len(sys.argv) > 1 else "diff_geo.tif")) as src:
    diff = src.read(1)
    tf = src.transform
H, W = diff.shape
H5, W5 = H // F, W // F
dx_m = abs(tf.a) * F * 111320.0 * np.cos(np.radians(28.0))
dy_m = abs(tf.e) * F * 110574.0
print("cell size m (x, y):", round(dx_m, 1), round(dy_m, 1))

# change mask at full res, then block max
smooth = ndi.uniform_filter(np.nan_to_num(diff), size=3)
mask = smooth < -3.0
lab, n = ndi.label(mask)
sizes = ndi.sum(mask, lab, range(1, n + 1))
keep = np.isin(lab, [i + 1 for i, s in enumerate(sizes) if s >= 30])
keep = keep[:H5 * F, :W5 * F].reshape(H5, F, W5, F).max(axis=(1, 3))
rows, cols = np.nonzero(keep)
print("change cells:", len(rows))

# rivers on the coarse grid
feats = json.loads((RAW / "osm_rivers.geojson").read_text())["features"]
coarse_tf = tf * tf.scale(F, F)
river = rasterize([(shape(f["geometry"]), 1) for f in feats], out_shape=(H5, W5),
                  transform=coarse_tf, all_touched=True).astype(bool)
dist = ndi.distance_transform_edt(~river, sampling=(dy_m, dx_m))
dist = np.minimum(dist, CAP_M)

best = (1e9, 0, 0)
cost = np.zeros((2 * SEARCH + 1, 2 * SEARCH + 1))
for i, dr in enumerate(range(-SEARCH, SEARCH + 1)):
    for j, dc in enumerate(range(-SEARCH, SEARCH + 1)):
        rr = np.clip(rows + dr, 0, H5 - 1)
        cc = np.clip(cols + dc, 0, W5 - 1)
        c = dist[rr, cc].mean()
        cost[i, j] = c
        if c < best[0]:
            best = (c, dr, dc)

c0 = dist[rows, cols].mean()
c, dr, dc = best
east, north = dc * dx_m, -dr * dy_m
print("mean capped distance at zero shift (m):", round(float(c0), 0))
print("mean capped distance at best shift (m):", round(float(c), 0))
print("best shift to apply to change map: east", round(east), "m, north", round(north), "m")
rr = np.clip(rows + dr, 0, H5 - 1)
cc = np.clip(cols + dc, 0, W5 - 1)
print("median distance after shift (m):", round(float(np.median(dist[rr, cc])), 0))
print("share of change cells within 200 m of a river after shift:",
      round(float((dist[rr, cc] < 200).mean()), 3))

# sharpness check: is the minimum a clear valley or a flat plain
flat = np.sort(cost.ravel())
print("cost best vs 10th-best vs median (m):",
      round(flat[0], 0), round(flat[10], 0), round(float(np.median(flat)), 0))