import subprocess
import sys
import time

PY = sys.executable
STEPS = [
    ["scripts/window_aoi.py"], ["scripts/first_change.py"], ["scripts/geocode_diff.py"],
    ["scripts/check_vs_osm.py"], ["scripts/fetch_dem.py"], ["scripts/terrain_geocode.py"],
    ["scripts/terrain_classes.py"], ["scripts/hand.py"],
    ["scripts/run_pair.py", "2026-08-16", "2026-08-28", "event"],
    ["scripts/run_pair.py", "2026-07-23", "2026-08-04", "placebo1"],
    ["scripts/run_pair.py", "2026-08-04", "2026-08-16", "placebo2"],
    ["scripts/run_pair.py", "2026-07-11", "2026-07-23", "placebo3"],
    ["scripts/batch_pairs.py"], ["scripts/frozen_rule.py"],
    ["scripts/fetch_roads.py"], ["scripts/edge_evidence.py"], ["scripts/score_maps.py"],
    ["scripts/access_analysis.py"], ["scripts/make_report.py"], ["scripts/build_dashboard.py"],
]
start = int(sys.argv[1]) if len(sys.argv) > 1 else 0
for n, step in enumerate(STEPS):
    if n < start:
        continue
    t0 = time.time()
    print(f"\n>> step {n}: {' '.join(step)}", flush=True)
    if subprocess.run([PY] + step).returncode != 0:
        sys.exit(f"step {n} failed, fix it and resume with: python scripts/run_all.py {n}")
    print(f"   done in {time.time() - t0:.0f} s")
