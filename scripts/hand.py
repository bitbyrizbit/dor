import pathlib
import numpy as np
import rasterio
from rasterio.transform import Affine
from scipy import ndimage as ndi
if not hasattr(np, "in1d"):
    np.in1d = lambda a, b, **kw: np.isin(np.asarray(a).ravel(), b, **kw)
from pysheds.grid import Grid

RAW = pathlib.Path("data/raw")
F = 3

with rasterio.open(RAW / "dem_geo.tif") as s:
    dem = s.read(1)
    tf = s.transform
H, W = dem.shape
dem = np.where(np.isfinite(dem), dem, np.nanmedian(dem)).astype(np.float32)
coarse = dem[::F, ::F]
ctf = tf * Affine.scale(F, F)
with rasterio.open(RAW / "dem_30m.tif", "w", driver="GTiff", height=coarse.shape[0],
                   width=coarse.shape[1], count=1, dtype="float32", crs="EPSG:4326",
                   transform=ctf, nodata=-9999.0) as o:
    o.write(coarse, 1)

grid = Grid.from_raster(str(RAW / "dem_30m.tif"))
d = grid.read_raster(str(RAW / "dem_30m.tif"))
d = grid.fill_pits(d)
d = grid.fill_depressions(d)
d = grid.resolve_flats(d)
fdir = grid.flowdir(d)
acc = grid.accumulation(fdir)
print("flow accumulation max (cells):", int(np.nanmax(np.asarray(acc))))

with rasterio.open(RAW / "diff_terrain.tif") as s:
    diff = s.read(1)
cls = np.load(RAW / "geom_class.npy")
smooth = ndi.uniform_filter(np.nan_to_num(diff), size=3)
mask = np.abs(smooth) > 3.0
lab, k = ndi.label(mask)
sizes = ndi.sum(mask, lab, range(1, k + 1))
keep = np.isin(lab, [i + 1 for i, s_ in enumerate(sizes) if s_ >= 30]) & (cls == 0)
rows, cols = np.nonzero(keep)
print("strong |change| cells in good geometry:", len(rows))
rng = np.random.default_rng(0)
rs, cs = rng.integers(0, H, 20000), rng.integers(0, W, 20000)

for acc_cells in (500, 3000):
    # pass the raster comparison itself, not a numpy array
    hand = grid.compute_hand(fdir, d, acc > acc_cells)
    hand = np.asarray(hand, dtype=np.float32)
    hand[~np.isfinite(hand) | (hand < -1000)] = np.nan
    share = float(np.mean(np.asarray(acc > acc_cells)))
    hf = np.repeat(np.repeat(hand, F, 0), F, 1)
    hfull = np.full((H, W), np.nan, np.float32)
    hh, ww = min(H, hf.shape[0]), min(W, hf.shape[1])
    hfull[:hh, :ww] = hf[:hh, :ww]
    np.save(RAW / f"hand_{acc_cells}.npy", hfull)
    v = hfull[rows, cols]
    r = hfull[rs, cs]
    print("drainage threshold (cells):", acc_cells, "| drainage share of aoi:", round(share, 3))
    print("  change cells HAND m p25/median/p75:", np.nanpercentile(v, [25, 50, 75]).round(0),
          "| under 20 m:", round(float(np.nanmean(v < 20)), 3),
          "| under 50 m:", round(float(np.nanmean(v < 50)), 3))
    print("  random pixels HAND m median:", np.nanpercentile(r, 50).round(0),
          "| under 20 m:", round(float(np.nanmean(r < 20)), 3),
          "| under 50 m:", round(float(np.nanmean(r < 50)), 3))