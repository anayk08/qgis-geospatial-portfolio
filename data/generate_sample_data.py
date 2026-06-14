"""
generate_sample_data.py
=======================

Builds a small, self-contained synthetic dataset so the whole portfolio can be
run without any proprietary or licensed data.

Produces (under ./data/):
    aoi.gpkg            - Area Of Interest polygon (single feature)
    parcels.gpkg        - grid of parcel polygons inside the AOI
    facilities.gpkg     - point layer (e.g. clinics / hydrants / stations)
    samples.gpkg        - point layer with a continuous attribute (for interpolation)
    dem.tif             - synthetic Digital Elevation Model (single band, float32)
    multiband.tif       - synthetic 4-band image (B,G,R,NIR) for NDVI

CRS: EPSG:32633 (WGS 84 / UTM zone 33N) — a projected, metre-based CRS so that
distances, areas and buffers are meaningful.

Runs both inside the QGIS Python Console and headless. Raster generation uses
GDAL + numpy; vector generation uses OGR via osgeo so it works even outside QGIS.
"""

import os
import math
import random

from osgeo import gdal, ogr, osr
import numpy as np

random.seed(42)
np.random.seed(42)

DATA_DIR = os.path.dirname(os.path.abspath(__file__)) \
    if "__file__" in globals() else os.path.join(os.getcwd(), "data")
os.makedirs(DATA_DIR, exist_ok=True)

EPSG = 32633
# AOI extent in projected metres (a 10 km x 8 km block).
XMIN, YMIN, XMAX, YMAX = 500000.0, 5_000_000.0, 510000.0, 5_008_000.0


def _srs():
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(EPSG)
    return srs


def _new_gpkg(path, geom_type, fields):
    """Create a fresh single-layer GeoPackage and return (datasource, layer)."""
    if os.path.exists(path):
        os.remove(path)
    drv = ogr.GetDriverByName("GPKG")
    ds = drv.CreateDataSource(path)
    layer_name = os.path.splitext(os.path.basename(path))[0]
    layer = ds.CreateLayer(layer_name, _srs(), geom_type)
    for name, ftype in fields:
        layer.CreateField(ogr.FieldDefn(name, ftype))
    return ds, layer


def make_aoi():
    path = os.path.join(DATA_DIR, "aoi.gpkg")
    ds, layer = _new_gpkg(path, ogr.wkbPolygon, [("name", ogr.OFTString)])
    ring = ogr.Geometry(ogr.wkbLinearRing)
    for x, y in [(XMIN, YMIN), (XMAX, YMIN), (XMAX, YMAX), (XMIN, YMAX), (XMIN, YMIN)]:
        ring.AddPoint(x, y)
    poly = ogr.Geometry(ogr.wkbPolygon)
    poly.AddGeometry(ring)
    feat = ogr.Feature(layer.GetLayerDefn())
    feat.SetField("name", "Study Area")
    feat.SetGeometry(poly)
    layer.CreateFeature(feat)
    ds = None
    print(f"  aoi.gpkg          -> 1 polygon")
    return path


def make_parcels(rows=8, cols=10):
    path = os.path.join(DATA_DIR, "parcels.gpkg")
    ds, layer = _new_gpkg(
        path, ogr.wkbPolygon,
        [("parcel_id", ogr.OFTInteger),
         ("landuse", ogr.OFTString),
         ("value_usd", ogr.OFTReal)],
    )
    dx = (XMAX - XMIN) / cols
    dy = (YMAX - YMIN) / rows
    landuses = ["residential", "commercial", "industrial", "agricultural", "vacant"]
    pid = 0
    for r in range(rows):
        for c in range(cols):
            x0 = XMIN + c * dx
            y0 = YMIN + r * dy
            ring = ogr.Geometry(ogr.wkbLinearRing)
            for x, y in [(x0, y0), (x0 + dx, y0), (x0 + dx, y0 + dy),
                         (x0, y0 + dy), (x0, y0)]:
                ring.AddPoint(x, y)
            poly = ogr.Geometry(ogr.wkbPolygon)
            poly.AddGeometry(ring)
            feat = ogr.Feature(layer.GetLayerDefn())
            feat.SetField("parcel_id", pid)
            feat.SetField("landuse", random.choice(landuses))
            feat.SetField("value_usd", round(random.uniform(80_000, 1_200_000), 2))
            feat.SetGeometry(poly)
            layer.CreateFeature(feat)
            pid += 1
    ds = None
    print(f"  parcels.gpkg      -> {pid} polygons")
    return path


