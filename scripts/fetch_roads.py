import json
import pathlib
import time
import numpy as np
import requests
import networkx as nx
from scipy.spatial import cKDTree
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BBOX = [85.10, 27.85, 85.45, 28.25]
SNAP = "2026-07-27T00:00:00Z"
RAW = pathlib.Path("data/raw")
HEADERS = {"User-Agent": "dor-hackathon-prototype (student project, github.com/bitbyrizbit)"}
URLS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter"]
S, W, N, E = BBOX[1], BBOX[0], BBOX[3], BBOX[2]
KX, KY = 111320.0 * np.cos(np.radians(28.0)), 110574.0
HW = "motorway|trunk|primary|secondary|tertiary|unclassified|residential|track|service|motorway_link|trunk_link|primary_link|secondary_link|tertiary_link"


def run(q):
    for url in URLS:
        for attempt in (1, 2):
            try:
                r = requests.post(url, data={"data": q}, headers=HEADERS, timeout=240)
                print(url, r.status_code)
                if r.status_code == 200:
                    return url, r.json().get("elements", [])
            except requests.RequestException as e:
                print(url, "error", repr(e))
            time.sleep(15)
    raise SystemExit("all overpass attempts failed")


q_roads = f'[out:json][timeout:200][date:"{SNAP}"];way["highway"~"^({HW})$"]({S},{W},{N},{E});out meta geom qt;'
q_pts = (f'[out:json][timeout:200][date:"{SNAP}"];('
         f'node["place"~"^(city|town|village|hamlet|suburb|isolated_dwelling)$"]({S},{W},{N},{E});'
         f'nwr["amenity"~"^(hospital|clinic)$"]({S},{W},{N},{E}););out meta center qt;')

src1, ways = run(q_roads)
src2, pts = run(q_pts)
print("sources:", src1, src2)
ts = max(e.get("timestamp", "") for e in ways + pts)
print("elements: ways", len(ways), "points", len(pts), "| newest edit timestamp:", ts)
if ts > SNAP:
    raise SystemExit("DATA RULE: element newer than the snapshot, discarding. Do not use.")
(RAW / "osm_roads_raw.json").write_text(json.dumps(ways))
(RAW / "osm_points_raw.json").write_text(json.dumps(pts))

G = nx.Graph()
xy = {}
by_class, bridges = {}, []
total_m = 0.0
for w in ways:
    nodes, geom, tags = w.get("nodes", []), w.get("geometry", []), w.get("tags", {})
    if len(nodes) != len(geom) or len(nodes) < 2:
        continue
    isb = tags.get("bridge", "no") not in ("no", "")
    for n_, g in zip(nodes, geom):
        xy[n_] = (g["lon"] * KX, g["lat"] * KY)
    for a, b in zip(nodes[:-1], nodes[1:]):
        d = float(np.hypot(xy[a][0] - xy[b][0], xy[a][1] - xy[b][1]))
        G.add_edge(a, b, length=d, way=w["id"], bridge=isb, hw=tags.get("highway"))
        total_m += d
        by_class[tags.get("highway")] = by_class.get(tags.get("highway"), 0.0) + d
    if isb:
        bridges.append(w["id"])
print("road length km:", round(total_m / 1000, 1))
print("km by class:", {k: round(v / 1000, 1) for k, v in sorted(by_class.items(), key=lambda kv: -kv[1])})
print("bridge ways:", len(set(bridges)))

comps = sorted(nx.connected_components(G), key=len, reverse=True)
comp_of = {n_: i for i, c in enumerate(comps) for n_ in c}
clen = {}
for a, b, d in G.edges(data=True):
    clen[comp_of[a]] = clen.get(comp_of[a], 0.0) + d["length"]
print("components:", len(comps), "| top 5 km:", [round(clen[i] / 1000, 1) for i in range(min(5, len(comps)))],
      "| largest share of length:", round(clen[0] / total_m, 3))

ids = list(xy.keys())
tree = cKDTree(np.array([xy[i] for i in ids]))
rows = []
for e in pts:
    lat = e.get("lat", e.get("center", {}).get("lat"))
    lon = e.get("lon", e.get("center", {}).get("lon"))
    if lat is None:
        continue
    d, j = tree.query([lon * KX, lat * KY])
    t = e.get("tags", {})
    kind = t.get("place") or t.get("amenity")
    rows.append({"id": e["id"], "type": e["type"], "kind": kind, "name": t.get("name"),
                 "lat": lat, "lon": lon, "snap_m": float(d), "comp": comp_of[ids[j]]})
(RAW / "osm_points.json").write_text(json.dumps(rows, indent=1))

pl = [r for r in rows if r["kind"] in ("city", "town", "village", "hamlet", "suburb", "isolated_dwelling")]
hosp = [r for r in rows if r["kind"] in ("hospital", "clinic")]
print("places:", len(pl), "| by kind:", {k: sum(1 for r in pl if r["kind"] == k) for k in set(r["kind"] for r in pl)})
if pl:
    sn = np.array([r["snap_m"] for r in pl])
    print("places within 500 m / 2 km of a mapped road node:", round(float((sn < 500).mean()), 3), round(float((sn < 2000).mean()), 3))
    print("places snapped to the largest road component:", round(float(np.mean([r["comp"] == 0 for r in pl])), 3))
print("hospitals and clinics:", len(hosp))
for r in hosp:
    print("  ", r["kind"], r["name"], "| snap m:", round(r["snap_m"]), "| largest component:", r["comp"] == 0)

fig, ax = plt.subplots(figsize=(9, 10))
for a, b, d in G.edges(data=True):
    ax.plot([xy[a][0] / KX, xy[b][0] / KX], [xy[a][1] / KY, xy[b][1] / KY],
            color="red" if d["bridge"] else "0.5", lw=1.4 if d["bridge"] else 0.5)
ax.scatter([r["lon"] for r in pl], [r["lat"] for r in pl], s=6, c="tab:blue", label="places")
ax.scatter([r["lon"] for r in hosp], [r["lat"] for r in hosp], s=60, c="tab:green", marker="+", label="hospital or clinic")
ax.set_xlim(BBOX[0], BBOX[2])
ax.set_ylim(BBOX[1], BBOX[3])
ax.legend()
ax.set_title("pre-event OSM roads (grey), bridges (red), places, health")
plt.savefig(RAW / "osm_roads.png", dpi=110, bbox_inches="tight")