import os
from dotenv import load_dotenv


def setup_cdse_s3():
    load_dotenv()
    os.environ["AWS_ACCESS_KEY_ID"] = os.environ["CDSE_S3_KEY"]
    os.environ["AWS_SECRET_ACCESS_KEY"] = os.environ["CDSE_S3_SECRET"]
    os.environ["AWS_S3_ENDPOINT"] = "eodata.dataspace.copernicus.eu"
    os.environ["AWS_VIRTUAL_HOSTING"] = "FALSE"
    os.environ["AWS_HTTPS"] = "YES"