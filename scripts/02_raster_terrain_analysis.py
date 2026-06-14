"""
02_raster_terrain_analysis.py
=============================

Digital terrain analysis from a DEM.

Workflow
--------
1. Derive slope (degrees), aspect, and hillshade from the DEM.
2. Reclassify slope into buildability classes (0-5, 5-15, 15-30, >30 deg).
3. Compute zonal statistics: mean elevation & mean slope per parcel.
4. Report a developability summary.

Demonstrates: GDAL/native terrain derivatives, raster reclassification with
the raster calculator, zonal statistics joining raster -> vector, and class
breakdown.
"""

import os

from qgis.core import QgsVectorLayer, QgsRasterLayer
from qgis.analysis import QgsZonalStatistics
import processing

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) \
    if "__file__" in globals() else os.getcwd()
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(ROOT, "output")
os.makedirs(OUT, exist_ok=True)

DEM = os.path.join(DATA, "dem.tif")


def main():
    print("== 02 Raster / terrain analysis ==")
    dem = QgsRasterLayer(DEM, "dem")
    if not dem.isValid():
        raise RuntimeError(f"DEM not found: {DEM} (run generate_sample_data.py)")

    # 1) Terrain derivatives.
    slope = processing.run("native:slope",
                           {"INPUT": DEM, "Z_FACTOR": 1.0,
                            "OUTPUT": os.path.join(OUT, "slope.tif")})["OUTPUT"]
    processing.run("native:aspect",
                   {"INPUT": DEM, "Z_FACTOR": 1.0,
                    "OUTPUT": os.path.join(OUT, "aspect.tif")})
    processing.run("native:hillshade",
                   {"INPUT": DEM, "Z_FACTOR": 1.0, "AZIMUTH": 315, "V_ANGLE": 45,
                    "OUTPUT": os.path.join(OUT, "hillshade.tif")})
    print("  derived slope, aspect, hillshade")

    # 2) Reclassify slope into buildability classes.
    #    table = [min, max, class] triples
    table = [
        0, 5, 1,      # gentle    - ideal
        5, 15, 2,     # moderate
        15, 30, 3,    # steep
        30, 9999, 4,  # very steep - constrained
    ]
    reclass = processing.run("native:reclassifybytable", {
        "INPUT_RASTER": slope,
        "RASTER_BAND": 1,
        "TABLE": table,
        "NODATA_FOR_MISSING": True,
        "NO_DATA": 0,
        "RANGE_BOUNDARIES": 1,   # min < value <= max
        "OUTPUT": os.path.join(OUT, "slope_class.tif"),
    })["OUTPUT"]
    print("  reclassified slope into 4 buildability classes")

    # 3) Zonal statistics: mean elevation & slope per parcel.
    parcels = QgsVectorLayer(os.path.join(DATA, "parcels.gpkg"), "parcels", "ogr")
    # Work on a copy so we don't mutate source data.
    parcels = processing.run("native:savefeatures",
                             {"INPUT": parcels,
                              "OUTPUT": os.path.join(OUT, "parcels_terrain.gpkg")})["OUTPUT"]
    parcels = QgsVectorLayer(parcels, "parcels_terrain", "ogr")

    QgsZonalStatistics(parcels, dem, "elev_",
                       1, QgsZonalStatistics.Mean).calculateStatistics(None)
    slope_lyr = QgsRasterLayer(slope, "slope")
    QgsZonalStatistics(parcels, slope_lyr, "slp_",
                       1, QgsZonalStatistics.Mean).calculateStatistics(None)
    print("  computed zonal mean elevation & slope per parcel")

    # 4) Developability summary.
    devable = 0
    total = 0
    for f in parcels.getFeatures():
        total += 1
        mean_slope = f["slp_mean"]
        if mean_slope is not None and mean_slope <= 15:
            devable += 1
    pct = (devable / total * 100) if total else 0
    print(f"\n  Parcels with mean slope <= 15 deg (developable): "
          f"{devable}/{total} ({pct:.1f}%)")
    print(f"  Outputs -> {OUT}")


if __name__ == "__main__" or "__file__" not in globals():
    main()
