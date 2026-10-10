import csv
import json
import pathlib
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

import numpy as np
import networkx as nx
from scipy.spatial import cKDTree
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection

RAW = pathlib.Path("data/raw")
OUT = pathlib.Path("outputs")
OUT.mkdir(exist_ok=True)
EVENT_DATE, OSM_SNAPSHOT = "2026-08-26", "2026-07-27"
BBOX = [85.10, 27.85, 85.45, 28.25]
KX, KY = 111320.0 * np.cos(np.radians(28.0)), 110574.0
SNAP_PLACE_M, SNAP_HOSP_M, CIRC_MAX = 500.0, 300.0, 3.0
STRICT, LOOSE = (0.05, 0), (0.02, 2)
SWEEP = [(0.02, 2), (0.03, 1), (0.05, 0), (0.10, 0), (0.20, 0)]
SETTLE = ("town", "village", "hamlet")
POST = "\u091a\u094c\u0915\u0940"
STATES = ["ISOLATED_STRICT", "ISOLATED_LOOSE", "UNCERTAIN_UNASSESSED", "REROUTED", "NO_CHANGE",
          "TRACK_ONLY", "DISCONNECTED_BASELINE", "NO_ROAD"]


def git_hash():
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


EV = np.load(RAW / "edge_evidence.npz", allow_pickle=True)
ways = json.loads((RAW / "osm_roads_raw.json").read_text())
pts = json.loads((RAW / "osm_points.json").read_text())

node_xy, edges = {}, []
for w in ways:
    nodes, geom, tags = w.get("nodes", []), w.get("geometry", []), w.get("tags", {})
    if len(nodes) != len(geom) or len(nodes) < 2:
        continue
    br = tags.get("bridge", "no") not in ("no", "")
    for k in range(len(nodes)):
        node_xy[nodes[k]] = (geom[k]["lon"], geom[k]["lat"])
    for k in range(len(nodes) - 1):
        x0, y0, x1, y1 = geom[k]["lon"], geom[k]["lat"], geom[k + 1]["lon"], geom[k + 1]["lat"]
        edges.append((nodes[k], nodes[k + 1], float(np.hypot((x1 - x0) * KX, (y1 - y0) * KY)),
                      tags.get("highway", ""), br, w["id"]))
assert len(edges) == len(EV["wid"]), "edge count differs from edge_evidence.npz, rerun edge_evidence.py"
assert np.array_equal(np.array([e[5] for e in edges]), EV["wid"]), "edge order differs"

LEN = np.array([e[2] for e in edges])
IS_TRACK = np.array([e[3] == "track" for e in edges])
IS_BR = np.array([e[4] for e in edges])
NT = ~IS_TRACK
INSIDE, ASSESS = EV["inside"].astype(bool), EV["assess"].astype(bool)
UNASS = ~ASSESS            # poor geometry inside the footprint AND everything outside it
km = lambda m: round(float(LEN[m].sum()) / 1000, 1)


def flagged(ms, mk):
    return ASSESS & (EV["ev"] >= ms) & (EV["k_ev"] <= mk)


def cluster(idx, r_m):
    idx = np.asarray(idx)
    if len(idx) == 0:
        return []
    p = np.stack([EV["lon"][idx] * KX, EV["lat"][idx] * KY], axis=1)
    pr = cKDTree(p).query_pairs(r_m, output_type="ndarray")
    n = len(idx)
    if len(pr) == 0:
        lab = np.arange(n)
    else:
        g = coo_matrix((np.ones(len(pr)), (pr[:, 0], pr[:, 1])), shape=(n, n))
        lab = connected_components(g, directed=False)[1]
    return [idx[lab == k] for k in range(lab.max() + 1)]


def build(closed, tracks=False):
    G = nx.Graph()
    for i, e in enumerate(edges):
        if closed[i] or (IS_TRACK[i] and not tracks):
            continue
        if not G.has_edge(e[0], e[1]):
            G.add_edge(e[0], e[1], length=e[2])
    return G


