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

## Geometry classes (first run)
- Model sanity: range bearing 80.3 deg (east, consistent with ascending right-looking), 9.95 m/px along range, incidence estimate 38.6 deg (from GCPs, not from the product annotation)
- AOI shares: good 75.9, poor 19.3, layover 4.6, shadow 0.2 percent. Thresholds (poor under 15 or 75 to 90 deg local incidence) are placeholders
- Strong-change cells fall in bad geometry only slightly more often than the base rate (26 vs 24 percent), so geometry does not generate most false positives
- Strong cells in good geometry are close to rivers far more often (median 132 m, 59 percent within 200 m) than in bad geometry (1384 m, 19.6 percent)
- Design rule confirmed: bad-geometry cells become "unable to assess", never "no damage"
- Open: 41 percent of good-geometry strong cells are over 200 m from mapped rivers. River distance is a proxy only, OSM rivers are incomplete
- Open: detector keeps only decreases below -3 dB and loses increases (rough debris). Switch to absolute change with sign as a feature

## HAND (first run)
- HAND computed from Copernicus DEM (30 m, subsampled from the AOI grid) with pysheds. pysheds calls np.in1d, which numpy 2.4 removed, so a shim or a numpy pin below 2.4 is required
- Strong |change| cells in good geometry (27930): median HAND 18 m (dense network, 500 cells) vs 238 m for random pixels. Under 20 m: 52.3 vs 7.8 percent. Result holds with a sparse network (3000 cells): 47.8 vs 4.9 percent
- Caveat: random pixels are a weak baseline and monsoon river change is not separated from the flood yet. Next: placebo pair on a pre-event interval of the same track
- HAND is a weight, not a gate: debris flows climb tens of metres in gorges. 34 percent of strong cells have HAND above 50 m

## Track 85 ascending scenes in the AOI (all 100 percent coverage, 12 days apart)
2026-07-11, 07-23, 08-04, 08-16, 08-28, 09-09, 09-21
- Event pair: 08-16 to 08-28. Placebo pairs (no event): 07-23 to 08-04 and 08-04 to 08-16. Post pair: 08-28 to 09-09
- All pairs processed by scripts/run_pair.py with identical settings and thresholds

## Placebo comparison (same track 85, identical settings, absolute change above 3 dB, good geometry only)
- Strong cells per km2: event 24.2, placebo 07-23/08-04 10.7, placebo 08-04/08-16 15.1, post 08-28/09-09 15.2. Total-count ratio event to placebo is only 1.6 to 2.3. False alarm floor of about 7 to 14 strong cells per km2 in every pair, event included
- Share within 200 m of a pre-event OSM river: event 55 percent, placebos 16 and 10 percent, post 53 percent. River-aligned density per km2 (arithmetic from the above): event 13.4, placebos 1.7 and 1.5, post 8.0. HAND under 20 m density: event 12.7, placebos about 2.3
- Conclusion: ordinary monsoon change is not channel-aligned, the flood signal is. The post pair keeps most of the signal with the same sign, so change is progressive, not a one-scene artefact. Cause not identified
- The south-to-north split does not discriminate (43 to 54 percent in the south for every pair)
- Rule: thresholds must not be tuned to maximise OSM river alignment (circular) or against EMSR927 (check-only). Tuning uses placebo pairs as known negatives, with a held-out placebo

## Correction after placebo3 (2026-07-11 to 07-23, same track)
- Placebo3 is the noisiest pair: 42.1 strong cells per km2 (event 24.2), 30 percent negative (event 65.5), within 200 m of rivers 20.7 percent, HAND under 20 m 54.2 percent. Mostly brightening on the wide southern valley floor. Cause not established (seasonal soil or crop change is a guess)
- The earlier claim "HAND under 20 m separates the event from placebos" is withdrawn: placebo3 has 22.8 HAND-under-20 cells per km2 against 12.7 for the event. HAND stays a weight, not evidence
- The earlier claim "event has 8 to 9x the river-aligned density of placebos" held only for placebos 1 and 2. Against placebo3 it is 1.5x (13.4 vs 8.7 per km2)
- What still holds: share of strong cells within 200 m of a river is higher in the event (55 percent) than in any placebo (10 to 21 percent), and the sign mix differs
- Z-score against local placebo sigma (sigma from placebos 2 and 3, 31 px window, placebo1 held out): at z 3.0 total ratio 5.6, river-aligned ratio 18.3. This is one held-out placebo, the quietest. Not a conclusion. Leave-one-out across all three placebos is the next check

