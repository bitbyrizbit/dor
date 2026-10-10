import html
import json
import pathlib
import re
import numpy as np
from dor.copilot.ledger import Ledger
from dor.copilot.guard import check

RAW, OUT = pathlib.Path("data/raw"), pathlib.Path("outputs")
BBOX = [85.10, 27.85, 85.45, 28.25]
ATTR = ["Contains modified Copernicus Sentinel data 2026.",
        "Produced using Copernicus WorldDEM-30 \u00a9 DLR e.V. 2010-2014 and \u00a9 Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved.",
        "\u00a9 OpenStreetMap contributors (pre-event snapshot, ODbL)."]

res = json.loads((RAW / "access_results.json").read_text(encoding="utf-8"))
EV = np.load(RAW / "edge_evidence.npz", allow_pickle=True)
ways = json.loads((RAW / "osm_roads_raw.json").read_text())

seg, hw_edge, ctx = [], [], []
for w in ways:
    nodes, geom, tags = w.get("nodes", []), w.get("geometry", []), w.get("tags", {})
    if len(nodes) != len(geom) or len(nodes) < 2:
        continue
    hw = tags.get("highway", "")
    if hw in ("trunk", "primary", "secondary", "tertiary") and any(
            BBOX[0] <= g["lon"] <= BBOX[2] and BBOX[1] <= g["lat"] <= BBOX[3] for g in geom):
        ctx.append([[round(g["lon"], 4), round(g["lat"], 4)] for g in geom])
    for k in range(len(nodes) - 1):
        seg.append((geom[k]["lon"], geom[k]["lat"], geom[k + 1]["lon"], geom[k + 1]["lat"]))
        hw_edge.append(hw)
assert len(seg) == len(EV["wid"]), "edge count differs from edge_evidence.npz, rerun edge_evidence.py"

ASSESS = EV["assess"].astype(bool)
ev, kk = EV["ev"], EV["k_ev"]
nt = np.array([h != "track" for h in hw_edge])
m_strict = ASSESS & (ev >= 0.05) & (kk <= 0) & nt
m_loose = ASSESS & (ev >= 0.02) & (kk <= 2) & nt & ~m_strict


def lines(mask):
    return [[[round(s[0], 5), round(s[1], 5)], [round(s[2], 5), round(s[3], 5)]]
            for s, m in zip(seg, mask) if m]


# generated text goes through the ledger and the guard
L = Ledger(res["run_id"])
n = L.num
c, t, S, G = res["counts"], res["totals"], "access_results.json", res["groups"]
sw = [s["isolated"] for s in res["sweep"]]
prot = ["Sentinel-1", "DOR"]
vk = lambda g: "bridge" if g["bridge"] else "road segment"

hero = (f"{n('n_strict', c['ISOLATED_STRICT'], 'settlements', S)} of {n('n_base', t['reachable_at_baseline'], 'settlements', S)} "
        f"settlements with a mapped hospital route may be cut off under the strict rule. "
        f"Across {n('n_sw', len(sw), 'rules', S)} closure rules the answer ranges from {n('sw_min', min(sw), 'settlements', S)} to {n('sw_max', max(sw), 'settlements', S)}.")

