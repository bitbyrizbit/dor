import json
import pathlib
import numpy as np
import rasterio
from rasterio.windows import Window
from pystac_client import Client
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from dor.acquire.s3_env import setup_cdse_s3

STAC = "https://stac.dataspace.copernicus.eu/v1"
BBOX = [85.10, 27.85, 85.45, 28.25]  # lon_min, lat_min, lon_max, lat_max
SCENES = {
    "pre": "S1D_IW_GRDH_1SDV_20260816T122141_20260816T122206_004151_007980_B091_COG",
    "post": "S1D_IW_GRDH_1SDV_20260828T122141_20260828T122206_004326_007FA4_C73B_COG",
}
PAD_DEG = 0.25
PAD_PX = 300
OUT = pathlib.Path("data/raw")
OUT.mkdir(parents=True, exist_ok=True)


def fit_affine(gcps):
    A = np.array([[g.x, g.y, 1.0] for g in gcps])
    cols = np.array([g.col for g in gcps])
    rows = np.array([g.row for g in gcps])
    cx = np.linalg.lstsq(A, cols, rcond=None)[0]
    ry = np.linalg.lstsq(A, rows, rcond=None)[0]
    res = np.hypot(A @ cx - cols, A @ ry - rows)
    return cx, ry, res


setup_cdse_s3()
cat = Client.open(STAC)

for tag, sid in SCENES.items():
    it = next(cat.search(collections=["sentinel-1-grd"], ids=[sid]).items())
    href = it.assets["vv"].href
    with rasterio.open(href) as src:
        pts, _ = src.gcps
        local = [
            g for g in pts
            if BBOX[0] - PAD_DEG <= g.x <= BBOX[2] + PAD_DEG
            and BBOX[1] - PAD_DEG <= g.y <= BBOX[3] + PAD_DEG
        ]
        print(tag, "local gcps:", len(local))
        if len(local) < 6:
            raise SystemExit(f"{tag}: too few gcps near aoi, check bbox vs scene")
        cx, ry, res = fit_affine(local)
        print(tag, "affine fit residual px: mean", round(res.mean(), 1), "max", round(res.max(), 1))

        corners = [(BBOX[0], BBOX[1]), (BBOX[0], BBOX[3]), (BBOX[2], BBOX[1]), (BBOX[2], BBOX[3])]
        cc = [cx @ [x, y, 1.0] for x, y in corners]
        rr = [ry @ [x, y, 1.0] for x, y in corners]
        c0 = max(int(min(cc)) - PAD_PX, 0)
        c1 = min(int(max(cc)) + PAD_PX, src.width)
        r0 = max(int(min(rr)) - PAD_PX, 0)
        r1 = min(int(max(rr)) + PAD_PX, src.height)
        print(tag, "window cols", c0, c1, "rows", r0, r1)
        if c1 <= c0 or r1 <= r0:
            raise SystemExit(f"{tag}: aoi falls outside the scene")

        arr = src.read(1, window=Window(c0, r0, c1 - c0, r1 - r0))

    valid = float((arr > 0).mean())
    print(tag, "window shape", arr.shape, "valid fraction", round(valid, 3))
    np.save(OUT / f"{tag}_vv_window.npy", arr)
    (OUT / f"{tag}_meta.json").write_text(json.dumps({
        "scene": sid, "col_off": c0, "row_off": r0,
        "affine_col": cx.tolist(), "affine_row": ry.tolist(),
    }, indent=2))

    step = max(arr.shape[0] // 1000, 1)
    ql = np.log10(np.clip(arr[::step, ::step].astype(float), 1, None))
    plt.figure(figsize=(8, 8))
    plt.imshow(ql, cmap="gray")
    plt.title(f"{tag} VV (raw pixel grid, not map-oriented)")
    plt.axis("off")
    plt.savefig(OUT / f"quicklook_{tag}.png", dpi=110, bbox_inches="tight")
    plt.close()