## Leave-one-out z-score results (sigma from two placebos, third held out, event never in the reference set)
- Worst fold is placebo3 held out. Total strong-cell ratio event / held-out placebo is 0.6 to 0.8 at every z from 2.5 to 4.0, so the placebo is louder than the event. On the quieter folds: z 3.0 total ratio 5.6 (placebo1 held out) and 2.1 (placebo2 held out)
- The earlier statement that z-scoring improves the total ratio from about 2.3 to 5.6 held for one fold only. Retracted as a general claim
- Conclusion: amplitude change relative to local variability, learned from three 2026 placebos, does not separate the flood from monsoon variability in the worst fold. No threshold is chosen
- Likely reason (hypothesis): placebo3 conditions are noisier than the reference placebos, 73 percent of its strong cells lie in the southernmost band (wide valley floor), mostly brightening. Cause not established
- Post-hoc observation, not a result: river-aligned darkening only gives event / worst placebo 3.8 to 5.7 across z 2.5 to 4.0 (arithmetic from the printed shares, which are rounded). Found by inspecting the same pairs, so it needs out-of-sample testing. It does not remove ordinary river-water darkening, because river-aligned placebo cells are also mostly dark at high z in placebos 1 and 2
- HAND does not separate the event, main-channel proximity does. DEM-derived main-channel distance must replace OSM river distance before the pipeline depends on it, since OSM rivers may be sparse elsewhere
- Frozen rule for out-of-sample testing (set before new runs): sigma from all three 2026 placebos, z below -3.0, 3 px smoothing, blobs of 30+ px, good geometry, within 200 m of an OSM river, metric cells per km2. Pass: event density at least 3x on every new placebo

## Pre-registered out-of-sample test (frozen before any new pair was run)
- Rule: sigma from placebos 2026-07-23/08-04, 08-04/08-16, 07-11/07-23 (31 px window, floor at 5th percentile). z below -3.0 after 3 px smoothing, blobs of 30+ px, good geometry only, within 200 m of a pre-event OSM river. Metric: cells per km2 of good geometry
- New placebos (track 85 ascending, S1A): 2025-07-21/08-02, 08-02/08-14, 08-14/08-26, 08-26/09-07, 2024-07-14/07-26, 07-26/08-07, 08-07/08-19, 08-19/08-31, 08-31/09-12
- Excluded: 2025-06-27/07-09 (spans the 2025-07-08 Bhotekoshi flood, used as positive control) and 2025-07-09/07-21 (aftermath)
- Pass: 2026 event density at least 3x every placebo. Positive control: at least 3x the median placebo
- Exclusions only for a dated documented flood or a failed run, never for score
- Caveats: sensor change S1A vs S1D, one track and AOI, no ground truth, 2024 pairs not certified flood-free
- 2024-08-07 and 2024-08-19 exist as two product versions of one datatake. One is used (sorted by id)

## Out-of-sample test results (pre-registered test, run once, no exclusions)
- Rule as registered above. Event (2026-08-16/08-28): 6.59 river-aligned darkening cells per km2 (9.28 darkening in total)
- Nine new placebos (S1A, 2024 and 2025): river-aligned darkening 0.11 to 0.82 per km2. Event/placebo ratio 8.0 to 59.9, median 34.7. All nine pass the 3x criterion. Lowest ratio: 2024-08-31/09-12
- Positive control (2025-06-27/07-09, spans the 2025-07-08 Bhotekoshi flood): 3.96 per km2, 20.8x the median placebo (0.19). Pass
- Total darkening without the river filter does not separate: 2024-08-19/08-31 has 12.81 per km2 against 9.28 for the event, 2024-08-31/09-12 has 8.51. The separation comes from channel alignment (OSM rivers within 200 m), not from amplitude. Cause of the strong off-river darkening in 2024-08-19/08-31 is unknown
- Run health: all 10 pairs ran, coregistration offsets 1.1 px or less, GCP fit residual 2.2 to 2.3 px mean, 9.0 to 9.1 max
- Limits: the rule design (darkening, 200 m, z 3.0, river alignment) was chosen after seeing the event and the three 2026 placebos, so the event/placebo ratio is optimistic. The nine placebos and the positive control are out of sample. One track, one AOI, S1A vs S1D confound, 2024 pairs not certified flood-free, rule depends on OSM river coverage. No ground truth: false-alarm test, not accuracy
- Claim allowed: darkening along mapped channels in this AOI is 8x to 60x more frequent in the 2026 event pair than in nine non-flood pairs, and the 2025 flood pair also exceeds them. Not allowed: the detector is validated, or that it measures damage

