# Methodology

The conventions every workflow in this portfolio follows. These are the habits
that separate reproducible production GIS from one-off desktop clicking.

## 1. Coordinate Reference Systems (CRS)

- **Everything is reprojected to a single projected CRS** (`EPSG:32633`, UTM 33N)
  before any measurement. Distances, areas, and buffers are only meaningful in a
  metre-based projected system — never computed in geographic (lat/long) degrees.
- CRS is set **explicitly** on every layer and output. No reliance on
  "on-the-fly" project CRS, which hides mismatches.
- When integrating layers of different CRS, reprojection is an explicit,
  logged step (`native:reprojectlayer`), not an implicit side effect.

## 2. Geometry validation & QA/QC

- Incoming geometry is **never trusted**. Each vector workflow runs
  `native:fixgeometries` (or `ST_MakeValid` in PostGIS) and reports how many
  features were invalid.
- Self-intersections, slivers, and null geometries are the most common cause of
  silently wrong overlay results — catching them up front is non-negotiable.

## 3. Reproducibility

- All analysis runs through the **QGIS Processing framework** (`processing.run`)
  rather than manual menu actions, so every step is scriptable, auditable, and
  re-runnable headless.
- Sample data is **generated deterministically** (fixed random seeds) so results
  are identical on every machine.
- Source data is never mutated in place — workflows operate on copies and write
  to a dedicated `output/` directory.

## 4. Performance

- Spatial indexes (GiST in PostGIS) are created before any spatial join, and
  query plans are verified with `EXPLAIN ANALYZE` to confirm index usage.
- Nearest-neighbour queries use the index-assisted KNN `<->` operator rather
  than a brute-force cross join.
- Raster operations are tiled and compressed (`TILED=YES`, `COMPRESS=DEFLATE`).

## 5. Documentation & deliverables

- Every script has a header docstring stating the workflow, the techniques
  demonstrated, and the inputs/outputs.
- Final cartographic deliverables are produced through scripted print layouts +
  Atlas, so a 50-page map series regenerates with one command when the data
  changes.

## Tool/provider choices

| Need | Provider used | Why |
|---|---|---|
| Vector geoprocessing | `native:*` (QGIS) | Fast, no external deps |
| Raster band math | `gdal:rastercalculator` | Robust, handles nodata |
| Terrain derivatives | `native:slope/aspect/hillshade` | Consistent with DEM units |
| Interpolation | `qgis:idwinterpolation`, `qgis:tininterpolation` | Built-in, parameterized |
| Network routing | `qgis.analysis` graph API | Full control over cost strategy |
| Bulk DB analysis | PostGIS | Set-based, indexed, scales |
