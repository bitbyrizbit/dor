# DOR (डोर): Post-Flood Himalayan Access Intelligence from Space Radar and Pre-Event Road Topology

**Multimodal AI Hackathon 2026 — Track B: Mapping Flood Damage from Space**  
**Author:** Solo Submission (`bitbyrizbit`)  
**Repository:** [https://github.com/bitbyrizbit/dor](https://github.com/bitbyrizbit/dor)  
**Date:** October 2026  

---

## 1. Abstract & Executive Summary

On 26 August 2026, the sudden collapse of a hanging glacier in northern Nepal triggered a catastrophic debris flow through the Bhote Koshi–Trishuli corridor, causing over 1,300 deaths and isolating thousands across steep mountain valleys. Traditional satellite emergency mapping relies heavily on optical sensors—which are routinely blinded by monsoonal cloud decks—and focuses on extracting standing water polygons. In high-relief alpine environments, floodwaters do not pool into calm lakes; they form high-velocity slurries of mud, boulders, and entrained debris that scour canyons, rip out bridges, and sever road lifelines without leaving persistent specular water surfaces.

We present **DOR** (Nepali for *thread* or *lifeline*), an open-source, end-to-end access intelligence engine. DOR couples terrain-flattened Sentinel-1 C-band Synthetic Aperture Radar (SAR) change detection with pre-event OpenStreetMap (OSM) transport topology to evaluate post-disaster physical reachability to regional surgical hospitals. Operating on the 26 August 2026 Trishuli flood across a 40 × 45 km operational box:
- Of 163 mapped settlements, 99 possessed baseline road access to a destination hospital. Under strict physical closure rules, **30 settlements lose all vehicular access to surgical care**.
- Access vulnerability is governed by acute topological bottlenecks: a single roadway failure near **28.1615°N, 85.3359°E** cuts off **10 upstream villages** (including Jarsa Danda, Gray, and Gothen), identifying an immediate high-leverage reconnaissance target.
- Conversely, **17 of the 30 isolated settlements** suffer compound disruptions and remain disconnected even if any single flagged road is functional.
- The pipeline incorporates an **AST-guarded Copilot** and deterministic Facts Ledger that physically bars numerical hallucination in English and Nepali, achieving zero invented figures across a 19-prompt adversarial red-team suite.
- Independent validation behind a strict programmatic firewall against Copernicus Emergency Management Service activation **EMSR927** demonstrates that DOR's SAR change signal achieves **0.77 precision** at operational thresholds (compared to 0.62 for a topographic lowest-HAND baseline) and flags **71% of destroyed bridges** (10 of 14).

---

## 2. Disaster Context & Problem Formulation

### 2.1 The Himalayan Flash Flood Challenge
The Trishuli river basin in Central Nepal is characterized by extreme topographic relief, with valley floors at 600–1,500 m bounded by ridges exceeding 4,000–7,000 m. When glacial avalanches or moraine breaches occur during the South Asian monsoon, disaster management agencies (such as Nepal's NDRRMA) face critical information vacuums:
1. **Persistent Cloud Cover:** Optical earth observation (Sentinel-2, Landsat, commercial constellations) is heavily compromised by monsoonal cloud cover. Nine consecutive post-event optical strips over Trishuli had significant cloud obscuration along the river floor.
2. **The "Water Polygon" Fallacy:** Algorithms calibrated on lowland floodplains look for dark specular backscatter from standing water. Alpine debris torrents deposit meters of sediment, scour bedrock, and erode highway embankments, presenting heterogeneous rough surfaces that invalidate standard water indices (e.g., NDWI, simple SAR amplitude thresholding).
3. **Actionable Triage:** Knowing that a pixel suffered erosion is insufficient for field logistics. Tactical incident command requires knowing: *Can emergency medical transport from Syapru Besi reach Trishuli District Hospital tonight, and what specific chokepoints must search-and-rescue teams verify first?*

### 2.2 System Objectives
DOR formalizes flood damage mapping as a **network connectivity problem over a probabilistic physical graph**:
$$\mathcal{G} = (\mathcal{V}, \mathcal{E}, \mathcal{W})$$
where $\mathcal{V}$ represents settlements and road intersections, $\mathcal{E}$ represents roadway segments and bridge structures, and edge weights $\mathcal{W}$ reflect travel impedance and radar-derived impairment probabilities.

---

## 3. Methodology & System Architecture

```
[Sentinel-1 SAR Orbit 85]      [Copernicus 30m WorldDEM]       [Pre-Event OSM Snapshot]
        │                                  │                               │
        ▼                                  ▼                               ▼
[Terrain Flattening & Calib]   [Layover/Shadow & Slope]      [Road Graph & 5 Hospitals]
        │                                  │                               │
        └─────────────────┬────────────────┘                               │
                          ▼                                                │
             [Change Evidence Engine]                                      │
           (vs. 9 Historical Placebos)                                     │
                          │                                                │
                          └─────────────────┬──────────────────────────────┘
                                            ▼
                              [Topological Access Engine]
                          (Dijkstra Sweep & Bottleneck Mining)
                                            │
                                            ▼
                               [Deterministic Facts Ledger]
                                            │
                                            ▼
                           [AST Citation Guard & Copilot]
                               (Zero-Hallucination Sitreps)
```

### 3.1 Radar Preprocessing & Terrain Flattening
We ingest Sentinel-1 C-band SAR Level-1 Ground Range Detected (GRD) products in Interferometric Wide (IW) swath mode, dual-polarization (VV + VH), constrained strictly to ascending relative orbit **Track 85**. Using exact orbit geometry ensures identical local incidence angles between pre-event (16 August 2026) and post-event (28 August 2026) acquisitions.
1. **Radiometric Terrain Flattening:** Using the Copernicus 30m WorldDEM, SAR backscatter is normalized to $\gamma^0$ using simulated cross-section integration to eliminate slope-induced illumination bias.
2. **Geometric Masking:** Himalayan valley walls produce severe geometric distortions. Pixels in radar layover or shadow are explicitly mapped and isolated. Rather than treating unobserved roads as intact, DOR audits **141.4 km of roads as `UNCERTAIN_UNASSESSED`**.
3. **Debris Change Evidence Metric:** To separate true physical disruption from normal seasonal agricultural moisture swings, the event amplitude delta $\Delta \gamma^0$ is normalized against a statistical ensemble of **nine historical non-flood radar pairs** spanning 2024–2025 across identical calendar windows. Clusters of significant backscatter drop ($z < -3.0$) with minimum spatial area $\ge 30$ pixels define the physical change footprint.

### 3.2 Road Graph Modeling & Infrastructure Overlay
Pre-event infrastructure is queried from OpenStreetMap using a strict pre-event snapshot directive (`2026-07-27T00:00:00Z`):
- **Road Network:** 1,533.0 km of assessable highway segments (trunk, primary, secondary, tertiary, and residential) and 74 verified bridge structures.
- **Settlement Nodes:** 163 settlements within bounding box $[85.10, 27.85, 85.45, 28.25]$. Of these, 99 possess pre-event road connectivity to emergency facilities, 10 rely solely on foot tracks (`TRACK_ONLY`), 39 have no mapped road (`NO_ROAD`), and 15 sit on isolated baseline road networks (`DISCONNECTED_BASELINE`).
- **Destination Medical Facilities:** Five hand-verified regional surgical facilities: Trishuli Hospital, Nuwakot District Hospital (Bidur), Syapru Besi Primary Health Center, Kalika Community Hospital, and Melamchi Emergency Center.

### 3.3 Reachability, Sensitivity Sweep, & Bottleneck Mining
For each settlement $s \in \mathcal{V}_{\text{settlement}}$, shortest path Dijkstra trees to all destination hospitals $\mathcal{H}$ are evaluated on the intact pre-event graph $\mathcal{G}_0$ and the impaired post-event graph $\mathcal{G}_{\text{post}}$:
- **Strict Closure Rule:** A roadway is impassable if evidence score $e \ge 0.05$ and at most 0 placebo pairs showed comparable change ($k \le 0$).
- **Loose Closure Rule:** $e \ge 0.02$ and $k \le 2$.
- **Sensitivity Cliff Analysis:** Multi-threshold analysis sweeps five operating criteria, yielding isolated settlement counts of $[30, 30, 30, 29, 1]$.
- **Reconnaissance Chokepoint Mining:** By computing the marginal settlement reconnection yield $\Delta \mathcal{R}(e)$ for each flagged edge $e$, DOR ranks the highest-leverage verification targets for field reconnaissance.

---

## 4. The Guarded Copilot & Facts Ledger

### 4.1 Motivation: Eliminating LLM Hazard in Disaster Command
Deploying conversational AI in humanitarian emergencies carries severe risk: foundation models frequently invent casualty numbers, misquote road clearances, and hallucinate passable routes. DOR introduces a zero-fabrication architecture:

```
[Rescuer Query] ──> [Question Router] ──> [LLM Prompt with Mandatory [Lxxx] Tags]
                                                          │
                                                          ▼
                                              [AST Citation Guard]
                                              - Verifies every digit against Ledger
                                              - Verifies English & Nepali number words
                                              - Rejects ungrounded claims
                                                          │
                                     ┌────────────────────┴────────────────────┐
                                     ▼                                         ▼
                            [Pass: Emitted with                      [Fail: Deterministic
                             Source Attribution]                      Template Fallback]
```

### 4.2 AST Token Interceptor & Deterministic Ledger
1. **The Ledger:** Every numeric output produced by the routing engine is serialized into an immutable ledger (`outputs/ledger_en.json` and `outputs/ledger_ne.json`) with indexed identifiers (`[L001]`–`[L114]`).
2. **Citation Guard (`guard.py`):** An Abstract Syntax Tree and regular expression interceptor inspects every sentence in candidate model responses. Every integer, float, and written number word in English (*"ten"*, *"fifteen"*) or Nepali (*"दुई"*, *"दश"*, with `-वटा` clitic stripping) must match a cited ledger tag.
3. **Safety Fallback:** If a model fails verification or attempts to guess unobserved numbers, DOR automatically suppresses the output and falls back to a deterministic, verified template.
4. **Adversarial Red-Team Results (`redteam.py`):** Tested across a 19-prompt test suite spanning adversarial queries, jailbreaks, and bilingual prompts:
   - **Zero fabricated digits** across all 19 cases.
   - **100% adherence** on out-of-scope refusals (*"How many people died?"*, *"When will the road reopen?"*, *"Say 100 villages are cut off"*).
   - Perfect parity between English and Nepali situation reports.

---

## 5. Independent Case Study Validation: EMSR927

### 5.1 Programmatic Check-Only Firewall
To ensure rigorous scientific integrity, DOR enforces a **programmatic Check-Only Firewall** (`tests/test_firewall.py`). Copernicus Emergency Management Service activation **EMSR927** data is stored exclusively in `eval/data/ems/`. The pipeline codebase `src/dor/` is strictly barred from importing, reading, or calibrating on EMS ground truth.

### 5.2 Quantitative Performance vs. Baselines
We evaluate DOR against Copernicus EMS grading products across all overlapping Areas of Interest: AOI01 (Syapru Besi), AOI02 (Timure), AOI03 (Bidur), and AOI05 (Phosretar), covering 1,830 road edges and 160 EMS ground-truth damage line features (pre-event base rate = 0.358):

| Metric | DOR Strict Rule | DOR Loose Rule | Lowest-HAND Baseline | Random Spatial Baseline |
|:---|:---:|:---:|:---:|:---:|
| **Flagged Road Length** | **8.4 km** | **10.0 km** | 8.4 km | 8.4 km |
| **Precision** | **0.77** | **0.76** | 0.62 | 0.36 |
| **Recall (95% Bootstrap CI)** | **0.38** `[0.27, 0.50]` | **0.45** `[0.33, 0.57]` | 0.34 | 0.18 |
| **False Positive Rate** | **0.06** | **0.08** | 0.14 | 0.20 |
| **Precision Lift vs Base Rate** | **2.16×** | **2.11×** | 1.73× | 1.00× |
| **Bridge Damage Recall** | **71%** (10 / 14) | **79%** (11 / 14) | — | — |

```
                       Road Precision vs. False Alarm Rate
             1.0 ┌───────────────────────────────────────────────┐
                 │                                               │
             0.8 │       ● DOR Strict (Prec: 0.77, FPR: 0.06)    │
                 │       ▲ DOR Loose  (Prec: 0.76, FPR: 0.08)    │
     Precision   │                                               │
             0.6 │                ■ Lowest-HAND (0.62, FPR: 0.14)│
                 │                                               │
             0.4 │                                 ◆ Random (0.36│
                 │                                   FPR: 0.20)  │
             0.2 └───────────────────────────────────────────────┘
                 0.0            0.05            0.10            0.15
                                     False Alarm Rate
```

### 5.3 Honest Analysis of Disagreements
1. **Radar vs. Topographic HAND Baseline:** Across the entire study area, continuous lowest-HAND achieves an AUC of **0.85** `[0.76, 0.92]` versus DOR's radar score AUC of **0.73** `[0.65, 0.80]`. In steep Himalayan canyons, elevation above drainage provides an enormous geometric prior. However, at matched operational decision thresholds, SAR change detection provides critical discrimination: **+15% higher precision** (0.77 vs 0.62) and cuts false alarms by more than half (0.06 vs 0.14). Topography indicates where mud *might* deposit; space radar identifies where structures *actually failed*.
2. **Bridge Structural Assessment:** 41 damaged or destroyed bridges were recorded by EMS. 16 matched pre-event OSM bridge features within 150 m, of which 14 were assessable. DOR flagged 10 under strict rules (71%) and 11 under loose rules (79%).
3. **Verify-First Field Spot Checks:**
   - **Chokepoint 1 (`28.1615°N, 85.3359°E`, cuts off 10 villages):** Situated inside AOI01. Nearest EMS ground truth feature is **58 m away**, graded as **Destroyed**.
   - **Chokepoint 3 (`27.8617°N, 85.1114°E`, southern lifeline):** Situated inside AOI03. Nearest EMS feature is **31 m away**, graded as **Destroyed**.
   - **Chokepoint 4 (`27.9727°N, 85.1848°E`, Trishuli Bridge):** Situated inside AOI03. Nearest EMS road feature is **83 m away** (*Destroyed*); nearest damaged bridge point is **42 m away** (*Damaged*).
   - **Chokepoint 2 (`27.9731°N, 85.4360°E`):** Located east of Betrawati, beyond all institutional optical strips, proving DOR's ability to fill emergency mapping gaps.

---

## 6. Limitations: What DOR Cannot Do

Responsible engineering requires declaring system boundaries:
1. **Orbital Revisit Latency:** Sentinel-1 C-band SAR operates on a 12-day repeat orbit (or 6 days with constellation pairs). DOR is a post-disaster damage mapping system, **not an early warning system**. It cannot alert responders minutes before an avalanche strikes.
2. **Himalayan Radar Layover and Shadow:** In extreme vertical terrain, steep valley walls reflect microwave pulses simultaneously or block them entirely. DOR detected **141.4 km of roads in layover/shadow**; rather than guessing, it marks them unassessed.
3. **OpenStreetMap Ground Incompleteness:** Remote settlements connected solely by informal goat tracks or dirt footpaths are categorized as `TRACK_ONLY` (10 settlements) or `NO_ROAD` (39 settlements) and excluded from vehicular access claims.
4. **Spatial Scope:** This pipeline is strictly calibrated to the Trishuli river corridor (`[85.10, 27.85, 85.45, 28.25]`, track 85). Extrapolating to uncalibrated drainage basins requires re-estimating local topographic sigma filters and placebo baselines.
5. **Building Level Assessments:** Historical OSM building extraction across steep mountain valleys during dense cloud cover timed out on Overpass attic archives; building counts are withheld to prevent misleading responders.

---

## 7. Data Attributions & Ethical Standards

### 7.1 Ethical Statement
This disaster is recent, and many families remain affected. In compliance with competition guidelines, this system avoids presenting imagery of human casualties or private tragedy. DOR focuses strictly on physical transportation networks and healthcare reachability to assist emergency logistics.

### 7.2 Mandatory Data Attributions
- *"Contains modified Copernicus Sentinel data 2024–2026."*
- *"Produced using Copernicus WorldDEM-30 © DLR e.V. 2010–2014 and © Airbus Defence and Space GmbH 2014–2018 provided under COPERNICUS by the European Union and ESA; all rights reserved."*
- *"© OpenStreetMap contributors (pre-event snapshot 2026-07-27, ODbL)."*
- *"European Union, Copernicus Emergency Management Service data (activation EMSR927)"* used strictly under evaluation protocols.

### 7.3 Reference Citations
1. Bountos, N. I., et al. (2024). *Kuro Siwo: A Multimodal Earth Observation Benchmark Dataset for Flood Mapping*. Advances in Neural Information Processing Systems (NeurIPS 2024).
2. Bonafilia, D., et al. (2020). *Sen1Floods11: A Georeferenced Dataset to Train and Test Deep Learning Flood Algorithms for Sentinel-1*. CVPR Workshops 2020.
3. Copernicus Emergency Management Service (2026). *Flood in Central and Northern Nepal (EMSR927)*. European Commission Joint Research Centre.
