from dor.copilot.report import build
from dor.copilot.guard import check

RES = {
    "run_id": "t", "event_date": "2026-08-26", "osm_snapshot": "2026-07-27",
    "counts": {"ISOLATED_STRICT": 3, "ISOLATED_LOOSE": 0, "UNCERTAIN_UNASSESSED": 2, "REROUTED": 1,
               "NO_CHANGE": 4, "TRACK_ONLY": 1, "DISCONNECTED_BASELINE": 1, "NO_ROAD": 2},
    "mean_extra_km": 4.2,
    "totals": {"reachable_at_baseline": 10, "km_flag_strict": 3.5, "km_flag_loose": 4.0,
               "km_assessable": 100.0, "km_unassessed": 10.0,
               "bridge_structures_total": 7, "bridge_structures_strict": 2},
    "sweep": [{"isolated": 3}, {"isolated": 3}, {"isolated": 3}, {"isolated": 2}, {"isolated": 0}],
    "circuity": {"n_suspect": 1}, "n_multi": 1, "settlements": [{}] * 14,
    "groups": [{"lat": 27.9, "lon": 85.1, "bridge": True, "reconnect": 2, "max_score": 0.17,
                "names": ["Ward 5"]},
               {"lat": 28.0, "lon": 85.2, "bridge": False, "reconnect": 1, "max_score": 0.08, "names": []}],
}


def test_templates_pass_guard_both_languages():
    pairs = {}
    for lang in ("en", "ne"):
        text, L, prot = build(RES, lang)
        ok, problems = check(text, L, prot)
        assert ok, problems
        pairs[lang] = L.pairs()
    assert pairs["en"] == pairs["ne"]


def test_tampered_report_fails():
    text, L, prot = build(RES, "en")
    assert not check(text + "\n99 settlements are cut off.", L, prot)[0]
