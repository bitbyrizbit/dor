from pystac_client import Client
from shapely.geometry import box, shape

STAC = "https://stac.dataspace.copernicus.eu/v1"
BBOX = [85.10, 27.85, 85.45, 28.25]
aoi = box(*BBOX)
cat = Client.open(STAC)

GRD_IDS = [
    "S1D_IW_GRDH_1SDV_20260816T122141_20260816T122206_004151_007980_B091_COG",
    "S1D_IW_GRDH_1SDV_20260828T122141_20260828T122206_004326_007FA4_C73B_COG",
]

print("== GRD coverage ==")
for it in cat.search(collections=["sentinel-1-grd"], ids=GRD_IDS).items():
    frac = shape(it.geometry).intersection(aoi).area / aoi.area
    print(it.id, "aoi coverage:", round(frac * 100, 1), "%")
    print("  assets:", list(it.assets.keys()))

print("== SLC availability, same dates ==")
try:
    for day in ["2026-08-16", "2026-08-28"]:
        res = cat.search(
            collections=["sentinel-1-slc"],
            bbox=BBOX,
            datetime=f"{day}T00:00:00Z/{day}T23:59:59Z",
        )
        for it in res.items():
            p = it.properties
            frac = shape(it.geometry).intersection(aoi).area / aoi.area
            print(day, it.id, p.get("sat:relative_orbit"), p.get("sat:orbit_state"),
                  "coverage:", round(frac * 100, 1), "%")
except Exception as e:
    print("SLC search error:", e)
    print("Available collections:", [c.id for c in cat.get_collections()])
