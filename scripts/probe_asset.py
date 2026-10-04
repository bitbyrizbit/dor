from pystac_client import Client
import rasterio

STAC = "https://stac.dataspace.copernicus.eu/v1"
ID = "S1D_IW_GRDH_1SDV_20260816T122141_20260816T122206_004151_007980_B091_COG"

cat = Client.open(STAC)
it = next(cat.search(collections=["sentinel-1-grd"], ids=[ID]).items())
asset = it.assets["vv"]
print("href:", asset.href)
print("media:", asset.media_type)
print("extra:", asset.extra_fields)

import os
from dotenv import load_dotenv
load_dotenv()

os.environ["AWS_ACCESS_KEY_ID"] = os.getenv("CDSE_S3_KEY", "")
os.environ["AWS_SECRET_ACCESS_KEY"] = os.getenv("CDSE_S3_SECRET", "")
os.environ["AWS_S3_ENDPOINT"] = "eodata.dataspace.copernicus.eu"
os.environ["AWS_VIRTUAL_HOSTING"] = "FALSE"
os.environ["AWS_HTTPS"] = "YES"

try:
    with rasterio.open(asset.href) as src:
        print("crs:", src.crs)
        print("size:", src.width, src.height)
        print("transform:", src.transform)
        print("gcps:", len(src.gcps[0]), "gcp crs:", src.gcps[1])
        print("overviews:", src.overviews(1))
        small = src.read(1, out_shape=(src.height // 64, src.width // 64))
        print("downsampled read ok:", small.shape, small.dtype, int(small.max()))
except Exception as e:
    print("OPEN FAILED:", repr(e))