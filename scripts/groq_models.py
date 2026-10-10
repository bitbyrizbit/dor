import os
import requests
from dotenv import load_dotenv

load_dotenv()
r = requests.get("https://api.groq.com/openai/v1/models",
                 headers={"Authorization": "Bearer " + os.environ["GROQ_API_KEY"]}, timeout=30)
print("status:", r.status_code)
if r.status_code == 200:
    for m in sorted(x["id"] for x in r.json().get("data", [])):
        print(m)
else:
    print(r.text[:300])
