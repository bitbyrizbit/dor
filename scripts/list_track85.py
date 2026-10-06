from pystac_client import Client
from shapely.geometry import box, shape

STAC = "https://stac.dataspace.copernicus.eu/v1"
BBOX = [85.10, 27.85, 85.45, 28.25]
aoi = box(*BBOX)
res = Client.open(STAC).search(collections=["sentinel-1-grd"], bbox=BBOX,
                               datetime="2026-07-01/2026-09-30", max_items=500)
rows = []
for it in res.items():
    p = it.properties
    if p.get("sat:relative_orbit") == 85 and p.get("sat:orbit_state") == "ascending":
        cov = shape(it.geometry).intersection(aoi).area / aoi.area
        rows.append((it.datetime, it.id, cov))
for dt, i, cov in sorted(rows):
    print(dt.date(), round(cov * 100, 1), "%", i)