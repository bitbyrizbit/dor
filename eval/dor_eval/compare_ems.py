import json
import pathlib
import re
import sys
import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
import shapely
from shapely.geometry import LineString, Point, box
from scipy.stats import rankdata
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.stdout.reconfigure(encoding="utf-8")
RAW, EMS, OUT = pathlib.Path("data/raw"), pathlib.Path("eval/data/ems"), pathlib.Path("outputs")
M = 32645
BBOX = [85.10, 27.85, 85.45, 28.25]
STRICT, LOOSE = (0.05, 0), (0.02, 2)
PAT = re.compile(r"^EMSR927_AOI(\d\d)_([A-Z]+)_([A-Z0-9]+)_([A-Za-z0-9]+)_v(\d+)\.(json|geojson|shp|gpkg)$")
rng = np.random.default_rng(0)

# 1. choose files
sel, unmatched = {}, []
for p in sorted(EMS.rglob("*")):
    if not p.is_file():
        continue
    m = PAT.match(p.name)
    if not m:
        unmatched.append(p.name)
        continue
    aoi, kind, ptype, layer, ver, ext = m.groups()
    if kind != "GRA":
        continue
    mon = 0 if ptype == "PRODUCT" else 1 + int(re.sub(r"\D", "", ptype) or 99)
    score = (mon, -int(ver), 0 if ext in ("json", "geojson") else 1)
    if (aoi, layer) not in sel or score < sel[(aoi, layer)][0]:
        sel[(aoi, layer)] = (score, p, ptype, int(ver))
if not sel:
    raise SystemExit("no EMS grading files matched the pattern. first unmatched names: " + str(unmatched[:20]))
print("layer names present:", sorted({l for _, l in sel}))
print("selected files (area, layer, product, version):")
for (aoi, layer), (_, p, ptype, ver) in sorted(sel.items()):
    if layer in ("areaOfInterestA", "builtUpP", "transportationL", "transportationP"):
        print("  AOI" + aoi, layer, ptype, "v" + str(ver), p.name)


def load(layer):
    parts = []
    for (aoi, lay), (_, p, ptype, ver) in sorted(sel.items()):
        if lay != layer:
            continue
        g = gpd.read_file(p)
        if len(g) == 0:
            continue
        g = g.set_crs(4326, allow_override=True) if g.crs is None else g.to_crs(4326)
        g["aoi"] = aoi
        parts.append(g)
    return gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), crs=4326) if parts else gpd.GeoDataFrame(geometry=[], crs=4326)


A = load("areaOfInterestA").to_crs(M)
ours = gpd.GeoSeries([box(*BBOX)], crs=4326).to_crs(M).iloc[0]
poly = {r.aoi: r.geometry for r in A.itertuples()}
print("area of interest overlap with our box:")
for a, g in sorted(poly.items()):
    print("  AOI" + a, "share of the area inside our box:", round(g.intersection(ours).area / g.area, 2))

# 2. our edges
EV = np.load(RAW / "edge_evidence.npz", allow_pickle=True)
ways = json.loads((RAW / "osm_roads_raw.json").read_text())
geoms, hw, br, wid = [], [], [], []
for w in ways:
    nodes, geom, tags = w.get("nodes", []), w.get("geometry", []), w.get("tags", {})
    if len(nodes) != len(geom) or len(nodes) < 2:
        continue
    for k in range(len(nodes) - 1):
        geoms.append(LineString([(geom[k]["lon"], geom[k]["lat"]), (geom[k + 1]["lon"], geom[k + 1]["lat"])]))
        hw.append(tags.get("highway", ""))
        br.append(tags.get("bridge", "no") not in ("no", ""))
        wid.append(w["id"])
assert len(geoms) == len(EV["wid"]), "edge count differs from edge_evidence.npz"
E = gpd.GeoDataFrame({"hw": hw, "bridge": br, "wid": wid, "ev": EV["ev"], "k": EV["k_ev"],
                      "assess": EV["assess"].astype(bool), "length": EV["length"]}, geometry=geoms, crs=4326).to_crs(M)
with rasterio.open(RAW / "dem_geo.tif") as d:
    tf, H, W = d.transform, d.height, d.width
hand = np.load(RAW / "hand_500.npy")
r_ = np.floor((EV["lat"] - tf.f) / tf.e).astype(int)
c_ = np.floor((EV["lon"] - tf.c) / tf.a).astype(int)
okp = (r_ >= 0) & (r_ < H) & (c_ >= 0) & (c_ < W)
hv = np.full(len(r_), np.nan)
hv[okp] = hand[r_[okp], c_[okp]]
E["hand"] = hv
E["strict"] = E.assess & (E.ev >= STRICT[0]) & (E.k <= STRICT[1])
E["loose"] = E.assess & (E.ev >= LOOSE[0]) & (E.k <= LOOSE[1])


