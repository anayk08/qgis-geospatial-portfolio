"""
04_interpolation.py
===================

Geostatistical surface generation from point samples.

Workflow
--------
1. Interpolate the `measure` attribute of the sample points to a continuous
   raster surface using Inverse Distance Weighting (IDW).
2. Also produce a TIN interpolation for comparison.
3. Run a simple leave-some-out cross-validation to report interpolation error.

Demonstrates: IDW & TIN interpolation, surface extent/resolution control, and
quantitative accuracy assessment (RMSE / MAE) via holdout cross-validation.
"""

import os
import math
import random

from qgis.core import QgsVectorLayer, QgsRasterLayer
import processing

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) \
    if "__file__" in globals() else os.getcwd()
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(ROOT, "output")
os.makedirs(OUT, exist_ok=True)

random.seed(7)
PIXEL = 50.0  # output resolution in metres


def _interp_field_spec(layer, field):
    """Build the 'data' string IDW/TIN interpolation expects:
       layer_source::~::band::~::field_index::~::type"""
    fidx = layer.fields().indexOf(field)
    return f"{layer.source()}::~::0::~::{fidx}::~::0"


def idw(layer, field, extent, out_path):
    res = processing.run("qgis:idwinterpolation", {
        "INTERPOLATION_DATA": _interp_field_spec(layer, field),
        "DISTANCE_COEFFICIENT": 2.0,
        "EXTENT": extent,
        "PIXEL_SIZE": PIXEL,
        "OUTPUT": out_path,
    })
    return res["OUTPUT"]


def tin(layer, field, extent, out_path):
    res = processing.run("qgis:tininterpolation", {
        "INTERPOLATION_DATA": _interp_field_spec(layer, field),
        "METHOD": 0,            # linear
        "EXTENT": extent,
        "PIXEL_SIZE": PIXEL,
        "OUTPUT": out_path,
    })
    return res["OUTPUT"]


def sample_raster(raster_path, x, y):
    lyr = QgsRasterLayer(raster_path, "tmp")
    val, ok = lyr.dataProvider().sample(_pt(x, y), 1)
    return val if ok else None


def _pt(x, y):
    from qgis.core import QgsPointXY
    return QgsPointXY(x, y)


def cross_validate(points, field):
    """Leave-10%-out: interpolate from the rest, predict held-out points."""
    feats = []
    ids = []
    for f in points.getFeatures():
        feats.append((f.geometry().asPoint(), f[field]))
        ids.append(f.id())

    holdout = random.sample(range(len(feats)), max(1, len(feats) // 10))
    hold_ids = {ids[i] for i in holdout}

    # Build the training subset (everything not held out) and interpolate from it.
    expr = "$id NOT IN (" + ",".join(str(i) for i in hold_ids) + ")"
    train = processing.run("native:extractbyexpression",
                           {"INPUT": points, "EXPRESSION": expr,
                            "OUTPUT": os.path.join(OUT, "_cv_train.gpkg")})["OUTPUT"]
    train_lyr = QgsVectorLayer(train, "train", "ogr")

    ext = points.extent()
    extent_str = f"{ext.xMinimum()},{ext.xMaximum()},{ext.yMinimum()},{ext.yMaximum()}"
    surf = idw(train_lyr, field, extent_str, os.path.join(OUT, "_cv_idw.tif"))

    errs = []
    for i in holdout:
        (x, y), actual = feats[i]
        pred = sample_raster(surf, x, y)
        if pred is not None and actual is not None:
            errs.append(pred - actual)
    if not errs:
        return None
    rmse = math.sqrt(sum(e * e for e in errs) / len(errs))
    mae = sum(abs(e) for e in errs) / len(errs)
    return rmse, mae, len(errs)


def main():
    print("== 04 Interpolation ==")
    pts = QgsVectorLayer(os.path.join(DATA, "samples.gpkg"), "samples", "ogr")
    if not pts.isValid():
        raise RuntimeError("samples.gpkg missing (run generate_sample_data.py)")

    ext = pts.extent()
    extent_str = f"{ext.xMinimum()},{ext.xMaximum()},{ext.yMinimum()},{ext.yMaximum()}"

    idw_out = idw(pts, "measure", extent_str, os.path.join(OUT, "idw_surface.tif"))
    print(f"  IDW surface  -> {idw_out}")
    tin_out = tin(pts, "measure", extent_str, os.path.join(OUT, "tin_surface.tif"))
    print(f"  TIN surface  -> {tin_out}")

    cv = cross_validate(pts, "measure")
    if cv:
        rmse, mae, n = cv
        print(f"\n  IDW cross-validation (n={n} holdout):")
        print(f"    RMSE = {rmse:.3f}")
        print(f"    MAE  = {mae:.3f}")
    print(f"\n  Outputs -> {OUT}")


if __name__ == "__main__" or "__file__" not in globals():
    main()