qa = []
if G:
    g0 = G[0]
    nm = ", ".join(g0["names"]) if g0["names"] else "none named on the map"
    prot.extend(g0["names"])
    a1 = (f"Under the strict rule {n('n_strict', c['ISOLATED_STRICT'], 'settlements', S)} settlements lose every road route to a destination hospital. "
          f"The biggest single dependency is the {vk(g0)} near {n('g0_lat', g0['lat'], 'deg', S, 4)}, {n('g0_lon', g0['lon'], 'deg', S, 4)}, "
          f"with {n('g0_k', g0['reconnect'], 'settlements', S)} settlements behind it, for example {nm}. "
          f"{n('n_multi', res['n_multi'], 'settlements', S)} cut-off settlements would stay cut off even if any single flagged place were open.")
    items = [f"{vk(g)} near {n(f'g{i}_lat', g['lat'], 'deg', S, 4)}, {n(f'g{i}_lon', g['lon'], 'deg', S, 4)} "
             f"({n(f'g{i}_k', g['reconnect'], 'settlements', S)} settlements, evidence score {n(f'g{i}_score', g['max_score'], 'score', S, 2)})"
             for i, g in enumerate(G[:3])]
    a2 = "Check these first: " + "; ".join(items) + ". Confirming one of them open would reconnect the settlements behind it."
    qa.append({"q": "Which villages may be cut off?", "a": a1})
    qa.append({"q": "What should responders check first?", "a": a2})
a3 = (f"The count of {n('n_strict', c['ISOLATED_STRICT'], 'settlements', S)} depends on the rule: {n('sw0', sw[0], 'settlements', S)} at the loosest setting "
      f"and {n('sw4', sw[-1], 'settlements', S)} at the strictest. "
      f"Flagged road is {n('km_strict', t['km_flag_strict'], 'km', S, 1)} km of {n('km_assess', t['km_assessable'], 'km', S, 1)} km assessable. "
      f"Flagged means the radar signal near the road dropped more than in all of {n('n_pl', 9, 'pairs', S)} non-flood radar pairs. It is evidence of change, not confirmed damage.")

a4 = (f"{n('km_unass', t['km_unassessed'], 'km', S, 1)} km of road inside the radar footprint lies in layover, shadow or poor geometry and is not assessed. "
      f"{n('n_noroad', c['NO_ROAD'], 'settlements', S)} settlements have no mapped road and {n('n_track', c['TRACK_ONLY'], 'settlements', S)} have only a track, "
      "so they are not reported as cut off. Roads outside the radar footprint are not assessed, optical imagery is not used, and nothing here is confirmed damage.")
qa.append({"q": "How sure are we?", "a": a3})
qa.append({"q": "What can DOR not see?", "a": a4})
canned = {"how_sure": a3, "cannot_see": a4}
if G:
    canned.update({"cut_off": a1, "check_first": a2})
(OUT / "qa.json").write_text(json.dumps(canned, ensure_ascii=False, indent=1), encoding="utf-8")

for text in [hero] + [x["a"] for x in qa]:
    ok, problems = check(text, L, prot)
    if not ok:
        raise SystemExit(f"GUARD FAIL: {problems}")
print("guard PASS on hero and", len(qa), "answers | ledger entries:", len(L.entries))
L.save(OUT / "ledger_dashboard.json")

keep = ("name", "kind", "lat", "lon", "state", "base_km", "circuity")
data = {"bbox": BBOX, "run_id": res["run_id"], "counts": c, "sweep": res["sweep"], "hero": hero, "qa": qa,
        "settlements": [{k: r.get(k) for k in keep} for r in res["settlements"]],
        "tier1": res["tier1"], "groups": G[:8], "ctx": ctx,
        "strict": lines(m_strict), "loose": lines(m_loose), "attrib": ATTR,
        "sitrep": {"en": (OUT / "sitrep_en.md").read_text(encoding="utf-8"),
                   "ne": (OUT / "sitrep_ne.md").read_text(encoding="utf-8")}}

import base64
fpp = OUT / "footprint.png"
if fpp.exists():
    data["footprint"] = "data:image/png;base64," + base64.b64encode(fpp.read_bytes()).decode()
    data["footprint_bounds"] = json.loads((RAW / "footprint.json").read_text())["bounds"]

