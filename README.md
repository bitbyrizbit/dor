# DOR (डोर)

**What still connects?**

dor means thread. a flood cuts threads. this finds the ones still holding.

dor takes an area and a flood date and uses Sentinel-1/2, the Copernicus DEM
and pre-event OpenStreetMap to estimate which settlements are likely cut off from the nearest
town or hospital, how sure it is, and what a human should verify first.

Built for the Multimodal AI Hackathon 2026, Track B (Mapping Flood Damage from Space).
Educational prototype, not an operational tool.

## Status
Work in progress. See the roadmap below.

## What it answers
1. Where did the flood hit?
2. What was damaged?
3. Who is cut off, and how sure are we?
4. What should we check first?

## How it is different
- debris-flow aware: terrain-masked change detection, not a water threshold
- isolation as a probability over a simulated road graph
- "unable to assess" is a mapped state, never shown as safe
- copilot that cannot state a number that is not in the facts ledger (English and Nepali)

## Quickstart
(coming as the pipeline lands)

    dor run --aoi <bbox> --date 2026-08-26

## Pipeline
acquire -> preprocess -> evidence -> fusion -> infrastructure impact
-> connectivity (monte carlo) -> triage -> facts ledger -> copilot and report

## Data rules
See DATA_RULES.md. EMS/UNOSAT/post-event OSM are used only for evaluation, under eval/.

## Evaluation
Results vs EMSR927, ablation, calibration, cross-event generalization: coming.

## Limitations
Satellite revisit gaps, cloud and radar geometry, OSM incompleteness, small calibration set.
Not a warning system.

## Attribution
See ATTRIBUTION.md.

## License
MIT (code). Data under its respective licenses.
