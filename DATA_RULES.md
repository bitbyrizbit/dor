# Data rules

Allowed as pipeline inputs:
- Sentinel-1 and Sentinel-2 (Copernicus Data Space)
- Copernicus DEM
- OpenStreetMap, pre-event snapshot via ohsome API (snapshot date must be before the event)
- Training datasets: Kuro Siwo, Sen1Floods11

Forbidden as pipeline inputs (check-only, under eval/ only):
- Copernicus EMS (including EMSR927), UNOSAT, any published damage map
- OpenStreetMap edits made after the event

Enforcement:
- src/dor must never import dor_eval or read eval/ paths
- tests/test_firewall.py fails CI on violation
- every run writes a manifest listing all input sources and snapshot dates