def dists(G, sources):
    G.add_node("SUPER")
    for s in sources:
        if s in G:
            G.add_edge("SUPER", s, length=0.0)
    d = nx.single_source_dijkstra_path_length(G, "SUPER", weight="length")
    G.remove_node("SUPER")
    return d


none = np.zeros(len(edges), bool)
c_strict, c_loose = flagged(*STRICT), flagged(*LOOSE)
Gb, Gs, Gl = build(none), build(c_strict), build(c_loose)
Gu, Gt = build(c_loose | UNASS), build(none, tracks=True)
print("graph nodes/edges (no tracks):", Gb.number_of_nodes(), Gb.number_of_edges())


def mk_tree(G):
    nl = list(G.nodes())
    return nl, cKDTree(np.array([[node_xy[n][0] * KX, node_xy[n][1] * KY] for n in nl]))


nodes_b, tree_b = mk_tree(Gb)
nodes_t, tree_t = mk_tree(Gt)


def snap(tree, nl, lon, lat):
    d, j = tree.query([lon * KX, lat * KY])
    return nl[j], float(d)


def distinct(rows):
    out = []
    for r in rows:
        if all(np.hypot((r["lon"] - o["lon"]) * KX, (r["lat"] - o["lat"]) * KY) > 300.0 for o in out):
            out.append(r)
    return out


WL = [s.lower() for s in json.loads(pathlib.Path("configs/tier1_hospitals.json").read_text(encoding="utf-8"))["name_contains"]]

def tier1_ok(p):
    nm = (p.get("name") or "").lower()
    return p["kind"] == "hospital" and any(w in nm for w in WL)


tier1 = distinct([p for p in pts if tier1_ok(p)])
tier2 = [p for p in pts if p["kind"] in ("hospital", "clinic")]


def src_nodes(rows, verbose=False):
    out = []
    for r in rows:
        n, sd = snap(tree_b, nodes_b, r["lon"], r["lat"])
        if sd <= SNAP_HOSP_M:
            out.append((n, r))
        elif verbose:
            print("hospital not on the road graph, dropped:", r.get("name"), round(sd), "m")
    return out


S1, S2 = src_nodes(tier1, True), src_nodes(tier2)
T1, T2 = [n for n, _ in S1], [n for n, _ in S2]
H1 = np.array([[r["lon"] * KX, r["lat"] * KY] for _, r in S1])
print("tier 1 hospitals (incl. buffer):", len(tier1), [r.get("name") for r in tier1])

d0, ds, dl, du = dists(Gb, T1), dists(Gs, T1), dists(Gl, T1), dists(Gu, T1)
dl_any = dists(Gl, T2)
in_aoi = lambda p: BBOX[0] <= p["lon"] <= BBOX[2] and BBOX[1] <= p["lat"] <= BBOX[3]

rows = []
for p in pts:
    if p["kind"] not in SETTLE or not in_aoi(p):
        continue
    n, sd = snap(tree_b, nodes_b, p["lon"], p["lat"])
    r = {"osm_id": p["id"], "name": p.get("name"), "kind": p["kind"], "lat": p["lat"], "lon": p["lon"],
         "snap_m": round(sd), "node": n, "base_km": None, "strict_km": None, "loose_km": None,
         "extra_km_loose": None, "any_health_loose_km": None, "circuity": None}
    if sd > SNAP_PLACE_M:
        _, st = snap(tree_t, nodes_t, p["lon"], p["lat"])
        r["state"] = "TRACK_ONLY" if st <= SNAP_PLACE_M else "NO_ROAD"
    elif n not in d0:
        r["state"] = "DISCONNECTED_BASELINE"
    else:
        r["base_km"] = round(d0[n] / 1000, 1)
        straight = float(np.min(np.hypot(H1[:, 0] - p["lon"] * KX, H1[:, 1] - p["lat"] * KY)))
        r["circuity"] = round(d0[n] / straight, 1) if straight >= 200 else None
        s_, l_, u_, a_ = ds.get(n), dl.get(n), du.get(n), dl_any.get(n)
        r["strict_km"] = None if s_ is None else round(s_ / 1000, 1)
        r["loose_km"] = None if l_ is None else round(l_ / 1000, 1)
        r["any_health_loose_km"] = None if a_ is None else round(a_ / 1000, 1)
        if s_ is None:
            r["state"] = "ISOLATED_STRICT"
        elif l_ is None:
            r["state"] = "ISOLATED_LOOSE"
        elif u_ is None:
            r["state"] = "UNCERTAIN_UNASSESSED"
        elif l_ - d0[n] > 50:
            r["state"] = "REROUTED"
            r["extra_km_loose"] = round((l_ - d0[n]) / 1000, 1)
        else:
            r["state"] = "NO_CHANGE"
    rows.append(r)

