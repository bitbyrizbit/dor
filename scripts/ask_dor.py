import json
import pathlib
import sys
from dotenv import load_dotenv
from dor.copilot.ask import ask

load_dotenv()
sys.stdout.reconfigure(encoding="utf-8")
res = json.loads(pathlib.Path("data/raw/access_results.json").read_text(encoding="utf-8"))
q = " ".join(a for a in sys.argv[1:] if not a.startswith("--"))
out = ask(res, q, "ne" if "--ne" in sys.argv else "en")
print("mode:", out["mode"], "| model:", out["model"], "| attempts:", len(out["attempts"]))
print(out["answer"])
for a in out["attempts"]:
    print("  attempt:", a)
