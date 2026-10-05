# Data decisions

## Sentinel-1 pair (Trishuli corridor, event 2026-08-26)
- Primary: relative orbit 85 ascending, 2026-08-16 (pre) and 2026-08-28 (post)
- Cross-check: relative orbit 19 descending, 2026-08-24 (pre) and 2026-09-05 (post)
- Backup: relative orbit 121 descending, 2026-08-19 and 2026-08-31
- GRD coverage of AOI: 100% on primary pair
- SLC available for primary pair, same datatakes (coherence feasible, processing untested)

## OpenStreetMap source (pre-event)
- Snapshot date: 2026-07-27 (before the 2026-08-26 event)
- Source used in the run: overpass-api.de with the [date:] directive, waterway=river, 70 ways in the AOI bbox
- ohsome API: data endpoints (POST) returned 403 from this machine, with and without a custom User-Agent, while the metadata endpoint returned 200. Cause not identified yet
- Overpass history queries timed out once (504) before succeeding on retry, so expect flaky behaviour on large AOIs
- Mirrors without confirmed [date:] support must not be used (risk of silently returning post-event OSM). Source name is printed on every run and must go in the run manifest
- Required attribution: (c) OpenStreetMap contributors, ODbL

## Geocoding findings (primary pair, track 85 ascending, 2026-08-16 and 2026-08-28)
- GRD COG files carry no CRS, only 210 GCPs in EPSG:4326
- Same-track pair, so change detection runs in the native radar grid. Pre and post median DN are 190 vs 189, global offset removed -0.05 dB, so no radiometric correction needed for now
- Geocoding via GCP thin-plate-spline (24 GCPs in the AOI) ignores terrain
- Measured mismatch against pre-event OSM rivers: median distance from strong-change pixels to nearest river 916 m before any shift, p90 2345 m
- Best global translation of the change map onto the river network: about 2.2 km west and 0.4 km south. Median distance falls to 293 m, 41 percent of strong-change cells within 200 m of a river
- Caveat: the metric is contaminated by terrain and moisture false positives, and a global shift cannot model displacement that varies with elevation. The shift is a diagnostic only and is never applied in the pipeline
- Decision: terrain-corrected geocoding with the Copernicus DEM is required before the infrastructure overlay, because road and bridge checks need tens of metres, not kilometres

## Open items
- Coherence: SLC scenes exist for the same datatakes, processing untested, cutoff day 6
- Strong-change thresholds (-3 dB, blobs of 30 px) are placeholders, not tuned
- Phase correlation coregistration reported low confidence (error 1.0), sharpness of the change line suggests it is fine, to be verified

- DEM: Copernicus DEM GLO-30 via the AWS Open Data mirror (copernicus-dem-30m), tiles N27_00_E085_00 and N28_00_E085_00. Chosen over CDSE because CDSE access may require Copernicus Contributing Missions registration. It is a surface model (includes canopy and buildings). Attribution string is in ATTRIBUTION.md.
