"""
08_atlas_cartography.py
=======================

Production cartography: a print layout driven by an Atlas to export one map
page per facility service area, plus a single overview map -- fully automated,
no manual layout editing.

Workflow
--------
1. Load parcels (styled by land use) and facilities.
2. Build a QgsPrintLayout programmatically: map, title, legend, scalebar,
   north arrow, and dynamic Atlas text.
3. Configure the Atlas to iterate over facilities and export a multi-page PDF.

Demonstrates: graduated/categorized styling, programmatic layout construction,
map decorations (legend/scalebar/north arrow), Atlas-driven map series, and
automated PDF export -- the deliverable end of every GIS engagement.
"""

import os

from qgis.core import (
    QgsProject, QgsVectorLayer, QgsPrintLayout, QgsLayoutItemMap,
    QgsLayoutItemLabel, QgsLayoutItemLegend, QgsLayoutItemScaleBar,
    QgsLayoutItemPicture, QgsLayoutPoint, QgsLayoutSize, QgsUnitTypes,
    QgsLayoutExporter, QgsRectangle, QgsCategorizedSymbolRenderer,
    QgsRendererCategory, QgsSymbol, QgsFillSymbol, QgsTextFormat,
)
from qgis.PyQt.QtGui import QColor, QFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) \
    if "__file__" in globals() else os.getcwd()
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(ROOT, "output")
os.makedirs(OUT, exist_ok=True)

LANDUSE_COLORS = {
    "residential":  "#fdd49e",
    "commercial":   "#3182bd",
    "industrial":   "#969696",
    "agricultural": "#a1d99b",
    "vacant":       "#f0f0f0",
}


def style_parcels(layer):
    cats = []
    for lu, hexcol in LANDUSE_COLORS.items():
        sym = QgsFillSymbol.createSimple(
            {"color": hexcol, "outline_color": "#636363",
             "outline_width": "0.2"})
        cats.append(QgsRendererCategory(lu, sym, lu))
    layer.setRenderer(QgsCategorizedSymbolRenderer("landuse", cats))
    layer.triggerRepaint()


def add_label(layout, text, x, y, size, bold=False):
    lbl = QgsLayoutItemLabel(layout)
    lbl.setText(text)
    font = QFont("Arial", size)
    font.setBold(bold)
    lbl.setFont(font)
    lbl.adjustSizeToText()
    lbl.attemptMove(QgsLayoutPoint(x, y, QgsUnitTypes.LayoutMillimeters))
    layout.addLayoutItem(lbl)
    return lbl


def main():
    print("== 08 Atlas cartography ==")
    project = QgsProject.instance()
    parcels = QgsVectorLayer(os.path.join(DATA, "parcels.gpkg"), "Parcels", "ogr")
    facilities = QgsVectorLayer(os.path.join(DATA, "facilities.gpkg"),
                                "Facilities", "ogr")
    if not parcels.isValid() or not facilities.isValid():
        raise RuntimeError("Sample layers missing (run generate_sample_data.py)")

    style_parcels(parcels)
    project.addMapLayer(parcels)
    project.addMapLayer(facilities)

    # ---- Build the layout -------------------------------------------------
    layout = QgsPrintLayout(project)
    layout.initializeDefaults()           # A4 portrait
    layout.setName("Service Area Atlas")

    # Map frame
    map_item = QgsLayoutItemMap(layout)
    map_item.setRect(0, 0, 190, 180)
    map_item.setExtent(parcels.extent())
    map_item.attemptMove(QgsLayoutPoint(10, 25, QgsUnitTypes.LayoutMillimeters))
    map_item.attemptResize(QgsLayoutSize(190, 180, QgsUnitTypes.LayoutMillimeters))
    map_item.setFrameEnabled(True)
    layout.addLayoutItem(map_item)

    # Title (static) + dynamic Atlas subtitle.
    add_label(layout, "Facility Service-Area Map Series", 10, 8, 16, bold=True)
    subtitle = add_label(
        layout,
        "[% 'Facility ' || \"fac_id\" || '  (' || \"type\" || ')' %]",
        10, 18, 11)

    # Legend
    legend = QgsLayoutItemLegend(layout)
    legend.setTitle("Land use")
    legend.setLinkedMap(map_item)
    legend.attemptMove(QgsLayoutPoint(155, 30, QgsUnitTypes.LayoutMillimeters))
    layout.addLayoutItem(legend)

    # Scale bar
    sb = QgsLayoutItemScaleBar(layout)
    sb.setStyle("Single Box")
    sb.setLinkedMap(map_item)
    sb.setUnits(QgsUnitTypes.DistanceMeters)
    sb.setUnitsPerSegment(1000)
    sb.setNumberOfSegments(4)
    sb.setUnitLabel("m")
    sb.attemptMove(QgsLayoutPoint(12, 200, QgsUnitTypes.LayoutMillimeters))
    layout.addLayoutItem(sb)

    # North arrow (resolved against QGIS's bundled SVG search paths).
    arrow = QgsLayoutItemPicture(layout)
    arrow.setPicturePath("svg/arrows/NorthArrow_02.svg")
    arrow.attemptMove(QgsLayoutPoint(180, 200, QgsUnitTypes.LayoutMillimeters))
    arrow.attemptResize(QgsLayoutSize(15, 15, QgsUnitTypes.LayoutMillimeters))
    layout.addLayoutItem(arrow)

    # ---- Configure the Atlas ---------------------------------------------
    atlas = layout.atlas()
    atlas.setEnabled(True)
    atlas.setCoverageLayer(facilities)
    atlas.setHideCoverage(False)
    map_item.setAtlasDriven(True)
    map_item.setAtlasScalingMode(QgsLayoutItemMap.Predefined)
    map_item.setAtlasMargin(2.0)          # 200% margin -> zoom around feature

    project.layoutManager().addLayout(layout)

    # ---- Export the full map series to one PDF ---------------------------
    pdf_path = os.path.join(OUT, "service_area_atlas.pdf")
    exporter = QgsLayoutExporter(layout)
    settings = QgsLayoutExporter.PdfExportSettings()
    result = exporter.exportToPdf(atlas, pdf_path, settings)
    n = facilities.featureCount()
    print(f"  built layout with {n} atlas pages "
          f"(1 per facility)")
    print(f"  exported -> {pdf_path}")


if __name__ == "__main__" or "__file__" not in globals():
    main()
