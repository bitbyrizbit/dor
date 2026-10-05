import numpy as np
import rasterio
from pystac_client import Client
from dor.acquire.s3_env import setup_cdse_s3

STAC = "https://stac.dataspace.copernicus.eu/v1"
PRE = "S1D_IW_GRDH_1SDV_20260816T122141_20260816T122206_004151_007980_B091_COG"

setup_cdse_s3()
it = next(Client.open(STAC).search(collections=["sentinel-1-grd"], ids=[PRE]).items())
with rasterio.open(it.assets["vv"].href) as src:
    pts, crs = src.gcps

z = np.array([g.z for g in pts])
x = np.array([g.x for g in pts])
y = np.array([g.y for g in pts])
col = np.array([g.col for g in pts])
print("gcps:", len(pts), "crs:", crs)
print("z min/p25/median/p75/max:", np.percentile(z, [0, 25, 50, 75, 100]).round(1))
print("z unique count:", len(np.unique(z.round(1))))
loc = (x > 85.0) & (x < 85.55) & (y > 27.75) & (y < 28.35)
print("local gcps:", int(loc.sum()), "| local z:", np.round(z[loc], 1)[:12])
print("corr of z with col (range position):", round(float(np.corrcoef(z, col)[0, 1]), 3))