TEMPLATE = r"""<!doctype html><html><head><meta charset="utf-8"><title>DOR - What still connects?</title>

<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.css">
<style>
*{box-sizing:border-box}body{margin:0;display:flex;height:100vh;font:14px/1.45 system-ui,Segoe UI,Arial,sans-serif;color:#1d1d1b}
#side{width:440px;max-width:46vw;overflow:auto;padding:16px 18px;background:#fff;border-right:1px solid #ddd}
#map{flex:1;background:#f4f1ea}
h1{margin:0;font-size:28px}h1 small{display:block;font-size:13px;font-weight:400;color:#6b6a63}
h3{margin:18px 0 6px;font-size:13px;text-transform:uppercase;letter-spacing:.06em;color:#6b6a63}
.banner{background:#fff4d6;border:1px solid #e9d08a;padding:6px 9px;font-size:12px;margin:10px 0}
.hero{font-size:17px;font-weight:600;margin:12px 0}
.row{display:flex;align-items:center;gap:8px;margin:2px 0}.dot{width:11px;height:11px;border-radius:50%;flex:none}
button{font:inherit;padding:5px 9px;margin:2px 3px 2px 0;border:1px solid #bbb;background:#fafafa;border-radius:6px;cursor:pointer}
button.on{background:#1d1d1b;color:#fff}
.card{border:1px solid #ddd;border-radius:8px;padding:8px 10px;margin:6px 0;cursor:pointer}.card:hover{background:#f7f7f4}
table{border-collapse:collapse;width:100%;font-size:12px}td,th{border-bottom:1px solid #eee;padding:3px 4px;text-align:right}th:first-child,td:first-child{text-align:left}
#ans{margin-top:8px;padding:8px 10px;background:#f4f1ea;border-radius:8px;display:none}
#sitrep{white-space:pre-wrap;font-size:12px;background:#fafafa;padding:8px;border:1px solid #eee;max-height:320px;overflow:auto}
sup.ref{color:#999;font-size:9px}.foot{font-size:11px;color:#6b6a63;margin-top:18px}
</style></head><body>
<div id="side">
<h1>DOR <small>What still connects?</small></h1>
<div class="banner">Educational prototype, not an operational tool. Evidence of radar change near roads, not confirmed damage. Run <span id="run"></span>.</div>
<div class="hero" id="hero"></div>
<h3>Settlements by state</h3><div id="legend"></div>
<h3>Ask DOR</h3><div id="qbtn"></div>
<div style="margin-top:6px"><input id="q" style="width:72%;padding:5px" placeholder="Ask in your own words (needs the local server)"> <button id="go">Ask</button></div>
<div id="ans"></div>
<h3>Check these first</h3><div id="groups"></div>
<h3>How the answer depends on the rule</h3><table id="sweep"></table>
<h3>Situation report</h3><div><button id="b_en" class="on">English</button><button id="b_ne">Nepali</button></div><div id="sitrep"></div>
<div class="foot" id="foot"></div>
</div><div id="map"></div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.js"></script>
<script>
const D = __DATA__;
const COL = {ISOLATED_STRICT:"#c0392b",ISOLATED_LOOSE:"#e67e22",UNCERTAIN_UNASSESSED:"#8e44ad",REROUTED:"#d4ac0d",NO_CHANGE:"#2c7fb8",TRACK_ONLY:"#8d6e63",DISCONNECTED_BASELINE:"#7f8c8d",NO_ROAD:"#000"};
const LAB = {ISOLATED_STRICT:"Cut off (strict rule)",ISOLATED_LOOSE:"Cut off (loose rule only)",UNCERTAIN_UNASSESSED:"Depends on road we could not assess",REROUTED:"Longer route",NO_CHANGE:"No change found",TRACK_ONLY:"Track only, not judged",DISCONNECTED_BASELINE:"Never reached a hospital on the map",NO_ROAD:"No mapped road, not judged"};
const h = s => String(s).replace(/[&<>]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));
const clean = t => h(t).replace(/\[(L\d{3})\]/g, '<sup class="ref">$1</sup>');
const flip = a => a.map(p => [p[1], p[0]]);
const map = L.map("map", {preferCanvas:true});
map.fitBounds([[D.bbox[1], D.bbox[0]], [D.bbox[3], D.bbox[2]]]);
let fpl = null;
if (D.footprint) { const b = D.footprint_bounds; fpl = L.imageOverlay(D.footprint, [[b.south, b.west], [b.north, b.east]], {opacity:0.85}).addTo(map); }
const ctx = L.polyline(D.ctx.map(flip), {color:"#b9b4a6", weight:1}).addTo(map);
const loose = L.polyline(D.loose.map(flip), {color:"#e67e22", weight:3}).addTo(map);
const strict = L.polyline(D.strict.map(flip), {color:"#c0392b", weight:4}).addTo(map);
const setl = L.layerGroup().addTo(map);
D.settlements.forEach(s => {
  const m = L.circleMarker([s.lat, s.lon], {radius: s.state === "ISOLATED_STRICT" ? 6 : 4, color:"#fff", weight:1, fillColor: COL[s.state] || "#999", fillOpacity:.95});
  m.bindPopup("<b>" + h(s.name || ("unnamed " + s.kind)) + "</b><br>" + h(LAB[s.state] || s.state) +
    (s.base_km != null ? "<br>route to nearest destination hospital before the event: " + s.base_km + " km" : "") +
    (s.circuity ? "<br>route / straight line: " + s.circuity : ""));
  m.addTo(setl);
});
const hosp = L.layerGroup().addTo(map);
D.tier1.forEach(x => L.circleMarker([x.lat, x.lon], {radius:9, color:"#1e8449", weight:3, fillColor:"#fff", fillOpacity:1}).bindTooltip(h(x.name || "hospital")).addTo(hosp));
const grp = L.layerGroup().addTo(map);
D.groups.forEach((g, i) => {
  const m = L.circleMarker([g.lat, g.lon], {radius:12, color:"#000", weight:2, fill:false});
  m.bindPopup("<b>" + (g.bridge ? "Bridge" : "Road segment") + "</b><br>" + g.reconnect + " settlements are cut off behind it (strict rule).<br>Evidence score " + g.max_score + ". Verify first.");
  m.addTo(grp); g._m = m;
});
const ov = {"Pre-event main roads":ctx, "Flagged road (loose)":loose, "Flagged road (strict)":strict, "Settlements":setl, "Destination hospitals":hosp, "Check first":grp};
if (fpl) ov["Radar change evidence zone"] = fpl;
L.control.layers(null, ov, {collapsed:false}).addTo(map);


document.getElementById("run").textContent = D.run_id;
document.getElementById("hero").innerHTML = clean(D.hero);
document.getElementById("legend").innerHTML = Object.keys(LAB).map(k => '<div class="row"><span class="dot" style="background:' + COL[k] + '"></span>' + h(LAB[k]) + ': <b>' + (D.counts[k] || 0) + '</b></div>').join("");
const ans = document.getElementById("ans");
document.getElementById("qbtn").innerHTML = D.qa.map((x, i) => '<button data-i="' + i + '">' + h(x.q) + '</button>').join("");
document.querySelectorAll("#qbtn button").forEach(b => b.onclick = () => { ans.style.display = "block"; ans.innerHTML = clean(D.qa[b.dataset.i].a); });
document.getElementById("groups").innerHTML = D.groups.map((g, i) => '<div class="card" data-i="' + i + '"><b>' + (g.bridge ? "Bridge" : "Road segment") + '</b> near ' + g.lat.toFixed(4) + ', ' + g.lon.toFixed(4) + '<br>' + g.reconnect + ' settlements behind it' + (g.names.length ? ': ' + h(g.names.join(", ")) : '') + '</div>').join("");
document.querySelectorAll("#groups .card").forEach(c => c.onclick = () => { const g = D.groups[c.dataset.i]; map.flyTo([g.lat, g.lon], 13); g._m.openPopup(); });
document.getElementById("sweep").innerHTML = '<tr><th>min score / placebos at or above</th><th>flagged km</th><th>cut off</th></tr>' + D.sweep.map(s => '<tr><td>' + s.min_score + ' / ' + s.max_k + '</td><td>' + s.km_flagged + '</td><td>' + s.isolated + '</td></tr>').join("");
const sr = document.getElementById("sitrep");
function show(l) { sr.innerHTML = clean(D.sitrep[l]); document.getElementById("b_en").className = l === "en" ? "on" : ""; document.getElementById("b_ne").className = l === "ne" ? "on" : ""; }
document.getElementById("b_en").onclick = () => show("en"); document.getElementById("b_ne").onclick = () => show("ne"); show("en");
document.getElementById("foot").innerHTML = D.attrib.map(h).join("<br>");
document.getElementById("go").onclick = async () => {
  const q = document.getElementById("q").value.trim();
  if (!q) return;
  ans.style.display = "block"; ans.textContent = "thinking...";
  try {
    const r = await fetch("/ask", {method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({q: q, lang: document.getElementById("b_ne").className === "on" ? "ne" : "en"})});
    const j = await r.json();
    const src = j.cited ? Object.entries(j.cited).map(([k, v]) => "<br>" + k + " = " + h(v)).join("") : "";
    ans.innerHTML = clean(j.answer || "No answer.") +
      '<div class="foot">' + (j.mode === "llm" ? "Model answer. Numbers are checked against the ledger. The wording is not verified, check the sources below." :
       j.mode === "refusal" ? "No evidence for this in the run." : "Standard answer (the model was unavailable, found no matching fact, or failed the check).") +
      src + '</div>';
  } catch (e) { ans.textContent = "Free-text questions need the local server: python scripts/serve.py"; }
};

</script></body></html>"""

