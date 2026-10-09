import sys

from urllib3.util.retry import Retry

from pystac_client import Client
from pystac_client.stac_api_io import StacApiIO
from shapely.geometry import box, shape

STAC = "https://stac.dataspace.copernicus.eu/v1"
BBOX = [85.10, 27.85, 85.45, 28.25]

# ---------- retry-aware STAC IO ----------
retries = Retry(
    total=5,
    backoff_factor=2,                          # waits 2, 4, 8, 16, 32 s
    status_forcelist=[429, 502, 503, 504],
    allowed_methods=["GET", "POST", "HEAD"],   # STAC search uses POST
    respect_retry_after_header=True,
)
stac_io = StacApiIO(max_retries=retries)
# ------------------------------------------

aoi = box(*BBOX)
start, end = sys.argv[1], sys.argv[2]
cat = Client.from_file(STAC, stac_io=stac_io)

res = cat.search(collections=["sentinel-1-grd"], bbox=BBOX,
                 datetime=f"{start}/{end}", max_items=500)
rows = []
for it in res.items():
    p = it.properties
    if p.get("sat:relative_orbit") == 85 and p.get("sat:orbit_state") == "ascending":
        cov = shape(it.geometry).intersection(aoi).area / aoi.area
        rows.append((it.datetime, p.get("platform"), round(cov * 100, 1), it.id))
for r in sorted(rows):
    print(r[0].date(), r[1], r[2], "%", r[3])