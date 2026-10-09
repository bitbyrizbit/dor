import csv
import json
import pathlib
import subprocess
import time
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
SNAP_PLACE_M, SNAP_HOSP_M = 500.0, 300.0
STRICT, LOOSE = (0.05, 0), (0.02, 2)
SWEEP = [(0.02, 2), (0.03, 1), (0.05, 0), (0.10, 0), (0.20, 0)]
SETTLE = ("town", "village", "hamlet")
POST = "\u091a\u094c\u0915\u0940"  # health post, in Devanagari
RANK = ["ISOLATED_STRICT", "ISOLATED_LOOSE", "UNCERTAIN_UNASSESSED", "REROUTED",
        "NO_CHANGE", "DISCONNECTED_BASELINE", "NO_ROAD"]


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
INSIDE, ASSESS = EV["inside"].astype(bool), EV["assess"].astype(bool)
UNASS = INSIDE & ~ASSESS
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


def build(closed):
    G = nx.Graph()
    for i, e in enumerate(edges):
        if IS_TRACK[i] or closed[i]:
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
c_unc = c_loose | UNASS
Gb, Gs, Gl, Gu = build(none), build(c_strict), build(c_loose), build(c_unc)
print("graph nodes/edges (no tracks):", Gb.number_of_nodes(), Gb.number_of_edges())

nodes_l = list(Gb.nodes())
tree = cKDTree(np.array([[node_xy[n][0] * KX, node_xy[n][1] * KY] for n in nodes_l]))


def snap(lon, lat):
    d, j = tree.query([lon * KX, lat * KY])
    return nodes_l[j], float(d)


def distinct(rows):
    out = []
    for r in rows:
        if all(np.hypot((r["lon"] - o["lon"]) * KX, (r["lat"] - o["lat"]) * KY) > 300.0 for o in out):
            out.append(r)
    return out


def tier1_ok(p):
    nm = p.get("name") or ""
    return p["kind"] == "hospital" and bool(nm) and POST not in nm and "health post" not in nm.lower()


tier1 = distinct([p for p in pts if tier1_ok(p)])
tier2 = [p for p in pts if p["kind"] in ("hospital", "clinic")]


def src_nodes(rows):
    out = []
    for r in rows:
        n, sd = snap(r["lon"], r["lat"])
        if sd <= SNAP_HOSP_M:
            out.append(n)
    return out


T1, T2 = src_nodes(tier1), src_nodes(tier2)
print("tier 1 hospitals:", len(tier1), [r.get("name") for r in tier1])
print("tier 2 facilities:", len(tier2))

d0, ds, dl, du = dists(Gb, T1), dists(Gs, T1), dists(Gl, T1), dists(Gu, T1)
dl_any = dists(Gl, T2)

rows = []
for p in pts:
    if p["kind"] not in SETTLE:
        continue
    n, sd = snap(p["lon"], p["lat"])
    r = {"osm_id": p["id"], "name": p.get("name"), "kind": p["kind"], "lat": p["lat"], "lon": p["lon"],
         "snap_m": round(sd), "node": n, "base_km": None, "strict_km": None, "loose_km": None,
         "extra_km_loose": None, "any_health_loose_km": None}
    if sd > SNAP_PLACE_M:
        r["state"] = "NO_ROAD"
    elif n not in d0:
        r["state"] = "DISCONNECTED_BASELINE"
    else:
        b = d0[n] / 1000
        r["base_km"] = round(b, 1)
        s_, l_, u_ = ds.get(n), dl.get(n), du.get(n)
        r["strict_km"] = None if s_ is None else round(s_ / 1000, 1)
        r["loose_km"] = None if l_ is None else round(l_ / 1000, 1)
        a_ = dl_any.get(n)
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

counts = {s: sum(1 for r in rows if r["state"] == s) for s in RANK}
rer = [r for r in rows if r["state"] == "REROUTED"]
mean_extra = round(float(np.mean([r["extra_km_loose"] for r in rer])), 1) if rer else 0.0
print("settlements:", len(rows), "| states:", counts, "| mean extra km (rerouted):", mean_extra)
iso = [r for r in rows if r["state"] in ("ISOLATED_STRICT", "ISOLATED_LOOSE")]
for r in sorted(iso, key=lambda r: RANK.index(r["state"])):
    print("  ", r["state"], r["kind"], r["name"], "| base km:", r["base_km"],
          "| any health reachable (km):", r["any_health_loose_km"], "|", round(r["lat"], 4), round(r["lon"], 4))

