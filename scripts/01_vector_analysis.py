"""
01_vector_analysis.py
=====================

Core vector geoprocessing through the QGIS Processing framework.

Workflow
--------
1. Load AOI, parcels, and facilities.
2. Validate & repair geometries (a non-negotiable first step in production work).
3. Reproject everything to a common projected CRS.
4. Build 500 m service buffers around facilities, then dissolve them.
5. Select parcels that intersect the buffered service area (spatial predicate).
6. Compute area (m2 / ha) and a derived value-density attribute.
7. Export the result and print a QA summary.

Demonstrates: CRS management, geometry validity QA, buffering, dissolve,
overlay/clip, spatial selection by predicate, attribute calculation, and
auditable Processing-based steps.
"""

import os

from qgis.core import (
    QgsVectorLayer, QgsProject, QgsCoordinateReferenceSystem,
    QgsField, QgsFeatureRequest, edit,
)
from qgis.PyQt.QtCore import QVariant
import processing

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) \
    if "__file__" in globals() else os.getcwd()
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(ROOT, "output")
os.makedirs(OUT, exist_ok=True)

TARGET_CRS = "EPSG:32633"
SERVICE_RADIUS_M = 500.0


def load(name):
    path = os.path.join(DATA, f"{name}.gpkg")
    lyr = QgsVectorLayer(path, name, "ogr")
    if not lyr.isValid():
        raise RuntimeError(f"Failed to load {path}")
    return lyr


def fix_geometries(layer, label):
    """Repair invalid geometries; report how many were affected."""
    invalid = sum(1 for f in layer.getFeatures() if not f.geometry().isGeosValid())
    res = processing.run("native:fixgeometries",
                         {"INPUT": layer, "OUTPUT": "memory:"})
    print(f"  [{label}] repaired {invalid} invalid geometr"
          f"{'y' if invalid == 1 else 'ies'}")
    return res["OUTPUT"]


def reproject(layer, label):
    res = processing.run("native:reprojectlayer", {
        "INPUT": layer,
        "TARGET_CRS": QgsCoordinateReferenceSystem(TARGET_CRS),
        "OUTPUT": "memory:",
    })
    out = res["OUTPUT"]
    print(f"  [{label}] reprojected -> {TARGET_CRS}")
    return out


def main():
    print("== 01 Vector analysis ==")
    aoi = reproject(fix_geometries(load("aoi"), "aoi"), "aoi")
    parcels = reproject(fix_geometries(load("parcels"), "parcels"), "parcels")
    facilities = reproject(load("facilities"), "facilities")

    # 1) Service buffers around facilities, then dissolve to a single area.
    buffered = processing.run("native:buffer", {
        "INPUT": facilities,
        "DISTANCE": SERVICE_RADIUS_M,
        "SEGMENTS": 16,
        "DISSOLVE": True,
        "OUTPUT": "memory:",
    })["OUTPUT"]
    print(f"  built & dissolved {SERVICE_RADIUS_M:.0f} m service buffers")

    # 2) Clip the service area to the AOI so we never analyse outside scope.
    service_area = processing.run("native:clip", {
        "INPUT": buffered, "OVERLAY": aoi, "OUTPUT": "memory:",
    })["OUTPUT"]

    # 3) Select parcels intersecting the service area (predicate = intersects).
    served = processing.run("native:extractbylocation", {
        "INPUT": parcels,
        "PREDICATE": [0],           # 0 = intersects
        "INTERSECT": service_area,
        "OUTPUT": "memory:",
    })["OUTPUT"]
    print(f"  parcels within service area: {served.featureCount()} "
          f"of {parcels.featureCount()}")

    # 4) Add area + value-density attributes.
    with edit(served):
        served.dataProvider().addAttributes([
            QgsField("area_ha", QVariant.Double),
            QgsField("val_per_ha", QVariant.Double),
        ])
        served.updateFields()
        idx_ha = served.fields().indexOf("area_ha")
        idx_vph = served.fields().indexOf("val_per_ha")
        idx_val = served.fields().indexOf("value_usd")
        for f in served.getFeatures():
            area_ha = f.geometry().area() / 10_000.0
            val = f[idx_val] or 0.0
            served.changeAttributeValue(f.id(), idx_ha, round(area_ha, 4))
            served.changeAttributeValue(
                f.id(), idx_vph, round(val / area_ha, 2) if area_ha else 0.0)

    # 5) Persist result.
    out_path = os.path.join(OUT, "served_parcels.gpkg")
    processing.run("native:savefeatures",
                   {"INPUT": served, "OUTPUT": out_path})

    # 6) QA summary by land use.
    summary = {}
    for f in served.getFeatures():
        lu = f["landuse"]
        rec = summary.setdefault(lu, {"n": 0, "ha": 0.0, "val": 0.0})
        rec["n"] += 1
        rec["ha"] += f["area_ha"] or 0.0
        rec["val"] += f["value_usd"] or 0.0
    print("\n  Served parcels by land use:")
    print(f"  {'landuse':<14}{'count':>7}{'area_ha':>12}{'value_usd':>16}")
    for lu, r in sorted(summary.items()):
        print(f"  {lu:<14}{r['n']:>7}{r['ha']:>12.2f}{r['val']:>16,.0f}")

    print(f"\n  Output -> {out_path}")


if __name__ == "__main__" or "__file__" not in globals():
    main()