def auc(score, pos):
    s, y = np.asarray(score, float), np.asarray(pos, bool)
    if y.all() or (~y).all():
        return np.nan
    rk = rankdata(s)
    n1, n0 = y.sum(), (~y).sum()
    return float((rk[y].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def summarize(df):
    L = df["length"].to_numpy() / 1000.0
    y = df["y"].to_numpy()
    pos, neg, poss = y == 1, y == 0, y == 2
    out = {"edges": int(len(df)), "lines": int(df["line_id"].nunique()),
           "km_pos": float(L[pos].sum()), "km_neg": float(L[neg].sum()), "km_poss": float(L[poss].sum())}
    base = out["km_pos"] / max(out["km_pos"] + out["km_neg"], 1e-9)
    out["base_rate"] = base
    hand_order = np.argsort(np.nan_to_num(df["hand"].to_numpy(), nan=1e9))
    for name in ("strict", "loose"):
        f = df[name].to_numpy()
        tp, fp = L[pos & f].sum(), L[neg & f].sum()
        prec = tp / (tp + fp) if tp + fp else np.nan
        h = np.zeros(len(df), bool)
        h[hand_order[np.cumsum(L[hand_order]) <= L[f].sum()]] = True
        tph, fph = L[pos & h].sum(), L[neg & h].sum()
        out[name] = {"flagged_km": float(L[f].sum()),
                     "recall": float(tp / L[pos].sum()) if L[pos].sum() else np.nan,
                     "fpr": float(fp / L[neg].sum()) if L[neg].sum() else np.nan,
                     "precision": float(prec), "lift": float(prec / base) if base and prec == prec else np.nan,
                     "possibly_flagged": float(L[poss & f].sum() / L[poss].sum()) if L[poss].sum() else np.nan,
                     "lowhand_recall": float(tph / L[pos].sum()) if L[pos].sum() else np.nan,
                     "lowhand_precision": float(tph / (tph + fph)) if tph + fph else np.nan,
                     "random_recall": float(L[f].sum() / L.sum())}
    m = pos | neg
    out["auc_score"] = auc(df["ev"].to_numpy()[m], pos[m])
    out["auc_lowhand"] = auc(-np.nan_to_num(df["hand"].to_numpy(), nan=1e9)[m], pos[m])
    return out


def boot(df, n=1000):
    ids = df["line_id"].unique()
    arr = df["line_id"].to_numpy()
    groups = {i: np.nonzero(arr == i)[0] for i in ids}
    acc = {"recall_strict": [], "recall_loose": [], "auc_score": [], "auc_lowhand": []}
    for _ in range(n):
        pick = rng.choice(ids, size=len(ids), replace=True)
        s = summarize(df.iloc[np.concatenate([groups[i] for i in pick])])
        acc["recall_strict"].append(s["strict"]["recall"])
        acc["recall_loose"].append(s["loose"]["recall"])
        acc["auc_score"].append(s["auc_score"])
        acc["auc_lowhand"].append(s["auc_lowhand"])
    return {k: [float(x) for x in np.nanpercentile(v, [2.5, 97.5])] for k, v in acc.items()}


def show(tag, s, ci):
    print(f"--- {tag}: {s['edges']} edges, {s['lines']} EMS lines | km damaged {s['km_pos']:.1f}, undamaged {s['km_neg']:.1f}, possibly {s['km_poss']:.1f} | base rate {s['base_rate']:.2f}")
    for name in ("strict", "loose"):
        x = s[name]
        print(f"   {name}: flagged {x['flagged_km']:.1f} km | recall {x['recall']:.2f} | fpr {x['fpr']:.2f} | precision {x['precision']:.2f} | lift {x['lift']:.2f} | possibly flagged {x['possibly_flagged']:.2f}")
        print(f"      baselines at the same km: lowest HAND recall {x['lowhand_recall']:.2f}, precision {x['lowhand_precision']:.2f} | random recall {x['random_recall']:.2f}")
    print(f"   AUC of DOR score {s['auc_score']:.2f} vs lowest HAND {s['auc_lowhand']:.2f}")
    if ci:
        print("   95% intervals (cluster bootstrap over EMS lines):", {k: [round(v, 2) for v in x] for k, x in ci.items()})


# 3. roads
roads = load("transportationL")
if "simplified" in roads.columns:
    roads = roads[roads["simplified"].astype(str) != "Tracks"]
R = roads.to_crs(M)[["aoi", "damage_gra", "geometry"]].reset_index(drop=True)
R["line_id"] = R.index
cand = E[(E.hw != "track") & E.assess].copy()
cand["eidx"] = cand.index
cand = cand.reset_index(drop=True)
j = gpd.sjoin_nearest(cand, R, how="inner", max_distance=25, distance_col="dist")
j = j.sort_values("dist").drop_duplicates("eidx")
j["y"] = j["damage_gra"].map({"Destroyed": 1, "Damaged": 1, "No visible damage": 0, "Possibly damaged": 2})
j = j[j["y"].notna()].copy()
print("\nroad edges labelled by EMS:", len(j), "| by grade:", dict(j["damage_gra"].value_counts()))
results = {"selected": {f"AOI{a}_{l}": f"{p.name}" for (a, l), (_, p, _, _) in sel.items()}}
if len(j) and j["line_id"].nunique() >= 5:
    for tag, d in [("pooled", j)] + [("AOI" + a, g) for a, g in j.groupby("aoi")]:
        s = summarize(d)
        ci = boot(d) if d["line_id"].nunique() >= 5 else None
        show(tag, s, ci)
        results["roads_" + tag] = {"summary": s, "ci": ci}
else:
    print("too few labelled road edges or EMS lines for a comparison, check the layer names and the 25 m match")

# 4. bridges
P = load("transportationP")
Eb = E[E.bridge].copy()
if len(P):
    P = P[P["damage_gra"].isin(["Destroyed", "Damaged"])].to_crs(M).reset_index(drop=True)
    Pb = P.copy()
    Pb["geometry"] = Pb.buffer(150)
    jj = gpd.sjoin(Eb[["strict", "loose", "assess", "ev", "geometry"]], Pb[["aoi", "geometry"]], predicate="intersects")
    rows = []
    for pid, row in P.iterrows():
        g = jj[jj["index_right"] == pid]
        rows.append({"aoi": row["aoi"], "grade": row["damage_gra"], "bridge_edges": int(len(g)),
                     "assessable": bool(g["assess"].any()) if len(g) else False,
                     "strict": bool(g["strict"].any()) if len(g) else False,
                     "loose": bool(g["loose"].any()) if len(g) else False,
                     "max_score": float(g["ev"].max()) if len(g) else None})
    BR = pd.DataFrame(rows)
    if len(BR):
        print("\nEMS damaged or destroyed bridges:", len(BR), "| with an OSM bridge within 150 m:", int((BR.bridge_edges > 0).sum()),
              "| assessable:", int(BR.assessable.sum()), "| flagged strict:", int(BR.strict.sum()), "| flagged loose:", int(BR.loose.sum()))
        print(BR.groupby("aoi")[["bridge_edges", "assessable", "strict", "loose"]].agg(lambda s: int((s > 0).sum())).to_string())
        inside = gpd.sjoin(Eb[["strict", "loose", "assess", "length", "geometry"]], A[["aoi", "geometry"]], predicate="intersects")
        inside = inside[~inside.index.duplicated()]
        a = inside[inside["assess"]]
        print("all OSM bridge edges inside the usable areas that could be assessed:", len(a),
              "| flagged strict:", round(float(a["strict"].mean()), 2) if len(a) else None,
              "| flagged loose:", round(float(a["loose"].mean()), 2) if len(a) else None)
        BR.to_csv(OUT / "ems_bridges.csv", index=False)
        results["bridges"] = BR.to_dict("records")

# 5. buildings
S = np.load(RAW / "score_maps.npz")
ev_map, k_map, gf = S["ev_map"], S["k_map"], S["good_frac"]


def flags_at(lon, lat):
    r = np.floor((lat - tf.f) / tf.e).astype(int)
    c = np.floor((lon - tf.c) / tf.a).astype(int)
    ok = (r >= 0) & (r < H) & (c >= 0) & (c < W)
    e, k, g = np.zeros(len(lon)), np.full(len(lon), 99), np.zeros(len(lon))
    e[ok], k[ok], g[ok] = ev_map[r[ok], c[ok]], k_map[r[ok], c[ok]], gf[r[ok], c[ok]]
    assess = ok & (g >= 0.5)
    return assess, assess & (e >= STRICT[0]) & (k <= STRICT[1]), assess & (e >= LOOSE[0]) & (k <= LOOSE[1])


B = load("builtUpP")
if len(B):
    B = B[B["damage_gra"].isin(["Destroyed", "Damaged", "Possibly damaged"])]
    pts = B.geometry.representative_point()
    a_, s_, l_ = flags_at(pts.x.to_numpy(), pts.y.to_numpy())
    B = B.assign(assess=a_, strict=s_, loose=l_)
    print("\nEMS buildings by area and grade: assessable / flagged strict / flagged loose (of assessable), and the flagged share of random points in the same area")
    for aoi, g in B.groupby("aoi"):
        pg = gpd.GeoSeries([poly[aoi]], crs=M).to_crs(4326).iloc[0]
        x0, y0, x1, y1 = pg.bounds
        rx, ry = rng.uniform(x0, x1, 40000), rng.uniform(y0, y1, 40000)
        inpoly = shapely.contains_xy(pg, rx, ry)
        ra, rs, rl = flags_at(rx[inpoly], ry[inpoly])
        area = (float(rs[ra].mean()), float(rl[ra].mean())) if ra.any() else (np.nan, np.nan)
        for grade, gg in g.groupby("damage_gra"):
            n_ass = int(gg.assess.sum())
            print(f"   AOI{aoi} {grade}: {len(gg)} buildings, assessable {n_ass}, strict {int(gg.strict.sum())} ({gg.strict.sum() / max(n_ass, 1):.2f}), "
                  f"loose {int(gg.loose.sum())} ({gg.loose.sum() / max(n_ass, 1):.2f}) | area share strict {area[0]:.2f}, loose {area[1]:.2f}")
            results[f"buildings_AOI{aoi}_{grade}"] = {"n": int(len(gg)), "assessable": n_ass, "strict": int(gg.strict.sum()),
                                                      "loose": int(gg.loose.sum()), "area_share_strict": area[0], "area_share_loose": area[1]}

# 6. our verify-first places against EMS
acc = json.loads((RAW / "access_results.json").read_text(encoding="utf-8"))
print("\nverify-first places: area, nearest EMS road grade and distance, nearest EMS damaged bridge distance")
Pall = P if len(P) else None
for i, g in enumerate(acc["groups"][:8]):
    pt = gpd.GeoSeries([Point(g["lon"], g["lat"])], crs=4326).to_crs(M).iloc[0]
    inside = [a for a, pg in poly.items() if pg.contains(pt)]
    dr = R.distance(pt)
    road = (R.loc[dr.idxmin(), "damage_gra"], round(float(dr.min()))) if len(R) else None
    bd = round(float(Pall.distance(pt).min())) if Pall is not None and len(Pall) else None
    print(f"  {i + 1}. {'bridge' if g['bridge'] else 'road'} {g['lat']:.4f},{g['lon']:.4f} | {g['reconnect']} settlements | inside AOI: {inside or 'none'} | nearest EMS road: {road} | nearest EMS damaged bridge m: {bd}")

# 7. figures
colors = {"Destroyed": "red", "Damaged": "orange", "Possibly damaged": "gold", "No visible damage": "limegreen"}
for aoi in sorted(poly):
    if poly[aoi].intersection(ours).area / poly[aoi].area < 0.5:
        continue
    gp = gpd.GeoSeries([poly[aoi]], crs=M).to_crs(4326)
    x0, y0, x1, y1 = gp.total_bounds
    fig, ax = plt.subplots(figsize=(8, 9))
    for gname, col in colors.items():
        sub = roads[(roads["aoi"] == aoi) & (roads["damage_gra"] == gname)]
        if len(sub):
            sub.plot(ax=ax, color=col, linewidth=3 if gname in ("Destroyed", "Damaged") else 1.5, label="EMS " + gname)
    fl = E[E.loose & (E.hw != "track")].to_crs(4326).cx[x0:x1, y0:y1]
    if len(fl[~fl.strict]):
        fl[~fl.strict].plot(ax=ax, color="0.45", linewidth=1, linestyle="--", label="DOR loose only")
    if len(fl[fl.strict]):
        fl[fl.strict].plot(ax=ax, color="black", linewidth=1.3, linestyle="--", label="DOR strict")
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.legend(fontsize=8)
    ax.set_title(f"AOI{aoi}: EMS road grading vs DOR flagged roads (check-only)")
    fig.savefig(OUT / f"ems_compare_aoi{aoi}.png", dpi=120, bbox_inches="tight")
    plt.close(fig)
(OUT / "ems_comparison.json").write_text(json.dumps(results, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)), encoding="utf-8")
print("\nwrote outputs/ems_comparison.json, outputs/ems_bridges.csv and one figure per usable area")
