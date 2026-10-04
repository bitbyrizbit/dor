import json
import pathlib
import numpy as np
import rasterio
from rasterio.control import GroundControlPoint
from rasterio.transform import from_origin
from rasterio.warp import reproject, Resampling
from pystac_client import Client
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from dor.acquire.s3_env import setup_cdse_s3

STAC = "https://stac.dataspace.copernicus.eu/v1"
PRE = "S1D_IW_GRDH_1SDV_20260816T122141_20260816T122206_004151_007980_B091_COG"
BBOX = [85.10, 27.85, 85.45, 28.25]
RES = 0.0001
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
print("gcps used:", len(sel))
gcps = [GroundControlPoint(row=g.row - r0, col=g.col - c0, x=g.x, y=g.y, z=0.0) for g in sel]

W = int(round((BBOX[2] - BBOX[0]) / RES))
H = int(round((BBOX[3] - BBOX[1]) / RES))
dst_tf = from_origin(BBOX[0], BBOX[3], RES, RES)
dst = np.full((H, W), np.nan, dtype=np.float32)

reproject(
    source=diff.astype(np.float32),
    destination=dst,
    gcps=gcps,
    src_crs="EPSG:4326",
    dst_transform=dst_tf,
    dst_crs="EPSG:4326",
    resampling=Resampling.bilinear,
    dst_nodata=np.nan,
    SRC_METHOD="GCP_TPS",
)
print("geocoded valid fraction:", round(float(np.isfinite(dst).mean()), 3))

with rasterio.open(RAW / "diff_geo.tif", "w", driver="GTiff", height=H, width=W, count=1,
                   dtype="float32", crs="EPSG:4326", transform=dst_tf, nodata=np.nan) as o:
    o.write(dst, 1)

fig, ax = plt.subplots(figsize=(9, 10))
ax.imshow(dst, cmap="RdBu", vmin=-4, vmax=4,
          extent=[BBOX[0], BBOX[2], BBOX[1], BBOX[3]])
ax.set_xlabel("lon")
ax.set_ylabel("lat")
ax.grid(True, alpha=0.3)
ax.set_title("post minus pre (dB), geocoded via GCP TPS")
plt.savefig(RAW / "diff_geo.png", dpi=110, bbox_inches="tight")