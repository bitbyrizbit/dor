import json
import pathlib
from dor.copilot.report import build
from dor.copilot.guard import check
from dor.manifest import write_manifest

res = json.loads(pathlib.Path("data/raw/access_results.json").read_text(encoding="utf-8"))
bp = pathlib.Path("data/raw/buildings_summary.json")
if bp.exists():
    res["buildings"] = json.loads(bp.read_text(encoding="utf-8"))
out = pathlib.Path("outputs")

out.mkdir(exist_ok=True)
pairs = {}
for lang in ("en", "ne"):
    text, ledger, protected = build(res, lang)
    ok, problems = check(text, ledger, protected)
    print(lang, "guard:", "PASS" if ok else "FAIL", "| ledger entries:", len(ledger.entries))
    for p in problems[:10]:
        print("   ", p)
    (out / f"sitrep_{lang}.md").write_text(text, encoding="utf-8")
    ledger.save(out / f"ledger_{lang}.json")
    pairs[lang] = ledger.pairs()
print("EN and NE ledgers carry identical numbers:", pairs["en"] == pairs["ne"])

cfg = json.loads(pathlib.Path("configs/trishuli_2026.json").read_text())
write_manifest(out / "manifest.json", cfg,
               [out / "sitrep_en.md", out / "sitrep_ne.md", out / "ledger_en.json",
                out / "settlements_access.csv", pathlib.Path("data/raw/access_results.json")],
               {"osm_source": "overpass-api.de with date directive", "run_id": res["run_id"]})
print("wrote outputs/manifest.json")
