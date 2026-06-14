# GIS & Geospatial Analysis Portfolio — QGIS / PyQGIS

A curated collection of reproducible geospatial workflows demonstrating end-to-end
proficiency in **QGIS 3.x**, **PyQGIS automation**, **PostGIS spatial SQL**, **raster &
remote-sensing analysis**, **network analysis**, **geostatistical interpolation**, and
**production cartography**.

Every workflow is scripted, parameterized, and reproducible — no manual button-clicking
required. Each script runs against synthetic sample data generated locally (see
[`data/generate_sample_data.py`](data/generate_sample_data.py)), so the entire portfolio
can be cloned and executed without proprietary datasets.

---

## Why this portfolio

GIS work is only credible if it is **reproducible, version-controlled, and automated**.
These projects were built the way I run production pipelines:

- Coordinate Reference Systems handled explicitly — never assumed.
- Geometry validity checked and repaired before analysis.
- Processing done through the **QGIS Processing framework** (`processing.run`) so every
  step is auditable and re-runnable headless.
- Outputs are deterministic and documented.

---

## Skill matrix

| Subject area | Demonstrated in | Key techniques |
|---|---|---|
| **Vector analysis & geoprocessing** | [`01_vector_analysis.py`](scripts/01_vector_analysis.py) | Buffers, overlays, dissolve, spatial predicates, attribute-driven selection, geometry repair |
| **Raster & terrain analysis** | [`02_raster_terrain_analysis.py`](scripts/02_raster_terrain_analysis.py) | Slope, aspect, hillshade, reclassification, zonal statistics, raster math |
| **Proximity & spatial joins** | [`03_spatial_join_proximity.py`](scripts/03_spatial_join_proximity.py) | Nearest-neighbour, spatial join by location, distance matrices |
| **Geostatistical interpolation** | [`04_interpolation.py`](scripts/04_interpolation.py) | IDW & TIN interpolation, surface generation, cross-validation |
| **Network analysis** | [`05_network_analysis.py`](scripts/05_network_analysis.py) | Shortest path, service areas / isochrones via QGIS network layer |
| **Remote sensing** | [`06_remote_sensing_ndvi.py`](scripts/06_remote_sensing_ndvi.py) | NDVI, band math, thresholding, vegetation classification |
| **Spatial SQL (PostGIS)** | [`07_postgis_spatial.sql`](scripts/07_postgis_spatial.sql) | Spatial indexing, `ST_*` functions, KNN, window functions, CTEs |
| **Cartography & Atlas** | [`08_atlas_cartography.py`](scripts/08_atlas_cartography.py) | Print layouts, atlas-driven map series, automated PDF export |
| **Batch processing & models** | [`09_batch_processing.py`](scripts/09_batch_processing.py) | Headless batch geoprocessing, custom Processing algorithm |

---

## Repository layout

```
qgis-geospatial-portfolio/
├── README.md
├── requirements.txt
├── data/
│   └── generate_sample_data.py     # builds synthetic AOI, points, DEM, raster bands
├── scripts/
│   ├── 01_vector_analysis.py
│   ├── 02_raster_terrain_analysis.py
│   ├── 03_spatial_join_proximity.py
│   ├── 04_interpolation.py
│   ├── 05_network_analysis.py
│   ├── 06_remote_sensing_ndvi.py
│   ├── 07_postgis_spatial.sql
│   ├── 08_atlas_cartography.py
│   └── 09_batch_processing.py
└── docs/
    ├── methodology.md              # CRS strategy, QA/QC, reproducibility approach
    └── case_study.md               # worked example: site-suitability analysis
```

---

## Running the workflows

These scripts use the PyQGIS API. Run them from the **QGIS Python Console**, or headless
via the QGIS-bundled Python interpreter.

### Option A — QGIS Python Console
1. Open QGIS → *Plugins → Python Console*.
2. Generate sample data:
   ```python
   exec(open(r"data/generate_sample_data.py").read())
   ```
3. Run any workflow:
   ```python
   exec(open(r"scripts/01_vector_analysis.py").read())
   ```

### Option B — Headless (standalone PyQGIS)
On Windows with the OSGeo4W shell:
```bat
python-qgis scripts\01_vector_analysis.py
```
On Linux/macOS, ensure `QGIS` Python bindings are on `PYTHONPATH`, then:
```bash
python3 scripts/01_vector_analysis.py
```

### PostGIS workflow
```bash
psql -d gisdb -f scripts/07_postgis_spatial.sql
```

---

## Tooling

- QGIS 3.28+ (LTR) / PyQGIS
- GDAL/OGR, GRASS & SAGA providers (via Processing)
- PostgreSQL 14+ / PostGIS 3.x
- Python 3.9+

See [`requirements.txt`](requirements.txt) for the analysis environment.

---

## Documentation

- **[Methodology](docs/methodology.md)** — how CRS, data validation, and reproducibility
  are handled across every workflow.
- **[Case study](docs/case_study.md)** — a complete multi-criteria site-suitability
  analysis combining vector, raster, and proximity layers into a weighted overlay.

---

*Author: Anay Kulkarni · QGIS / Geospatial Analyst · anayk08@gmail.com · [LinkedIn](https://www.linkedin.com/in/anay-kulkarni-3569562b3/)*
