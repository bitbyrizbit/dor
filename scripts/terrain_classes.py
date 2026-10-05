import json
import pathlib
import numpy as np
import rasterio
from rasterio.features import rasterize
from scipy import ndimage as ndi
from shapely.geometry import shape
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

RAW = pathlib.Path("data/raw")
m = json.loads((RAW / "geom_model.json").read_text())
kind, x0, y0, z0 = m["kind"], m["x0"], m["y0"], m["z0"]
cc = np.array(m["cc"])
KX, KY = 111320.0 * np.cos(np.radians(28.0)), 110574.0


def design(x, y, z):
    u = (np.asarray(x) - x0) * 10.0
    v = (np.asarray(y) - y0) * 10.0
    t = (np.asarray(z) - z0) / 1000.0
    cols = [np.ones_like(u), u, v]
    if kind in ("xyz", "xyz2"):
        cols.append(t)
    if kind == "xyz2":
        cols += [u * v, u * u, v * v]
    return np.stack(cols, axis=1)


def col_at(x, y, z):
    return (design(np.array([x]), np.array([y]), np.array([z])) @ cc)[0]


with rasterio.open(RAW / "dem_geo.tif") as d:
    dem = d.read(1)
    tf = d.transform
    b = d.bounds
H, W = dem.shape
dem = np.where(np.isfinite(dem), dem, np.nanmedian(dem))

# look direction and incidence angle from the gcp model at the AOI centre
lon_c, lat_c = (b.left + b.right) / 2, (b.bottom + b.top) / 2
z_c = float(np.median(dem))
d = 0.01
g_e = (col_at(lon_c + d, lat_c, z_c) - col_at(lon_c - d, lat_c, z_c)) / (2 * d * KX)
g_n = (col_at(lon_c, lat_c + d, z_c) - col_at(lon_c, lat_c - d, z_c)) / (2 * d * KY)
gmag = float(np.hypot(g_e, g_n))
bearing = float(np.degrees(np.arctan2(g_e, g_n)) % 360)
print("range direction bearing (deg, away from sensor if cols grow with range):", round(bearing, 1))
print("metres per pixel along range (expect about 10):", round(1.0 / gmag, 2))
dcol_dz = abs(col_at(lon_c, lat_c, z_c + 500) - col_at(lon_c, lat_c, z_c - 500))
hor_m = dcol_dz / gmag
theta = float(np.degrees(np.arctan2(1000.0, hor_m)))
print("height 1000 m moves the image by (m):", round(hor_m, 0), "-> incidence angle estimate (deg):", round(theta, 1))

# slope along the range direction
ds = ndi.gaussian_filter(dem, 1.5)
dx = abs(tf.a) * KX
dy = abs(tf.e) * KY
d0, d1 = np.gradient(ds, dy, dx)
dz_dn, dz_de = -d0, d1
er_e, er_n = g_e / gmag, g_n / gmag
alpha = np.degrees(np.arctan(dz_de * er_e + dz_dn * er_n))   # positive = faces the sensor
theta_loc = theta - alpha
cls = np.zeros((H, W), np.uint8)                              # 0 good
cls[(theta_loc < 15) | ((theta_loc > 75) & (theta_loc < 90))] = 1   # poor
cls[theta_loc <= 0] = 2                                       # layover
cls[theta_loc >= 90] = 3                                      # shadow
np.save(RAW / "geom_class.npy", cls)
names = ["good", "poor", "layover", "shadow"]
print("whole AOI shares:", {n: round(float((cls == i).mean()), 3) for i, n in enumerate(names)})

# where do the strong-change cells fall
with rasterio.open(RAW / "diff_terrain.tif") as s:
    diff = s.read(1)
smooth = ndi.uniform_filter(np.nan_to_num(diff), size=3)
mask = smooth < -3.0
lab, k = ndi.label(mask)
sizes = ndi.sum(mask, lab, range(1, k + 1))
keep = np.isin(lab, [i + 1 for i, s_ in enumerate(sizes) if s_ >= 30])
print("strong-change cells:", int(keep.sum()))
print("strong-change shares:", {n: round(float((cls[keep] == i).mean()), 3) for i, n in enumerate(names)})

# river distance by class
feats = json.loads((RAW / "osm_rivers.geojson").read_text())["features"]
river = rasterize([(shape(f["geometry"]), 1) for f in feats], out_shape=(H, W),
                  transform=tf, all_touched=True).astype(bool)
dist = ndi.distance_transform_edt(~river, sampling=(dy, dx))
for label, sel in (("all strong", keep), ("good only", keep & (cls == 0)),
                   ("layover+shadow+poor", keep & (cls > 0))):
    v = dist[sel]
    if len(v):
        print(label, "| n:", len(v), "| median m:", round(float(np.median(v)), 0),
              "| within 200 m:", round(float((v < 200).mean()), 3))

fig, ax = plt.subplots(figsize=(9, 10))
rgb = np.ones((H, W, 3), np.float32) * 0.92
rgb[cls == 1] = (1.0, 0.85, 0.3)
rgb[cls == 2] = (0.9, 0.2, 0.2)
rgb[cls == 3] = (0.2, 0.3, 0.8)
rr, c_ = np.nonzero(keep)
rgb[rr, c_] = (0, 0, 0)
ax.imshow(rgb[::3, ::3], extent=[b.left, b.right, b.bottom, b.top])
ax.set_title("geometry classes: poor yellow, layover red, shadow blue, strong change black")
plt.savefig(RAW / "terrain_classes.png", dpi=110, bbox_inches="tight")