## OSM roads, places and health facilities (pre-event, first run)
- Source: overpass-api.de, date directive 2026-07-27T00:00:00Z, queried with out meta. Newest element edit in the response: 2026-07-26T19:19:52Z. The script aborts if any element is newer than the snapshot. Attribution: (c) OpenStreetMap contributors, ODbL
- Roads: 2957 ways, 2236.1 km (unclassified 1352.6, track 472.6, tertiary 135.8, primary 97.8, residential 87.7, secondary 71.8, service 17.9). 151 connected components, largest holds 2012.3 km (90 percent). 88 bridge ways
- Places: 217 (hamlet 142, suburb 39, village 20, isolated_dwelling 15, town 1). 76 percent within 500 m of a road node, 94.5 percent within 2 km, 82.5 percent on the largest road component
- Health facilities: 17 entries. 4 distinct named hospitals (5 entries, Rasuwa District Hospital twice), 8 unnamed (7 hospital, 1 clinic), 3 health posts tagged as hospital, 1 village clinic. 15 of 17 on the largest component
- Decision: places off the main road component or far from any road are reported as "no mapped road access", never "cut off"
- Decision: tracks are excluded from the main graph and shown as unreliable alternatives. Class alone does not tell road quality (60 percent of length is unclassified), surface tags not yet used
- Decision: settlements are town, village, hamlet. Suburbs merge into their parent place
- Decision: two destination tiers. Tier 1 hospital: named, not a health post, deduplicated within 300 m. Tier 2: any health facility. Unnamed entries count only for tier 2
- Decision: outputs of the damage stage are named evidence scores, not probabilities, until checked against EMSR927 (check-only)

## Edge evidence (first run, event vs nine out-of-sample placebos)
- Score per road edge: share of a ~200 m window around the edge midpoint that is strong darkening (z below -3.0 vs sigma from the three 2026 placebos, blobs of 30+ px, good geometry). Flagged = score of at least 0.05 and above all nine placebos (event) or above the other eight (placebo folds). Ranking resolution is 1 in 10, so flagged means unusual, not probable
- Road inside AOI 2127.0 km: assessable 1960.3 km, unable to assess (poor geometry) 166.7 km (7.8 percent)
- Event flagged 34.0 km (1.7 percent of assessable). Placebo folds 1.8 to 16.4 km, median 3.8, loudest 2024-08-31/09-12 at 16.4 km. Event is about 9x the median and 2.1x the loudest placebo
- Event flags 17 of 88 bridge ways (28.1 percent of bridge length, other roads 1.7 percent). Placebo folds for bridges not yet computed, so no bridge conclusion
- Bridge ways overcount structures (several ways within 100 m). Count structures, clustered within 150 m
- The score is channel darkening near the crossing, not damage to the bridge: a 10 m pixel cannot see a deck, and a crossing over a darkened river scores high with the structure intact. Label it channel change at crossing
- Limits: darkening only, ranking against nine pairs, edges with under 50 percent good geometry are unable to assess, no ground truth

## Bridge fold check (edge evidence, event vs placebo folds)
- Assessable bridge structures (clustered within 150 m): 74. Event flags 13 structures (17 ways). Placebo folds flag 1, 0, 2, 0, 0, 0, 1, 1, 0 structures (median 0, max 2)
- Conclusion: channel darkening at bridge crossings separates the event from the placebo folds. It is channel change at the crossing, not damage to the bridge. Bridges follow the same rule as other edges
- Limits: ranking resolution 1 in 10, event ranked against 9 pairs and each fold against 8, 10 m pixels cannot see a deck

## Access scenarios (fixed before the first run)
- Graph: pre-event OSM roads, tracks excluded. Settlements are town, village, hamlet. Snap limit 500 m to a road node. Destination tier 1: named hospital, not a health post, deduplicated within 300 m. Any health facility is tier 2

