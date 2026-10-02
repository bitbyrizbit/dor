from collections import defaultdict
from datetime import datetime, timedelta
from pystac_client import Client

STAC = "https://stac.dataspace.copernicus.eu/v1"

def find_s1_pairs(bbox, event_date, window_days=30, gap_days=12):
    ev = datetime.fromisoformat(event_date)
    start = (ev - timedelta(days=window_days)).strftime("%Y-%m-%d")
    end = (ev + timedelta(days=window_days)).strftime("%Y-%m-%d")
    cat = Client.open(STAC)
    items = list(cat.search(
        collections=["sentinel-1-grd"],
        bbox=bbox,
        datetime=f"{start}/{end}",
        max_items=500,
    ).items())

    if not items:
        print("No items found. Collection ID might be wrong.")
        return []

    # If first item doesn't have the expected keys, print them for debugging
    props = items[0].properties
    if "sat:relative_orbit" not in props or "sat:orbit_state" not in props:
        print("Available properties in first item:", list(props.keys()))

    by_track = defaultdict(list)
    for it in items:
        p = it.properties
        key = (p.get("sat:relative_orbit"), p.get("sat:orbit_state"))
        by_track[key].append(it)

    pairs = []
    for key, its in by_track.items():
        its.sort(key=lambda i: i.datetime)
        for a in its:
            for b in its:
                d = (b.datetime - a.datetime).days
                if d == gap_days and a.datetime < ev.replace(tzinfo=a.datetime.tzinfo) <= b.datetime:
                    pairs.append((key, a.id, b.id, a.datetime, b.datetime))
    return pairs

if __name__ == "__main__":
    bbox = [85.10, 27.85, 85.45, 28.25]  # rough trishuli corridor, verify on map
    pairs = find_s1_pairs(bbox, "2026-08-26")
    for p in pairs:
        print(p)
