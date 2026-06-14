"""
03_spatial_join_proximity.py
============================

Proximity analysis and spatial joins.

Workflow
--------
1. For each parcel centroid, find the nearest facility and the distance to it.
2. Spatially join the facility type onto each parcel.
3. Flag parcels beyond an accessibility threshold (e.g. > 1500 m from any facility).

Demonstrates: centroid extraction, nearest-neighbour join (KNN), distance
attribution, join-by-nearest, and accessibility gap detection.
"""

import os

from qgis.core import QgsVectorLayer
import processing

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) \
    if "__file__" in globals() else os.getcwd()
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(ROOT, "output")
os.makedirs(OUT, exist_ok=True)

THRESHOLD_M = 1500.0


def main():
    print("== 03 Spatial join & proximity ==")
    parcels = QgsVectorLayer(os.path.join(DATA, "parcels.gpkg"), "parcels", "ogr")
    facilities = QgsVectorLayer(os.path.join(DATA, "facilities.gpkg"),
                                "facilities", "ogr")

    # 1) Parcel centroids (point-to-point distance is unambiguous).
    centroids = processing.run("native:centroids",
                               {"INPUT": parcels, "ALL_PARTS": False,
                                "OUTPUT": "memory:"})["OUTPUT"]

    # 2) Nearest facility + distance for every centroid.
    joined = processing.run("native:joinbynearest", {
        "INPUT": centroids,
        "INPUT_2": facilities,
        "FIELDS_TO_COPY": ["type", "fac_id"],
        "DISCARD_NONMATCHING": False,
        "PREFIX": "near_",
        "NEIGHBORS": 1,
        "MAX_DISTANCE": None,
        "OUTPUT": os.path.join(OUT, "parcels_nearest_facility.gpkg"),
    })["OUTPUT"]
    joined = QgsVectorLayer(joined, "joined", "ogr")
    print(f"  joined nearest facility to {joined.featureCount()} parcel centroids")

    # 3) Accessibility gap analysis.
    #    joinbynearest writes the distance into a 'distance' field.
    dist_field = "distance"
    dists = [f[dist_field] for f in joined.getFeatures() if f[dist_field] is not None]
    underserved = [d for d in dists if d > THRESHOLD_M]
    by_type = {}
    for f in joined.getFeatures():
        t = f["near_type"]
        by_type[t] = by_type.get(t, 0) + 1

    if dists:
        print(f"\n  Distance to nearest facility (m):")
        print(f"    min  {min(dists):8.1f}")
        print(f"    mean {sum(dists)/len(dists):8.1f}")
        print(f"    max  {max(dists):8.1f}")
    print(f"\n  Parcels beyond {THRESHOLD_M:.0f} m (accessibility gap): "
          f"{len(underserved)}/{len(dists)}")
    print("\n  Nearest-facility type distribution:")
    for t, n in sorted(by_type.items()):
        print(f"    {t:<14}{n:>4}")
    print(f"\n  Output -> {os.path.join(OUT, 'parcels_nearest_facility.gpkg')}")


if __name__ == "__main__" or "__file__" not in globals():
    main()