## Access analysis, first run (superseded by v2, not to be quoted)
- 163 settlements: ISOLATED_STRICT 32, UNCERTAIN_UNASSESSED 32, REROUTED 3, NO_CHANGE 31, DISCONNECTED_BASELINE 16, NO_ROAD 49. Reachable at baseline 98
- Sensitivity (isolated of 98, loosest to strictest): 32, 32, 32, 29, 1. About 28 settlements depend on edges with score 0.10 to 0.20
- Known defects: graph ends at the SAR bbox (hospitals outside the box ignored), tracks excluded so track-only villages counted as NO_ROAD, list sorted by baseline distance but labelled most likely cut off, flagged km included tracks while the graph excluded them
- v2 changes: OSM roads and hospitals fetched with a 0.15 degree buffer, roads outside the SAR footprint treated as unassessed, TRACK_ONLY state, circuity check (route length over straight-line distance to nearest named hospital, 3.0 is a placeholder), results grouped by the flagged place that decides them, km counted without tracks
- Strict scenario: edges closed if assessable, score >= 0.05 and above all 9 placebos
- Loose scenario: edges closed if assessable, score >= 0.02 and at most 2 of 9 placebos at or above
- Unassessed scenario: loose closures plus every edge inside the AOI that is not assessable (layover, shadow, poor geometry)
- States: NO_ROAD, DISCONNECTED_BASELINE, ISOLATED_STRICT, ISOLATED_LOOSE (isolated under loose only), UNCERTAIN_UNASSESSED (reachable under loose, not under unassessed), REROUTED (loose route over 50 m longer), NO_CHANGE
- Closure is an assumption: a flagged edge is assumed impassable. Flagged means evidence of change near the road, not confirmed damage
- Sensitivity sweep over (0.02, 2), (0.03, 1), (0.05, 0), (0.10, 0), (0.20, 0) is reported with every result
- Output is evidence under named scenarios, not a calibrated probability, until checked against EMSR927

## Access analysis v2 (first buffered run) and corrections
- OSM fetch buffered by 0.15 degrees: 23401 ways, 8849.0 km, 442 components (largest 95 percent of length), 443 bridge ways, 685 places, 1049 points. Newest edit 2026-07-26T19:19:52Z, guard passed
- The automatic hospital filter returned 81 entries including health posts spelled in other ways, a beauty parlour, a hypnosis centre, dental and ENT clinics, and Kathmandu valley hospitals pulled in by the buffer. Replaced by a hand-picked destination list in configs/tier1_hospitals.json (Sanjivani, Kalika Community, Rasuwa District, Trishuli, Melamchi). This is a human choice, not a result
- Strict-isolated count 30, sensitivity 30, 30, 30, 29, 1 across five rules. One road segment near 28.1615N 85.3359E decides 10 settlements, 17 of 30 stay cut off even if any single flagged place is open
- The circuity threshold of 3.0 was a placeholder and flags half of all settlements (median 3.1). Removed from the report. Circuity stays in the CSV and popups
- The map in the first v2 paste (32/35/3/28/10/16/39) did not match the console and report (30/38/1/30/10/15/39), so the two came from different runs. Map titles now carry the run id
- Chamoli test (bbox from memory, 2021-02-07): 11 scenes on one track, no pair spans the date. Cause unknown. Live use on another area is not supported
- Scope: the AOI covers the upper and middle reach only. The reported runout is close to 100 km, so the lower reach is outside it
- EMSR927 (check-only): four areas of interest. Data downloaded by hand into eval/data/ems, not committed, never used for thresholds. Product names, versions and release dates to be recorded here exactly as the download page shows them

## Copilot with a language model (Groq)
- The model gets a numbered facts sheet built from the ledger, writes sentences that cite fact ids, never computes. Checker: every number must appear in a cited fact, every sentence must cite, unknown ids rejected. One retry with the checker's complaint, then template fallback. NOT_IN_FACTS refusal when the facts do not cover the question
- The guard stops invented numbers. It does not stop wrong wording, wrong place names or invented causes without digits. Manual review of the red-team answers covers that
- Key in .env, read only by a local server bound to 127.0.0.1, never embedded in the dashboard
- Facts (OSM place names and aggregate counts) are sent to a third-party API. No personal data
- Nepali answers are model-generated and not reviewed by a native speaker
- Free-tier rate limits apply, fallback exists. Red team: 13 prompts, smoke test only