# verification priority: restore one flagged cluster at a time under the loose scenario
cand = np.nonzero(c_loose & ~IS_TRACK)[0]
groups = cluster(cand, 150.0)
print("loose flagged clusters:", len(groups))
gres = []
if iso or rer:
    for gi, members in enumerate(groups):
        added = []
        for i in members:
            a, b, l = edges[i][0], edges[i][1], edges[i][2]
            if not Gl.has_edge(a, b):
                Gl.add_edge(a, b, length=l)
                added.append((a, b))
        dg = dists(Gl, T1)
        for a, b in added:
            Gl.remove_edge(a, b)
        reconnect = sum(1 for r in iso if r["node"] in dg)
        saved = sum(dl[r["node"]] - dg[r["node"]] for r in rer if r["node"] in dg and r["node"] in dl) / 1000
        if reconnect or saved > 0.05:
            gres.append({"lat": float(EV["lat"][members].mean()), "lon": float(EV["lon"][members].mean()),
                         "km": round(float(LEN[members].sum()) / 1000, 2), "edges": int(len(members)),
                         "bridge": bool(IS_BR[members].any()), "reconnect": int(reconnect),
                         "saved_km": round(float(saved), 1)})
        if (gi + 1) % 50 == 0:
            print("  clusters done:", gi + 1)
    gres.sort(key=lambda g: (-g["reconnect"], -g["saved_km"]))
    print("top places to verify (reconnect count, saved km, bridge, lat, lon):")
    for g in gres[:10]:
        print("  ", g["reconnect"], g["saved_km"], g["bridge"], round(g["lat"], 4), round(g["lon"], 4))

# sensitivity of the answer to the closure rule
reach = [r["node"] for r in rows if r["base_km"] is not None]
sweep = []
for ms, mk in SWEEP:
    cm = flagged(ms, mk)
    d = dists(build(cm), T1)
    sweep.append({"min_score": ms, "max_k": mk, "km_flagged": km(cm & ~IS_TRACK),
                  "isolated": sum(1 for n in reach if n not in d), "reachable_at_baseline": len(reach)})
print("sensitivity (min score, max placebos at or above, km flagged, isolated of reachable):")
for s in sweep:
    print("  ", s["min_score"], s["max_k"], s["km_flagged"], s["isolated"], "of", s["reachable_at_baseline"])

base_b = IS_BR & ASSESS
totals = {"road_km_inside": km(INSIDE), "km_assessable": km(ASSESS), "km_unassessed": km(UNASS),
          "km_flag_strict": km(c_strict), "km_flag_loose": km(c_loose),
          "bridge_structures_total": len(cluster(np.nonzero(base_b)[0], 150.0)),
          "bridge_structures_strict": len(cluster(np.nonzero(c_strict & IS_BR)[0], 150.0)),
          "bridge_structures_loose": len(cluster(np.nonzero(c_loose & IS_BR)[0], 150.0))}
print("totals:", totals)

results = {"run_id": time.strftime("%Y%m%dT%H%M%S") + "-" + git_hash(), "event_date": EVENT_DATE,
           "osm_snapshot": OSM_SNAPSHOT, "params": {"strict": STRICT, "loose": LOOSE, "sweep": SWEEP,
           "snap_place_m": SNAP_PLACE_M, "snap_hospital_m": SNAP_HOSP_M},
           "counts": counts, "mean_extra_km": mean_extra, "totals": totals, "sweep": sweep,
           "settlements": rows, "groups": gres[:15],
           "tier1": [{"name": r.get("name"), "lat": r["lat"], "lon": r["lon"]} for r in tier1],
           "n_tier1": len(tier1), "n_tier2": len(tier2)}
(RAW / "access_results.json").write_text(
    json.dumps(results, default=lambda o: o.item() if hasattr(o, "item") else str(o), indent=1),
    encoding="utf-8")
with open(OUT / "settlements_access.csv", "w", newline="", encoding="utf-8") as f:
    cols = ["osm_id", "name", "kind", "lat", "lon", "state", "snap_m", "base_km", "strict_km",
            "loose_km", "extra_km_loose", "any_health_loose_km"]
    wr = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
    wr.writeheader()
    wr.writerows(rows)

fig, ax = plt.subplots(figsize=(10, 11))
ax.add_collection(LineCollection([[node_xy[e[0]], node_xy[e[1]]] for e in edges if e[3] != "track"],
                                 colors="0.8", linewidths=0.3))
for mask, col, lw in ((c_loose & ~IS_TRACK, "orange", 1.2), (c_strict & ~IS_TRACK, "red", 1.8)):
    ax.add_collection(LineCollection([[node_xy[edges[i][0]], node_xy[edges[i][1]]]
                                      for i in np.nonzero(mask)[0]], colors=col, linewidths=lw))
cmap = {"ISOLATED_STRICT": "red", "ISOLATED_LOOSE": "orange", "UNCERTAIN_UNASSESSED": "purple",
        "REROUTED": "gold", "NO_CHANGE": "tab:blue", "DISCONNECTED_BASELINE": "0.5", "NO_ROAD": "black"}
for st, col in cmap.items():
    sel = [r for r in rows if r["state"] == st]
    ax.scatter([r["lon"] for r in sel], [r["lat"] for r in sel], s=14, c=col, label=f"{st} ({len(sel)})")
ax.scatter([r["lon"] for r in tier1], [r["lat"] for r in tier1], s=120, c="green", marker="P", label="named hospital")
ax.set_xlim(BBOX[0], BBOX[2])
ax.set_ylim(BBOX[1], BBOX[3])
ax.legend(fontsize=7, loc="upper left")
ax.set_title("access under assumed closure of flagged segments (red strict, orange loose)")
plt.savefig(OUT / "access_map.png", dpi=110, bbox_inches="tight")
print("wrote data/raw/access_results.json, outputs/settlements_access.csv, outputs/access_map.png")
