from datetime import date, timedelta
from dor.acquire.pairs import choose


def mk(start, n, track, step=12):
    return [{"id": f"{track}-{i}", "date": start + timedelta(days=step * i), "track": track,
             "platform": "x", "cov": 1.0} for i in range(n)]


def test_trishuli_like_selection():
    t85, t19 = (85, "ascending"), (19, "descending")
    scenes = (mk(date(2026, 7, 11), 6, t85) + mk(date(2025, 6, 15), 11, t85)
              + mk(date(2024, 6, 20), 12, t85) + mk(date(2026, 8, 24), 2, t19))
    res = choose(scenes, date(2026, 8, 26))
    top = res["events"][0]
    assert top["track"] == t85
    assert top["pre"]["date"] == date(2026, 8, 16) and top["post"]["date"] == date(2026, 8, 28)
    assert [str(p[1]["date"]) for p in res["ref"]] == ["2026-08-16", "2026-08-04", "2026-07-23"]
    assert len(res["val"]) == 3 and all(p[1]["date"].year < 2026 for p in res["val"])


def test_no_pair_spanning_date():
    res = choose(mk(date(2026, 1, 1), 3, (1, "ascending")), date(2026, 8, 26))
    assert res["events"] == []
