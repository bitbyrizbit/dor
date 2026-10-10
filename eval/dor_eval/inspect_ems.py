import pathlib
import geopandas as gpd

ROOT = pathlib.Path("eval/data/ems")
EXT = {".shp", ".geojson", ".json", ".gpkg", ".kml"}
BBOX = (85.10, 27.85, 85.45, 28.25)

files = sorted(p for p in ROOT.rglob("*") if p.suffix.lower() in EXT)
print("vector files found:", len(files))
for p in files:
    layers = [None]
    if p.suffix.lower() == ".gpkg":
        import pyogrio
        layers = [l[0] for l in pyogrio.list_layers(p)]
    for lay in layers:
        try:
            g = gpd.read_file(p, layer=lay) if lay else gpd.read_file(p)
        except Exception as e:
            print(p, lay, "READ FAILED", repr(e)[:120])
            continue
        if not hasattr(g, "crs") or not hasattr(g, "geometry"):
            print("---", p.relative_to(ROOT), lay or "", "(non-spatial table, skipped)")
            continue
        print("---", p.relative_to(ROOT), lay or "")
        print("   rows:", len(g), "| crs:", g.crs, "| geometry:", dict(g.geom_type.value_counts()))

        if len(g) == 0:
            continue
        g4 = g.to_crs(4326) if g.crs else g
        print("   bounds:", [round(x, 3) for x in g4.total_bounds])
        inside = g4.cx[BBOX[0]:BBOX[2], BBOX[1]:BBOX[3]]
        print("   rows touching our bbox:", len(inside))
        for col in g.columns:
            if col == "geometry":
                continue
            u = g[col].nunique(dropna=True)
            if u <= 12:
                print("   ", col, dict(g[col].value_counts(dropna=False)))
            else:
                print("   ", col, "(", u, "distinct )")
