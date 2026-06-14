"""
09_batch_processing.py
======================

Automation: a reusable, headless batch geoprocessor and a custom Processing
algorithm.

Part A -- batch_buffer_directory():
    Buffer every vector layer in a folder by a given distance and write the
    results out, logging successes/failures. The kind of unattended pipeline
    you schedule rather than click through.

Part B -- SuitabilityScoreAlgorithm:
    A self-contained QgsProcessingAlgorithm that scores parcels by a weighted
    combination of attributes -- showing how to extend QGIS with custom,
    parameterized tools that appear in the Processing Toolbox.

Demonstrates: headless batch processing, robust error handling/logging, and
authoring custom QgsProcessingAlgorithm tools (the foundation of plugins).
"""

import os
import glob

from qgis.core import (
    QgsVectorLayer, QgsProcessingAlgorithm, QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField, QgsProcessingParameterNumber,
    QgsProcessingParameterFeatureSink, QgsFeatureSink, QgsField, QgsFeature,
    QgsProcessing,
)
from qgis.PyQt.QtCore import QVariant, QCoreApplication
import processing

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) \
    if "__file__" in globals() else os.getcwd()
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(ROOT, "output")
os.makedirs(OUT, exist_ok=True)


# ---------------------------------------------------------------------------
# Part A: headless batch buffering with logging.
# ---------------------------------------------------------------------------
def batch_buffer_directory(in_dir, out_dir, distance_m=250.0):
    os.makedirs(out_dir, exist_ok=True)
    files = sorted(glob.glob(os.path.join(in_dir, "*.gpkg")))
    ok, failed = 0, 0
    print(f"  batch buffering {len(files)} layers by {distance_m:.0f} m")
    for path in files:
        name = os.path.splitext(os.path.basename(path))[0]
        lyr = QgsVectorLayer(path, name, "ogr")
        if not lyr.isValid() or lyr.featureCount() == 0:
            print(f"    SKIP  {name} (invalid/empty)")
            failed += 1
            continue
        try:
            out_path = os.path.join(out_dir, f"{name}_buf.gpkg")
            processing.run("native:buffer", {
                "INPUT": lyr, "DISTANCE": distance_m, "SEGMENTS": 12,
                "DISSOLVE": False, "OUTPUT": out_path,
            })
            print(f"    OK    {name} -> {os.path.basename(out_path)}")
            ok += 1
        except Exception as exc:                       # noqa: BLE001
            print(f"    FAIL  {name}: {exc}")
            failed += 1
    print(f"  batch complete: {ok} ok, {failed} failed")
    return ok, failed


