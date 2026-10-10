import json
import pathlib
from .ledger import Ledger

SAFE = ["Sentinel-1", "Sentinel-2", "OpenStreetMap", "DOR"]
EN = {
    "title": "DOR situation report for event date {event_date}",
    "method": "Generated automatically from Sentinel-1 radar change and pre-event OpenStreetMap roads (snapshot {osm_date}). Educational prototype, not an operational tool.",
    "summary": "Settlements considered: {n_settle}. With a mapped road route to a named hospital before the event: {n_base}. Cut off from every named hospital under the strict criterion: {n_strict}.",
    "sens": "That count depends on the closure rule. From the loosest to the strictest of five settings it is {sw0}, {sw1}, {sw2}, {sw3} and {sw4}.",
    "uncertain": "Settlements whose route depends on road that could not be assessed or lies outside the assessed area: {n_unc}. Settlements with a longer route under the loose criterion: {n_rer}, on average {mean_extra} km longer.",
    "noroad": "Not reported as cut off: no mapped road access before the event: {n_noroad}. Reachable only by a track: {n_track}. Mapped road that never reached a named hospital: {n_disc}.",
    "suspect": "Routes more than three times the straight-line distance to the nearest named hospital, which can mean a gap in the map: {n_suspect}.",
    "flags": "Road flagged: {km_strict} km (strict) and {km_loose} km (loose) of {km_assess} km of assessable road, tracks excluded. Bridge structures flagged (strict): {br_strict} of {br_total}.",
    "unassessed": "Unable to assess: {km_unass} km of road inside the radar footprint lies in layover, shadow or poor geometry. This is not the same as undamaged. Roads outside the footprint are also treated as unassessed.",
    "group_head": "Flagged places that decide the most settlements (verify these first):",
    "group_item": "- {vkind} near {lat}, {lon}: {k} settlements are cut off behind it under the strict criterion, for example {names}. Strongest evidence score there: {score}.",
    "group_item_noname": "- {vkind} near {lat}, {lon}: {k} settlements are cut off behind it under the strict criterion (none named on the map). Strongest evidence score there: {score}.",
    "multi": "Settlements cut off under the strict criterion that no single flagged place would reconnect: {n_multi}.",
    "limits": "Flagged means radar signal near the road dropped more than in all (strict) or nearly all (loose) of nine non-flood radar pairs. It is evidence of change, not confirmed damage, and a flagged place is assumed impassable. Hospitals beyond the mapped area are not considered.",
    "vkind_bridge": "bridge", "vkind_road": "road segment",
}
NE = json.loads(pathlib.Path(__file__).with_name("ne.json").read_text(encoding="utf-8"))


def build(res, lang="en"):
    T = EN if lang == "en" else NE
    L = Ledger(res["run_id"])
    n, c, t = L.num, res["counts"], res["totals"]
    src = "access_results.json"
    V = {
        "event_date": L.fixed("event_date", res["event_date"], src),
        "osm_date": L.fixed("osm_date", res["osm_snapshot"], src),
        "n_settle": n("n_settle", len(res["settlements"]), "settlements", src),
        "n_base": n("n_base", t["reachable_at_baseline"], "settlements", src),
        "n_strict": n("n_strict", c["ISOLATED_STRICT"], "settlements", src),
        "n_unc": n("n_unc", c["UNCERTAIN_UNASSESSED"], "settlements", src),
        "n_rer": n("n_rer", c["REROUTED"], "settlements", src),
        "mean_extra": n("mean_extra", res["mean_extra_km"], "km", src, 1),
        "n_noroad": n("n_noroad", c["NO_ROAD"], "settlements", src),
        "n_track": n("n_track", c["TRACK_ONLY"], "settlements", src),
        "n_disc": n("n_disc", c["DISCONNECTED_BASELINE"], "settlements", src),
        "n_suspect": n("n_suspect", res["circuity"]["n_suspect"], "settlements", src),
        "n_multi": n("n_multi", res["n_multi"], "settlements", src),
        "km_strict": n("km_strict", t["km_flag_strict"], "km", src, 1),
        "km_loose": n("km_loose", t["km_flag_loose"], "km", src, 1),
        "km_assess": n("km_assess", t["km_assessable"], "km", src, 1),
        "km_unass": n("km_unass", t["km_unassessed"], "km", src, 1),
        "br_strict": n("br_strict", t["bridge_structures_strict"], "structures", src),
        "br_total": n("br_total", t["bridge_structures_total"], "structures", src),
    }
    for i, s in enumerate(res["sweep"]):
        V[f"sw{i}"] = n(f"sw{i}", s["isolated"], "settlements", src)
    protected = list(SAFE)
    lines = ["# " + T["title"].format(**V), "", T["method"].format(**V), "",
             T["summary"].format(**V), T["sens"].format(**V), T["uncertain"].format(**V),
             T["noroad"].format(**V), T["flags"].format(**V),
             T["unassessed"].format(**V), ""]
    groups = res["groups"][:5]
    if groups:
        lines.append(T["group_head"])
        for gi, g in enumerate(groups):
            key = f"g{gi}"
            vals = {"vkind": T["vkind_bridge" if g["bridge"] else "vkind_road"],
                    "lat": n(key + "_lat", g["lat"], "deg", src, 4),
                    "lon": n(key + "_lon", g["lon"], "deg", src, 4),
                    "k": n(key + "_k", g["reconnect"], "settlements", src),
                    "score": n(key + "_score", g["max_score"], "score", src, 2)}
            if g["names"]:
                protected.extend(g["names"])
                vals["names"] = ", ".join(g["names"])
                lines.append(T["group_item"].format(**vals))
            else:
                lines.append(T["group_item_noname"].format(**vals))
        lines.append("")
    lines.append(T["multi"].format(**V))
    lines.append(T["limits"])
    return "\n".join(lines), L, protected
