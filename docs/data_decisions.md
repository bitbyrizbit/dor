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

## DEM validation (first run)
- Copernicus DEM GLO-30 elevation range in the AOI: 454 to 5392 m, no gaps
- Valley-floor test, strong-change cells, height above local 2 km minimum: median 279 m at zero shift, 60 m at the OSM-fitted shift (random pixels: 502 m). Share under 50 m: 14.7 percent vs 45.1 percent vs 3.4 percent random
- Conclusion: a systematic geocoding offset exists and is supported by two independent datasets. Terrain-dependent, so a global shift is only a diagnostic
- Open: the offset direction (west) does not match a naive terrain-toward-sensor displacement. Hypothesis under test: the GCP reference height is high, so low terrain is displaced away from the sensor

## Geocoding root cause
- GCPs in the GRD COG are 3D points (z 240 to 6710 m over the scene, 1368 to 4575 m near the AOI). Plain 2D interpolation assumes grid heights of 1.4 to 4.6 km, while valley floors sit at about 0.5 to 1 km, so valley targets were placed roughly 2 km east of their true position
- Fix under test: inverse geocoding with a model from (lon, lat, DEM height) to (col, row), fitted on the GCPs
- Fallback if leave-one-out error stays above 20 px: range-Doppler geometry from the product annotation (orbit state vectors)

## Terrain-aware geocoding result (first run)
- Leave-one-out GCP error (px, 10 m): xy 51.1 mean, xyz 11.3, xyz2 4.2 mean and 14.8 max. Model chosen: xyz2 (7 parameters, 24 GCPs)
- Zero-shift results with the terrain-aware model: median distance to pre-event OSM rivers 215 m (was 916 m), 48 percent of strong-change cells within 200 m, 43 percent on valley floor. The global 2.2 km shift is no longer needed and is not applied anywhere
- Remaining spread (p75 1381 m, p90 2459 m) is false positives, not geocoding. To be handled by terrain masks
- Positional uncertainty to carry into the infrastructure stage: about 40 m mean, 150 m worst case. Use a buffer of about 100 m on road and bridge overlays
- Strong-change pixel counts are not comparable between geocodings because layover duplicates pixels

## Shift check after terrain-aware geocoding
- Best global shift on diff_terrain: about 197 m west, 166 m south. Mean capped distance 612 m vs 604 m at best shift, cost surface flat. Systematic offset removed. No shift is applied anywhere
- Correction: terrain-aware vs TPS plus fitted shift is a tie on the same coarse metric (mean capped distance 612 vs 546 m, within 200 m of river 44.7 vs 41 percent), not a clear win. The benefit is that it is physical and needs no fit to OSM