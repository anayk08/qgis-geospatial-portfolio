# Case Study — Multi-Criteria Site Suitability Analysis

A worked example that ties the individual workflows together into the kind of
deliverable a client actually asks for: *"Where are the best candidate sites?"*

## Problem statement

Identify parcels best suited for a new community facility, balancing three
competing criteria:

1. **Buildable terrain** — gentle slopes are cheaper to develop.
2. **Accessibility** — close to existing road/facility network.
3. **Acquisition cost** — lower assessed land value is preferred.

## Data

| Layer | Role | Source workflow |
|---|---|---|
| `parcels` | Analysis units | sample data |
| `dem.tif` | Slope / buildability | [02](../scripts/02_raster_terrain_analysis.py) |
| `facilities` | Accessibility reference | [03](../scripts/03_spatial_join_proximity.py) |
| `value_usd` (attribute) | Cost | sample data |

## Method — weighted overlay

The analysis is a **weighted linear combination** of normalized criteria, the
standard MCDA (multi-criteria decision analysis) approach.

### Step 1 — terrain constraint
From [`02_raster_terrain_analysis.py`](../scripts/02_raster_terrain_analysis.py):
zonal mean slope per parcel. Parcels with mean slope > 30° are **excluded**
outright (hard constraint).

### Step 2 — normalize each criterion to 0–1

| Criterion | Direction | Normalization |
|---|---|---|
| Slope | lower is better | `1 - (slope / max_slope)` |
| Distance to facility | lower is better | `1 - (dist / max_dist)` |
| Land value | lower is better | `1 - (value / max_value)` |

Distance comes from the nearest-facility join in
[`03_spatial_join_proximity.py`](../scripts/03_spatial_join_proximity.py).

### Step 3 — weighted score

```
suitability = 0.40 * slope_score
            + 0.35 * access_score
            + 0.25 * cost_score
```

The custom Processing algorithm in
[`09_batch_processing.py`](../scripts/09_batch_processing.py)
(`SuitabilityScoreAlgorithm`) implements exactly this weighted-and-renormalized
scoring pattern and can be re-run with different weights for sensitivity analysis.

### Step 4 — rank & map

- Sort parcels by `suit_score` descending; take the top decile as candidates.
- Produce a styled suitability map and a per-candidate Atlas page using
  [`08_atlas_cartography.py`](../scripts/08_atlas_cartography.py).

## Sensitivity analysis

Because scoring is parameterized, re-running with weight sets
(e.g. cost-priority `0.2/0.2/0.6` vs. access-priority `0.2/0.6/0.2`) shows how
the recommended sites shift — a key check before presenting a single "answer".

## Outputs

- `parcels_scored.gpkg` — every parcel with its 0–1 suitability score.
- `suitability_map.pdf` — choropleth of scores.
- `service_area_atlas.pdf` — detail page per candidate.

## Why this is defensible

- Every criterion is **explicit, normalized, and weighted transparently**.
- Hard constraints (excessive slope) are separated from soft preferences.
- The whole chain is **reproducible** — change the input data or weights and the
  result regenerates with one command.
- Sensitivity analysis acknowledges that the "best" site depends on stakeholder
  priorities, not just the model.