# ---------------------------------------------------------------------------
# Part B: a custom Processing algorithm (weighted suitability score).
# ---------------------------------------------------------------------------
class SuitabilityScoreAlgorithm(QgsProcessingAlgorithm):
    INPUT = "INPUT"
    AREA_FIELD = "AREA_FIELD"
    VALUE_FIELD = "VALUE_FIELD"
    W_AREA = "W_AREA"
    W_VALUE = "W_VALUE"
    OUTPUT = "OUTPUT"

    def tr(self, s):
        return QCoreApplication.translate("SuitabilityScore", s)

    def createInstance(self):
        return SuitabilityScoreAlgorithm()

    def name(self):
        return "suitabilityscore"

    def displayName(self):
        return self.tr("Weighted suitability score")

    def group(self):
        return self.tr("Portfolio tools")

    def groupId(self):
        return "portfoliotools"

    def shortHelpString(self):
        return self.tr(
            "Adds a normalized 0-1 suitability score = w_area*area_norm + "
            "w_value*value_norm. Weights are renormalized to sum to 1.")

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT, self.tr("Input polygons"),
            [QgsProcessing.TypeVectorPolygon]))
        self.addParameter(QgsProcessingParameterField(
            self.AREA_FIELD, self.tr("Area field"), parentLayerParameterName=self.INPUT,
            type=QgsProcessingParameterField.Numeric, optional=True))
        self.addParameter(QgsProcessingParameterField(
            self.VALUE_FIELD, self.tr("Value field"),
            parentLayerParameterName=self.INPUT,
            type=QgsProcessingParameterField.Numeric))
        self.addParameter(QgsProcessingParameterNumber(
            self.W_AREA, self.tr("Weight: area"),
            QgsProcessingParameterNumber.Double, defaultValue=0.5))
        self.addParameter(QgsProcessingParameterNumber(
            self.W_VALUE, self.tr("Weight: value"),
            QgsProcessingParameterNumber.Double, defaultValue=0.5))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT, self.tr("Scored output")))

    def processAlgorithm(self, parameters, context, feedback):
        source = self.parameterAsSource(parameters, self.INPUT, context)
        area_field = self.parameterAsString(parameters, self.AREA_FIELD, context)
        value_field = self.parameterAsString(parameters, self.VALUE_FIELD, context)
        w_area = self.parameterAsDouble(parameters, self.W_AREA, context)
        w_value = self.parameterAsDouble(parameters, self.W_VALUE, context)

        # Renormalize weights.
        total_w = (w_area + w_value) or 1.0
        w_area, w_value = w_area / total_w, w_value / total_w

        # First pass: collect ranges for min-max normalization.
        feats = list(source.getFeatures())
        def area_of(f):
            return (f[area_field] if area_field else f.geometry().area())
        areas = [area_of(f) for f in feats]
        values = [f[value_field] or 0.0 for f in feats]
        a_min, a_max = (min(areas), max(areas)) if areas else (0, 1)
        v_min, v_max = (min(values), max(values)) if values else (0, 1)

        def norm(x, lo, hi):
            return (x - lo) / (hi - lo) if hi > lo else 0.0

        out_fields = source.fields()
        out_fields.append(QgsField("suit_score", QVariant.Double))
        sink, dest_id = self.parameterAsSink(
            parameters, self.OUTPUT, context, out_fields,
            source.wkbType(), source.sourceCrs())

        for i, f in enumerate(feats):
            if feedback.isCanceled():
                break
            score = (w_area * norm(area_of(f), a_min, a_max) +
                     w_value * norm(f[value_field] or 0.0, v_min, v_max))
            out = QgsFeature(out_fields)
            out.setGeometry(f.geometry())
            out.setAttributes(f.attributes() + [round(score, 4)])
            sink.addFeature(out, QgsFeatureSink.FastInsert)
            feedback.setProgress(int(100 * i / max(1, len(feats))))

        return {self.OUTPUT: dest_id}


def demo_custom_algorithm():
    """Register & run the custom algorithm on the parcels layer."""
    from qgis.core import QgsApplication
    reg = QgsApplication.processingRegistry()
    # In a plugin you'd add a provider; here we run the instance directly.
    alg = SuitabilityScoreAlgorithm()
    params = {
        "INPUT": os.path.join(DATA, "parcels.gpkg"),
        "VALUE_FIELD": "value_usd",
        "W_AREA": 0.4,
        "W_VALUE": 0.6,
        "OUTPUT": os.path.join(OUT, "parcels_scored.gpkg"),
    }
    from qgis.core import QgsProcessingContext, QgsProcessingFeedback
    ctx = QgsProcessingContext()
    fb = QgsProcessingFeedback()
    alg.initAlgorithm()
    result = alg.run(params, ctx, fb)
    print(f"  custom suitability algorithm -> {params['OUTPUT']}")
    return result


def main():
    print("== 09 Batch processing & custom algorithm ==")
    print("\n  Part A: batch buffer")
    batch_buffer_directory(DATA, os.path.join(OUT, "buffers"), distance_m=250.0)
    print("\n  Part B: custom Processing algorithm")
    demo_custom_algorithm()
    print(f"\n  Outputs -> {OUT}")


if __name__ == "__main__" or "__file__" not in globals():
    main()
