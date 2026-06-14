"""
06_remote_sensing_ndvi.py
=========================

Multispectral remote-sensing analysis: NDVI and vegetation classification.

Workflow
--------
1. Read a 4-band image (B, G, R, NIR).
2. Compute NDVI = (NIR - Red) / (NIR + Red) with the raster calculator.
3. Threshold NDVI into a vegetation mask (NDVI > 0.3).
4. Polygonise the mask and report total vegetated area.

Demonstrates: band math / spectral indices, raster calculator expressions,
thresholding, raster-to-vector conversion, and area accounting -- the standard
remote-sensing vegetation-mapping pipeline.
"""

import os

from qgis.core import QgsRasterLayer, QgsVectorLayer
import processing

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) \
    if "__file__" in globals() else os.getcwd()
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(ROOT, "output")
os.makedirs(OUT, exist_ok=True)

IMG = os.path.join(DATA, "multiband.tif")
NDVI_THRESHOLD = 0.3


def main():
    print("== 06 Remote sensing (NDVI) ==")
    img = QgsRasterLayer(IMG, "multiband")
    if not img.isValid():
        raise RuntimeError(f"{IMG} missing (run generate_sample_data.py)")
    print(f"  image: {img.width()}x{img.height()}, {img.bandCount()} bands")

    # Band order in our sample: 1=Blue 2=Green 3=Red 4=NIR.
    ndvi_path = os.path.join(OUT, "ndvi.tif")
    processing.run("gdal:rastercalculator", {
        "INPUT_A": IMG, "BAND_A": 4,    # NIR
        "INPUT_B": IMG, "BAND_B": 3,    # Red
        "FORMULA": "(A.astype(float) - B) / (A.astype(float) + B + 1e-10)",
        "NO_DATA": None,
        "RTYPE": 5,                     # Float32
        "OUTPUT": ndvi_path,
    })
    print(f"  NDVI -> {ndvi_path}")

    # Vegetation mask: 1 where NDVI > threshold, else nodata.
    mask_path = os.path.join(OUT, "veg_mask.tif")
    processing.run("gdal:rastercalculator", {
        "INPUT_A": ndvi_path, "BAND_A": 1,
        "FORMULA": f"A > {NDVI_THRESHOLD}",
        "NO_DATA": 0,
        "RTYPE": 1,                     # Byte
        "OUTPUT": mask_path,
    })

    # Polygonise the mask and measure vegetated area.
    veg_vec = processing.run("gdal:polygonize", {
        "INPUT": mask_path, "BAND": 1, "FIELD": "veg",
        "EIGHT_CONNECTEDNESS": False,
        "OUTPUT": os.path.join(OUT, "vegetation.gpkg"),
    })["OUTPUT"]
    veg = QgsVectorLayer(veg_vec, "veg", "ogr")

    total_ha = 0.0
    for f in veg.getFeatures():
        if f["veg"] == 1:
            total_ha += f.geometry().area() / 10_000.0

    # NDVI summary statistics.
    stats = processing.run("native:rasterlayerstatistics",
                           {"INPUT": ndvi_path, "BAND": 1})
    print(f"\n  NDVI range: {stats['MIN']:.3f} .. {stats['MAX']:.3f} "
          f"(mean {stats['MEAN']:.3f})")
    print(f"  Vegetated area (NDVI > {NDVI_THRESHOLD}): {total_ha:.2f} ha")
    print(f"  Outputs -> {OUT}")


if __name__ == "__main__" or "__file__" not in globals():
    main()