(OUT / "dashboard.html").write_text(
    TEMPLATE.replace("__DATA__", json.dumps(data, ensure_ascii=False).replace("</", "<\\/")), encoding="utf-8")
print("wrote outputs/dashboard.html")


# printable one-page situation reports, print to PDF from the browser
def md_html(md):
    out, ul = False, False
    lines_out = []
    for line in md.splitlines():
        if line.startswith("- "):
            if not ul:
                lines_out.append("<ul>")
                ul = True
            lines_out.append("<li>" + html.escape(line[2:]) + "</li>")
            continue
        if ul:
            lines_out.append("</ul>")
            ul = False
        if line.startswith("# "):
            lines_out.append("<h1>" + html.escape(line[2:]) + "</h1>")
        elif line.strip():
            lines_out.append("<p>" + html.escape(line) + "</p>")
    if ul:
        lines_out.append("</ul>")
    return re.sub(r"\[(L\d{3})\]", r"<sup>\1</sup>", "\n".join(lines_out))


PAGE = ("<!doctype html><html><head><meta charset='utf-8'><title>DOR situation report</title><style>"
        "@page{size:A4;margin:12mm}body{font:9.5pt/1.35 system-ui,Segoe UI,Arial,sans-serif;color:#111}"
        "h1{font-size:14pt;margin:0 0 6px}p{margin:3px 0}ul{margin:3px 0;padding-left:16px}sup{font-size:6pt;color:#888}"
        ".f{margin-top:8px;font-size:7.5pt;color:#555;border-top:1px solid #ccc;padding-top:4px}</style></head><body>"
        "{body}<div class='f'>{attr}</div></body></html>")
for lang in ("en", "ne"):
    body = md_html((OUT / f"sitrep_{lang}.md").read_text(encoding="utf-8"))
    (OUT / f"sitrep_{lang}.html").write_text(
        PAGE.replace("{body}", body).replace("{attr}", "<br>".join(html.escape(a) for a in ATTR)), encoding="utf-8")
print("wrote outputs/sitrep_en.html and outputs/sitrep_ne.html (open, print to PDF, check it fits one page)")