def _random_points(path, n, fields, value_fn):
    ds, layer = _new_gpkg(path, ogr.wkbPoint, fields)
    defn = layer.GetLayerDefn()
    for i in range(n):
        x = random.uniform(XMIN, XMAX)
        y = random.uniform(YMIN, YMAX)
        pt = ogr.Geometry(ogr.wkbPoint)
        pt.AddPoint(x, y)
        feat = ogr.Feature(defn)
        value_fn(feat, i, x, y)
        feat.SetGeometry(pt)
        layer.CreateFeature(feat)
    ds = None
    return path


def make_facilities(n=15):
    path = os.path.join(DATA_DIR, "facilities.gpkg")
    types = ["clinic", "fire_station", "school", "pump_station"]

    def fill(feat, i, x, y):
        feat.SetField("fac_id", i)
        feat.SetField("type", random.choice(types))

    _random_points(
        path, n,
        [("fac_id", ogr.OFTInteger), ("type", ogr.OFTString)],
        fill,
    )
    print(f"  facilities.gpkg   -> {n} points")
    return path


def make_samples(n=120):
    """Points carrying a smooth-ish continuous variable for interpolation."""
    path = os.path.join(DATA_DIR, "samples.gpkg")
    cx, cy = (XMIN + XMAX) / 2, (YMIN + YMAX) / 2

    def fill(feat, i, x, y):
        # radial gradient + noise -> realistic surface to interpolate
        dist = math.hypot(x - cx, y - cy)
        val = 100.0 - (dist / 100.0) + random.gauss(0, 4)
        feat.SetField("sample_id", i)
        feat.SetField("measure", round(val, 3))

    _random_points(
        path, n,
        [("sample_id", ogr.OFTInteger), ("measure", ogr.OFTReal)],
        fill,
    )
    print(f"  samples.gpkg      -> {n} points")
    return path


def _write_raster(path, array, nbands=1, dtype=gdal.GDT_Float32):
    rows, cols = array.shape[-2], array.shape[-1]
    drv = gdal.GetDriverByName("GTiff")
    out = drv.Create(path, cols, rows, nbands, dtype,
                     options=["COMPRESS=DEFLATE", "TILED=YES"])
    px = (XMAX - XMIN) / cols
    py = (YMAX - YMIN) / rows
    # north-up geotransform
    out.SetGeoTransform((XMIN, px, 0, YMAX, 0, -py))
    out.SetProjection(_srs().ExportToWkt())
    if nbands == 1:
        out.GetRasterBand(1).WriteArray(array)
    else:
        for b in range(nbands):
            out.GetRasterBand(b + 1).WriteArray(array[b])
    out.FlushCache()
    out = None


def make_dem(cols=200, rows=160):
    """Synthetic DEM: two gaussian hills + a regional tilt."""
    xs = np.linspace(0, 1, cols)
    ys = np.linspace(0, 1, rows)
    gx, gy = np.meshgrid(xs, ys)

    def hill(cx, cy, amp, spread):
        return amp * np.exp(-(((gx - cx) ** 2 + (gy - cy) ** 2) / spread))

    dem = (300
           + hill(0.3, 0.35, 450, 0.03)
           + hill(0.7, 0.6, 380, 0.05)
           + 120 * gx)            # regional westeast tilt
    dem += np.random.normal(0, 3, dem.shape)
    _write_raster(os.path.join(DATA_DIR, "dem.tif"), dem.astype(np.float32))
    print(f"  dem.tif           -> {cols}x{rows} float32")


def make_multiband(cols=200, rows=160):
    """4-band (B,G,R,NIR) synthetic image with a vegetated patch (high NIR)."""
    xs = np.linspace(0, 1, cols)
    ys = np.linspace(0, 1, rows)
    gx, gy = np.meshgrid(xs, ys)
    veg_mask = ((gx - 0.4) ** 2 + (gy - 0.5) ** 2) < 0.05

    blue = np.full((rows, cols), 0.10) + np.random.normal(0, 0.01, (rows, cols))
    green = np.full((rows, cols), 0.14) + np.random.normal(0, 0.01, (rows, cols))
    red = np.where(veg_mask, 0.08, 0.22) + np.random.normal(0, 0.01, (rows, cols))
    nir = np.where(veg_mask, 0.55, 0.20) + np.random.normal(0, 0.02, (rows, cols))

    stack = np.clip(np.stack([blue, green, red, nir]), 0, 1).astype(np.float32)
    _write_raster(os.path.join(DATA_DIR, "multiband.tif"), stack,
                  nbands=4, dtype=gdal.GDT_Float32)
    print(f"  multiband.tif     -> {cols}x{rows} x4 (B,G,R,NIR)")


def main():
    print(f"Generating sample data in: {DATA_DIR}")
    print(f"CRS: EPSG:{EPSG} (UTM 33N, metres)\n")
    make_aoi()
    make_parcels()
    make_facilities()
    make_samples()
    make_dem()
    make_multiband()
    print("\nDone. Sample dataset ready.")


if __name__ == "__main__" or "__file__" not in globals():
    main()
