import os
from dotenv import load_dotenv

load_dotenv()

CDSE_USER = os.getenv("CDSE_USER")
CDSE_PASS = os.getenv("CDSE_PASS")
SH_CLIENT_ID = os.getenv("SH_CLIENT_ID")
SH_CLIENT_SECRET = os.getenv("SH_CLIENT_SECRET")