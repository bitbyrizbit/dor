import json
import pathlib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

RAW, OUT = pathlib.Path("data/raw"), pathlib.Path("outputs")
fr = json.loads((RAW / "frozen_rule.json").read_text())
order = (["event"] + ["placebo1", "placebo2", "placebo3"] +
         [t for t in fr if t.startswith("y2")] + (["pos2025"] if "pos2025" in fr else []))
vals = [fr[t]["aligned_per_km2"] for t in order]
cols = ["#c0392b"] + ["#aaaaaa"] * 3 + ["#2c7fb8"] * (len(order) - 4 - ("pos2025" in fr)) + (["#e67e22"] if "pos2025" in fr else [])
fig, ax = plt.subplots(figsize=(9, 4))
ax.bar(range(len(order)), vals, color=cols)
ax.set_xticks(range(len(order)))
ax.set_xticklabels(order, rotation=60, ha="right", fontsize=8)
ax.set_ylabel("river-aligned darkening cells per km2")
ax.set_title("2026 event pair vs non-flood pairs (grey: built sigma, blue: out of sample, orange: 2025 flood)")
fig.savefig(OUT / "fig_placebo.png", dpi=140, bbox_inches="tight")

res = json.loads((RAW / "access_results.json").read_text(encoding="utf-8"))
sw = res["sweep"]
fig, ax = plt.subplots(figsize=(6, 3.5))
ax.plot([f"{s['min_score']}/{s['max_k']}" for s in sw], [s["isolated"] for s in sw], marker="o")
ax.set_xlabel("closure rule (min score / placebos at or above)")
ax.set_ylabel("settlements cut off")
ax.set_title("the answer depends on the rule")
fig.savefig(OUT / "fig_sensitivity.png", dpi=140, bbox_inches="tight")
print("wrote outputs/fig_placebo.png, outputs/fig_sensitivity.png")