counts = {s: sum(1 for r in rows if r["state"] == s) for s in STATES}
rer = [r for r in rows if r["state"] == "REROUTED"]
mean_extra = round(float(np.mean([r["extra_km_loose"] for r in rer])), 1) if rer else 0.0
reach = [r for r in rows if r["base_km"] is not None]
circ = [r["circuity"] for r in reach if r["circuity"]]
suspect = [r for r in reach if r["circuity"] and r["circuity"] > CIRC_MAX]
print("settlements in footprint:", len(rows), "| reachable at baseline:", len(reach))
print("states:", counts, "| mean extra km (rerouted):", mean_extra)
print("circuity (route / straight line) p50/p90/p99:", np.percentile(circ, [50, 90, 99]).round(1),
      "| over", CIRC_MAX, ":", len(suspect), "| of those strict-isolated:",
      sum(1 for r in suspect if r["state"] == "ISOLATED_STRICT"))

# groups: which single flagged place, if restored, reconnects strict-isolated settlements
iso_s = [r for r in rows if r["state"] == "ISOLATED_STRICT"]
gres, covered = [], set()
for members in cluster(np.nonzero(c_strict & NT)[0], 150.0) if iso_s else []:
    added = []
    for i in members:
        a, b, l = edges[i][0], edges[i][1], edges[i][2]
        if not Gs.has_edge(a, b):
            Gs.add_edge(a, b, length=l)
            added.append((a, b))
    dg = dists(Gs, T1)
    for a, b in added:
        Gs.remove_edge(a, b)
    got = [r for r in iso_s if r["node"] in dg]
    if got:
        covered.update(r["osm_id"] for r in got)
        named = [r["name"] for r in got if r.get("name")]
        gres.append({"lat": float(EV["lat"][members].mean()), "lon": float(EV["lon"][members].mean()),
                     "n_edges": int(len(members)), "km": round(float(LEN[members].sum()) / 1000, 2),
                     "bridge": bool(IS_BR[members].any()), "max_score": round(float(EV["ev"][members].max()), 3),
                     "reconnect": len(got), "names": named[:3], "n_unnamed": len(got) - len(named),
                     "members": [r["osm_id"] for r in got]})
gres.sort(key=lambda g: -g["reconnect"])
n_multi = sum(1 for r in iso_s if r["osm_id"] not in covered)
print("strict-isolated:", len(iso_s), "| reconnectable by one flagged place:", len(covered), "| need several:", n_multi)
print("groups (reconnect, bridge, max score, lat, lon, names):")
for g in gres[:12]:
    print("  ", g["reconnect"], g["bridge"], g["max_score"], round(g["lat"], 4), round(g["lon"], 4), g["names"])

# sensitivity
sweep = []
for ms, mk in SWEEP:
    cm = flagged(ms, mk)
    d = dists(build(cm), T1)
    sweep.append({"min_score": ms, "max_k": mk, "km_flagged": km(cm & NT),
                  "isolated": sum(1 for r in reach if r["node"] not in d), "reachable": len(reach)})
print("sensitivity (min score, max placebos, km flagged, isolated of reachable):")
for s in sweep:
    print("  ", s["min_score"], s["max_k"], s["km_flagged"], s["isolated"], "of", s["reachable"])

