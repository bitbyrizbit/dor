import json
import pathlib
from .ledger import Ledger

SAFE = ["Sentinel-1", "Sentinel-2", "OpenStreetMap", "DOR"]
EN = {
    "title": "DOR situation report for event date {event_date}",
    "method": "Generated automatically from Sentinel-1 radar change and pre-event OpenStreetMap roads (snapshot {osm_date}). Educational prototype, not an operational tool.",
    "summary": "Settlements assessed: {n_settle}. Cut off from every named hospital under the strict criterion: {n_strict}. Cut off only under the loose criterion: {n_loose}.",
    "uncertain": "Settlements whose route depends on road the satellite could not assess: {n_unc}. Settlements with a longer route under the loose criterion: {n_rer}, on average {mean_extra} km longer.",
    "noroad": "Settlements with no mapped road access before the event: {n_noroad}, and with a mapped road that never reached a hospital: {n_disc}. They are not reported as cut off.",
    "flags": "Road flagged: {km_strict} km (strict) and {km_loose} km (loose) of {km_assess} km assessable. Bridge structures flagged (strict): {br_strict} of {br_total}.",
    "unassessed": "Unable to assess: {km_unass} km of road lies in radar layover or shadow. This is not the same as undamaged.",
    "list_head": "Settlements most likely cut off:",
    "item": "- {name}: {state}. The nearest named hospital was {base} km away on the pre-event map.",
    "item_unnamed": "- unnamed {kind} near {lat}, {lon}: {state}. The nearest named hospital was {base} km away on the pre-event map.",
    "verify_head": "Most useful places to verify first:",
    "verify_item": "- {vkind} near {lat}, {lon}: confirming it open would reconnect {k} settlements.",
    "limits": "Flagged means radar signal near the road dropped more than in all (strict) or nearly all (loose) of nine non-flood radar pairs. It is evidence of change, not confirmed damage. Hospitals outside the mapped area are not considered.",
    "state_ISOLATED_STRICT": "cut off from every named hospital (strict)",
    "state_ISOLATED_LOOSE": "cut off under the loose criterion only",
    "state_UNCERTAIN_UNASSESSED": "route depends on road that could not be assessed",
    "kind_hamlet": "hamlet", "kind_village": "village", "kind_town": "town",
    "vkind_bridge": "bridge", "vkind_road": "road segment",
}
NE = json.loads(pathlib.Path(__file__).with_name("ne.json").read_text(encoding="utf-8"))
RANK = ["ISOLATED_STRICT", "ISOLATED_LOOSE", "UNCERTAIN_UNASSESSED"]


def build(res, lang="en"):
    T = EN if lang == "en" else NE
    L = Ledger(res["run_id"])
    n, c, t = L.num, res["counts"], res["totals"]
    src = "access_results.json"
    V = {
        "event_date": L.fixed("event_date", res["event_date"], src),
        "osm_date": L.fixed("osm_date", res["osm_snapshot"], src),
        "n_settle": n("n_settle", len(res["settlements"]), "settlements", src),
        "n_strict": n("n_strict", c["ISOLATED_STRICT"], "settlements", src),
        "n_loose": n("n_loose", c["ISOLATED_LOOSE"], "settlements", src),
        "n_unc": n("n_unc", c["UNCERTAIN_UNASSESSED"], "settlements", src),
        "n_rer": n("n_rer", c["REROUTED"], "settlements", src),
        "mean_extra": n("mean_extra", res["mean_extra_km"], "km", src, 1),
        "n_noroad": n("n_noroad", c["NO_ROAD"], "settlements", src),
        "n_disc": n("n_disc", c["DISCONNECTED_BASELINE"], "settlements", src),
        "km_strict": n("km_strict", t["km_flag_strict"], "km", src, 1),
        "km_loose": n("km_loose", t["km_flag_loose"], "km", src, 1),
        "km_assess": n("km_assess", t["km_assessable"], "km", src, 1),
        "km_unass": n("km_unass", t["km_unassessed"], "km", src, 1),
        "br_strict": n("br_strict", t["bridge_structures_strict"], "structures", src),
        "br_total": n("br_total", t["bridge_structures_total"], "structures", src),
    }
    protected = list(SAFE)
    lines = ["# " + T["title"].format(**V), "", T["method"].format(**V), "",
             T["summary"].format(**V), T["uncertain"].format(**V), T["noroad"].format(**V),
             T["flags"].format(**V), T["unassessed"].format(**V), ""]
    iso = [r for r in res["settlements"] if r["state"] in RANK]
    iso.sort(key=lambda r: (RANK.index(r["state"]), r["base_km"] or 0))
    if iso:
        lines.append(T["list_head"])
        for r in iso[:8]:
            key = f"s{r['osm_id']}"
            vals = {"state": T["state_" + r["state"]], "base": n(key + "_base", r["base_km"], "km", src, 1)}
            if r.get("name"):
                protected.append(r["name"])
                vals["name"] = r["name"]
                lines.append(T["item"].format(**vals))
            else:
                vals["kind"] = T["kind_" + r["kind"]]
                vals["lat"] = n(key + "_lat", r["lat"], "deg", src, 4)
                vals["lon"] = n(key + "_lon", r["lon"], "deg", src, 4)
                lines.append(T["item_unnamed"].format(**vals))
        lines.append("")
    if res["groups"]:
        lines.append(T["verify_head"])
        for gi, g in enumerate(res["groups"][:3]):
            if g["reconnect"] <= 0:
                continue
            key = f"g{gi}"
            lines.append(T["verify_item"].format(
                vkind=T["vkind_bridge" if g["bridge"] else "vkind_road"],
                lat=n(key + "_lat", g["lat"], "deg", src, 4), lon=n(key + "_lon", g["lon"], "deg", src, 4),
                k=n(key + "_k", g["reconnect"], "settlements", src)))
        lines.append("")
    lines.append(T["limits"].format(**V))
    return "\n".join(lines), L, protected
