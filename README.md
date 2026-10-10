# DOR (डोर)

**What still connects?**

*dor* means thread in Nepali. A flood cuts threads. DOR finds the ones still holding.

DOR evaluates post-flood physical access from mountain settlements to destination hospitals following the 2026 Trishuli basin disaster. Instead of drawing a passive flood extent polygon or estimating inundation depth, DOR models post-event network connectivity: it combines Sentinel-1 SAR change detection with pre-event OpenStreetMap infrastructure, accounts for radar blind spots (shadow and layover), and isolates the bottleneck road and bridge failures that govern access for cut-off communities.

Built for the Multimodal AI Hackathon 2026, Track B (*Mapping Flood Damage from Space*). Educational prototype, not an operational decision tool.

---

## Key Findings

- **30 settlements cut off:** Of 163 settlements surveyed in the Trishuli corridor, 99 had mapped road access to a destination hospital prior to the event. Under the strict closure rule, **30 settlements lose all road access** to any destination hospital.
- **The critical bottleneck:** Isolation is dominated by single-point bottlenecks. One road segment near **28.1615°N, 85.3359°E** cuts off **10 settlements** (including Jarsa Danda, Gray, and Gothen). Reopening this single point would reconnect all 10.
- **Structural isolation:** Conversely, **17 of the 30 cut-off settlements** have compound failures and remain cut off even if any single flagged road or bridge is confirmed open.
- **Sensitivity cliff:** Across 5 closure rules (from loose to strict), isolated settlement counts are **30, 30, 30, 29, 1**.
- **Unassessed uncertainty:** 38 settlements depend on roads that could not be evaluated due to radar shadow, layover, or lack of radar coverage.
- **Road & bridge damage:** 27.4 km (strict) and 34.2 km (loose) of 1,533.0 km assessable road are flagged. 13 of 74 assessable bridge structures are flagged strict.

---

## Independent Validation against Copernicus EMS (EMSR927)

DOR was independently validated against Copernicus Emergency Management Service activation EMSR927 (check-only firewall; EMS data is never seen during processing).

| Metric | DOR Strict | DOR Loose | Lowest-HAND Baseline | Random Baseline |
|---|---|---|---|---|
| **Road Flagged (km)** | 8.4 km | 10.0 km | 8.4 km | 8.4 km |
| **Precision** | **0.77** | **0.76** | 0.62 | 0.36 |
| **Recall (95% CI)** | **0.38** [0.27, 0.50] | **0.45** [0.33, 0.57] | 0.34 | 0.18 |
| **False Positive Rate** | 0.06 | 0.08 | 0.14 | 0.20 |
| **Lift vs Prior** | 2.16× | 2.11× | 1.73× | 1.00× |
| **Bridge Recall** | **71%** (10 / 14) | **79%** (11 / 14) | — | — |

- **Operating Point Advantage:** At equivalent flagged road lengths, SAR change detection achieves 77% precision compared to 62% for lowest-HAND topographic baselines.
- **Continuous Rank-Order AUC:** Continuous lowest-HAND AUC is 0.85 [0.76, 0.92] vs DOR radar score AUC of 0.73 [0.65, 0.80], reflecting the strong prior that flood debris settles in valley floors, while radar discriminates actual structural changes along those corridors.
- **Verify-First Ground Check:**
  - Segment 1 (`28.1615°N, 85.3359°E`, 10 settlements): EMS recorded road *Destroyed* within 58 m.
  - Segment 3 (`27.8617°N, 85.1114°E`, 1 settlement): EMS recorded road *Destroyed* within 31 m.
  - Bridge 4 (`27.9727°N, 85.1848°E`, 1 settlement): EMS recorded road *Destroyed* within 83 m and bridge *Damaged* within 42 m.

---

## Guarded Copilot & Facts Ledger

DOR includes an interactive copilot that translates routing facts into English and Nepali situational reports.

- **Guarded Numbers:** An AST-level citation guard verifies that every number and number word emitted matches a recorded entry in `outputs/ledger_en.json` and `outputs/ledger_ne.json`. If a model output fails verification, it automatically falls back to verified canned templates.
- **Zero Fabricated Digits:** Evaluated on a 19-prompt red-team suite (`scripts/redteam.py`), achieving zero invented numbers and 100% adherence on out-of-scope refusal queries.
- **Bilingual Parity:** English and Nepali situation reports share identical underlying numeric values verified by the ledger.

---

## Repository Structure

```
dor/
├── configs/               # Corridor bounding box and destination hospitals
├── src/dor/
│   ├── acquire/           # Sentinel-1 STAC search and pair discovery
│   ├── dem/               # Terrain correction and shadow/layover masks
│   ├── roads/             # Pre-event OSM highway network extraction
│   ├── evidence/          # SAR change score computation
│   ├── access/            # Shortest-path reachability and Monte Carlo sweep
│   └── copilot/           # Facts ledger, AST citation guard, report generators
├── eval/dor_eval/         # Check-only EMS comparison script (firewalled from pipeline)
├── scripts/
│   ├── run_all.py         # Full reproduction pipeline
│   ├── score_maps.py      # Spatial evidence raster and placebo evaluation
│   ├── build_dashboard.py # Self-contained HTML interactive map & dashboard
│   ├── make_report.py     # Bilingual sitrep generation & manifest
│   ├── make_figures.py    # Figure generation (placebo, sensitivity)
│   ├── serve.py           # Dashboard local webserver with live Q&A API
│   └── redteam.py         # 19-prompt safety and fidelity test suite
└── outputs/               # Visualizations, dashboards, sitreps, and evaluation metrics
```

---

## Reproduction & Usage

### 1. Installation

```bash
git clone https://github.com/bitbyrizbit/dor.git
cd dor
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

pip install -e .
pip install -r requirements.txt
```

### 2. Run Tests

```bash
python -m pytest
```

### 3. Generate Reports & Dashboard

```bash
python scripts/score_maps.py
python scripts/make_figures.py
python scripts/make_report.py
python scripts/build_dashboard.py
```

Open `outputs/dashboard.html` in any browser to explore the interactive Leaflet map, evidence footprint layer, and verified settlement isolation statuses.

### 4. Interactive Copilot Server

```bash
python scripts/serve.py
```
Visit `http://localhost:8000` to interact with the map and ask free-form access queries.

---

## Limitations

1. **Revisit Cadence:** Sentinel-1 C-band SAR provides snapshots every 6–12 days; real-time event monitoring is impossible without higher-frequency SAR constellations.
2. **Topographic Layover & Shadow:** In high-relief Himalaya terrain, 141.4 km of roads could not be observed and are explicitly catalogued as unassessed rather than safe.
3. **OSM Completeness:** Only mapped roads and settlements are judged; unmapped hamlets or foot tracks are explicitly tracked as unassessed.
4. **Scope:** Configured specifically for the upper and middle Trishuli basin (`[85.10, 27.85, 85.45, 28.25]`, track 85).

---

## Data Attribution & Ethics

- Contains modified Copernicus Sentinel data (2024–2026), ESA.
- Copernicus WorldDEM-30 © DLR e.V. 2010–2014 and Airbus Defence and Space GmbH 2014–2018.
- OpenStreetMap contributors (pre-event snapshot, ODbL).
- Copernicus Emergency Management Service EMSR927 data used strictly for validation.