base_b = IS_BR & ASSESS
totals = {"road_km_inside": km(INSIDE & NT), "km_assessable": km(ASSESS & NT),
          "km_unassessed": km(INSIDE & ~ASSESS & NT), "km_flag_strict": km(c_strict & NT),
          "km_flag_loose": km(c_loose & NT), "reachable_at_baseline": len(reach),
          "bridge_structures_total": len(cluster(np.nonzero(base_b)[0], 150.0)),
          "bridge_structures_strict": len(cluster(np.nonzero(c_strict & IS_BR)[0], 150.0)),
          "bridge_structures_loose": len(cluster(np.nonzero(c_loose & IS_BR)[0], 150.0))}
print("totals (roads only, no tracks):", totals)

results = {"run_id": time.strftime("%Y%m%dT%H%M%S") + "-" + git_hash(), "event_date": EVENT_DATE,
           "osm_snapshot": OSM_SNAPSHOT, "counts": counts, "mean_extra_km": mean_extra, "totals": totals,
           "sweep": sweep, "settlements": rows, "groups": gres[:15], "n_multi": n_multi,
           "circuity": {"n_suspect": len(suspect), "max_ratio": CIRC_MAX,
                        "p50": float(np.percentile(circ, 50)), "p90": float(np.percentile(circ, 90))},
           "params": {"strict": STRICT, "loose": LOOSE, "sweep": SWEEP, "snap_place_m": SNAP_PLACE_M,
                      "snap_hospital_m": SNAP_HOSP_M},
           "tier1": [{"name": r.get("name"), "lat": r["lat"], "lon": r["lon"]} for r in tier1]}
(RAW / "access_results.json").write_text(
    json.dumps(results, default=lambda o: o.item() if hasattr(o, "item") else str(o), indent=1), encoding="utf-8")
with open(OUT / "settlements_access.csv", "w", newline="", encoding="utf-8") as f:
    cols = ["osm_id", "name", "kind", "lat", "lon", "state", "snap_m", "base_km", "circuity", "strict_km",
            "loose_km", "extra_km_loose", "any_health_loose_km"]
    wr = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
    wr.writeheader()
    wr.writerows(rows)

fig, ax = plt.subplots(figsize=(10, 11))
ax.add_collection(LineCollection([[node_xy[e[0]], node_xy[e[1]]] for e in edges if e[3] != "track"],
                                 colors="0.85", linewidths=0.3))
for mask, col, lw in ((c_loose & NT, "orange", 1.2), (c_strict & NT, "red", 1.8)):
    ax.add_collection(LineCollection([[node_xy[edges[i][0]], node_xy[edges[i][1]]]
                                      for i in np.nonzero(mask)[0]], colors=col, linewidths=lw))
cmap = {"ISOLATED_STRICT": "red", "ISOLATED_LOOSE": "orange", "UNCERTAIN_UNASSESSED": "purple",
        "REROUTED": "gold", "NO_CHANGE": "tab:blue", "TRACK_ONLY": "tab:brown",
        "DISCONNECTED_BASELINE": "0.5", "NO_ROAD": "black"}
for st, col in cmap.items():
    sel = [r for r in rows if r["state"] == st]
    ax.scatter([r["lon"] for r in sel], [r["lat"] for r in sel], s=14, c=col, label=f"{st} ({len(sel)})")
ax.scatter([r["lon"] for r in tier1], [r["lat"] for r in tier1], s=120, c="green", marker="P", label="named hospital")
ax.plot([BBOX[0], BBOX[2], BBOX[2], BBOX[0], BBOX[0]], [BBOX[1], BBOX[1], BBOX[3], BBOX[3], BBOX[1]],
        "k--", lw=0.8)
ax.autoscale()
ax.legend(fontsize=7, loc="upper left")
ax.set_title("access under assumed closure of flagged segments | run " + results["run_id"], fontsize=9)
plt.savefig(OUT / "access_map.png", dpi=110, bbox_inches="tight")
print("wrote data/raw/access_results.json, outputs/settlements_access.csv, outputs/access_map.png")
