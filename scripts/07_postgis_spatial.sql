-- ============================================================================
-- 07_postgis_spatial.sql
-- Spatial SQL in PostGIS -- the database backend behind production QGIS work.
--
-- Demonstrates: schema + spatial index setup, ST_* geometry functions,
-- KNN nearest-neighbour with the <-> operator, spatial joins, CTEs, window
-- functions, and a materialized analysis view ready to load straight into QGIS.
--
-- Run with:  psql -d gisdb -f 07_postgis_spatial.sql
-- Requires:  PostgreSQL 14+, PostGIS 3.x
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS postgis;

-- ----------------------------------------------------------------------------
-- 1. Schema. All geometry stored in EPSG:32633 (UTM 33N, metres) so distances
--    and areas are in metres without on-the-fly transformation.
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS parcels, facilities CASCADE;

CREATE TABLE parcels (
    parcel_id  integer PRIMARY KEY,
    landuse    text,
    value_usd  numeric,
    geom       geometry(Polygon, 32633)
);

CREATE TABLE facilities (
    fac_id  integer PRIMARY KEY,
    type    text,
    geom    geometry(Point, 32633)
);

-- Spatial indexes -- the single most important thing for query performance.
CREATE INDEX parcels_geom_gix    ON parcels    USING GIST (geom);
CREATE INDEX facilities_geom_gix ON facilities USING GIST (geom);

-- (Load data here, e.g. via ogr2ogr from the GeoPackages produced by
--  generate_sample_data.py:
--    ogr2ogr -f PostgreSQL PG:"dbname=gisdb" data/parcels.gpkg \
--            -nln parcels -t_srs EPSG:32633 )

-- ----------------------------------------------------------------------------
-- 2. Data hygiene: never trust incoming geometry. Repair and validate.
-- ----------------------------------------------------------------------------
UPDATE parcels
SET geom = ST_MakeValid(geom)
WHERE NOT ST_IsValid(geom);

-- ----------------------------------------------------------------------------
-- 3. KNN nearest facility per parcel using the <-> index-assisted operator
--    inside a LATERAL join. This is the idiomatic, fast PostGIS pattern.
-- ----------------------------------------------------------------------------
DROP MATERIALIZED VIEW IF EXISTS parcel_accessibility;

CREATE MATERIALIZED VIEW parcel_accessibility AS
SELECT
    p.parcel_id,
    p.landuse,
    p.value_usd,
    ST_Area(p.geom) / 10000.0                       AS area_ha,
    nf.fac_id                                       AS nearest_fac_id,
    nf.type                                         AS nearest_fac_type,
    ROUND(ST_Distance(p.geom, nf.geom)::numeric, 1) AS dist_to_fac_m,
    (ST_Distance(p.geom, nf.geom) > 1500)           AS access_gap,
    p.geom
FROM parcels p
CROSS JOIN LATERAL (
    SELECT f.fac_id, f.type, f.geom
    FROM facilities f
    ORDER BY f.geom <-> p.geom          -- KNN: index-assisted nearest first
    LIMIT 1
) AS nf;

CREATE INDEX parcel_access_gix ON parcel_accessibility USING GIST (geom);

-- ----------------------------------------------------------------------------
-- 4. Aggregate report with a window function: per-landuse stats plus each
--    land use's share of total assessed value.
-- ----------------------------------------------------------------------------
WITH by_landuse AS (
    SELECT
        landuse,
        COUNT(*)                       AS n_parcels,
        ROUND(SUM(area_ha), 2)         AS total_ha,
        SUM(value_usd)                 AS total_value,
        ROUND(AVG(dist_to_fac_m), 1)   AS avg_dist_m,
        COUNT(*) FILTER (WHERE access_gap) AS underserved
    FROM parcel_accessibility
    GROUP BY landuse
)
SELECT
    landuse,
    n_parcels,
    total_ha,
    total_value,
    avg_dist_m,
    underserved,
    ROUND(100.0 * total_value / SUM(total_value) OVER (), 1) AS pct_of_value
FROM by_landuse
ORDER BY total_value DESC;

-- ----------------------------------------------------------------------------
-- 5. Service-area dissolve: 500 m buffer around all facilities, unioned, then
--    the parcels intersecting it. ST_Union dissolves overlapping buffers.
-- ----------------------------------------------------------------------------
DROP MATERIALIZED VIEW IF EXISTS served_parcels;

CREATE MATERIALIZED VIEW served_parcels AS
WITH service_area AS (
    SELECT ST_Union(ST_Buffer(geom, 500)) AS geom
    FROM facilities
)
SELECT p.*
FROM parcels p, service_area s
WHERE ST_Intersects(p.geom, s.geom);

CREATE INDEX served_parcels_gix ON served_parcels USING GIST (geom);

-- ----------------------------------------------------------------------------
-- 6. Performance check: confirm the spatial index is actually used.
--    (EXPLAIN ANALYZE should show an Index Scan on *_geom_gix, not Seq Scan.)
-- ----------------------------------------------------------------------------
-- EXPLAIN ANALYZE
-- SELECT p.parcel_id
-- FROM parcels p
-- JOIN facilities f ON ST_DWithin(p.geom, f.geom, 500);

-- Both materialized views (parcel_accessibility, served_parcels) can now be
-- added directly to a QGIS project via the PostGIS data source connection.
