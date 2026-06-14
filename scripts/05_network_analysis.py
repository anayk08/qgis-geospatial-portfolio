"""
05_network_analysis.py
======================

Network / routing analysis on a road layer using QGIS's native graph tools.

Workflow
--------
1. Build a routable graph from a line network with a speed-based cost.
2. Compute the shortest path between two points (Dijkstra).
3. Generate a service area (isochrone-style reachable extent) from a facility.

This script builds a small synthetic road grid in memory if none is supplied,
so it is self-contained.

Demonstrates: QgsGraphBuilder / Dijkstra shortest path, cost strategies
(distance & travel-time), and service-area / catchment generation -- the core
of accessibility and logistics analysis.
"""

import os

from qgis.core import (
    QgsVectorLayer, QgsFeature, QgsGeometry, QgsPointXY, QgsField,
    QgsProject, QgsDistanceArea,
)
from qgis.analysis import (
    QgsVectorLayerDirector, QgsNetworkDistanceStrategy,
    QgsGraphBuilder, QgsGraphAnalyzer,
)
from qgis.PyQt.QtCore import QVariant

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) \
    if "__file__" in globals() else os.getcwd()
OUT = os.path.join(ROOT, "output")
os.makedirs(OUT, exist_ok=True)

XMIN, YMIN = 500000.0, 5_000_000.0
SPACING = 1000.0   # 1 km grid
N = 8              # 8x8 intersections


def build_road_grid():
    """Create an in-memory routable road grid (EPSG:32633)."""
    lyr = QgsVectorLayer("LineString?crs=EPSG:32633", "roads", "memory")
    pr = lyr.dataProvider()
    pr.addAttributes([QgsField("road_id", QVariant.Int)])
    lyr.updateFields()

    rid = 0
    feats = []
    for r in range(N):
        for c in range(N):
            x, y = XMIN + c * SPACING, YMIN + r * SPACING
            # horizontal segment
            if c < N - 1:
                f = QgsFeature(lyr.fields())
                f.setGeometry(QgsGeometry.fromPolylineXY(
                    [QgsPointXY(x, y), QgsPointXY(x + SPACING, y)]))
                f.setAttribute("road_id", rid); rid += 1
                feats.append(f)
            # vertical segment
            if r < N - 1:
                f = QgsFeature(lyr.fields())
                f.setGeometry(QgsGeometry.fromPolylineXY(
                    [QgsPointXY(x, y), QgsPointXY(x, y + SPACING)]))
                f.setAttribute("road_id", rid); rid += 1
                feats.append(f)
    pr.addFeatures(feats)
    lyr.updateExtents()
    print(f"  built road grid: {lyr.featureCount()} segments")
    return lyr


def build_graph(roads, tied_points):
    director = QgsVectorLayerDirector(
        roads, -1, "", "", "", QgsVectorLayerDirector.DirectionBoth)
    director.addStrategy(QgsNetworkDistanceStrategy())  # cost = distance (m)
    builder = QgsGraphBuilder(roads.sourceCrs())
    snapped = director.makeGraph(builder, tied_points)
    return builder.graph(), snapped


def shortest_path(graph, snapped, start_pt, end_pt):
    start_v = graph.findVertex(snapped[0])
    tree, cost = QgsGraphAnalyzer.dijkstra(graph, start_v, 0)
    end_v = graph.findVertex(snapped[1])
    if tree[end_v] == -1:
        return None, None
    # Walk back along the tree to reconstruct the route.
    route = [graph.vertex(end_v).point()]
    cur = end_v
    while cur != start_v:
        edge = graph.edge(tree[cur])
        cur = edge.fromVertex()
        route.append(graph.vertex(cur).point())
    route.reverse()
    return route, cost[end_v]


def service_area(graph, snapped_start_idx, max_cost):
    """Return reachable vertices within max_cost metres of the start."""
    start_v = graph.findVertex(snapped_start_idx)
    tree, cost = QgsGraphAnalyzer.dijkstra(graph, start_v, 0)
    reachable = [graph.vertex(i).point()
                 for i in range(graph.vertexCount())
                 if cost[i] != -1 and cost[i] <= max_cost]
    return reachable


def main():
    print("== 05 Network analysis ==")
    roads = build_road_grid()

    start = QgsPointXY(XMIN, YMIN)                       # SW corner
    end = QgsPointXY(XMIN + (N - 1) * SPACING,
                     YMIN + (N - 1) * SPACING)           # NE corner
    graph, snapped = build_graph(roads, [start, end])

    route, dist = shortest_path(graph, snapped, start, end)
    if route:
        # Straight-line vs network distance illustrates routing realism.
        d = QgsDistanceArea()
        straight = d.measureLine(start, end)
        print(f"  shortest path: {len(route)} vertices")
        print(f"    network distance  = {dist:,.0f} m")
        print(f"    straight-line     = {straight:,.0f} m")
        print(f"    detour factor     = {dist/straight:.2f}x")
        # Save the route.
        out = QgsVectorLayer("LineString?crs=EPSG:32633", "route", "memory")
        f = QgsFeature()
        f.setGeometry(QgsGeometry.fromPolylineXY(route))
        out.dataProvider().addFeature(f)
        import processing
        processing.run("native:savefeatures",
                       {"INPUT": out, "OUTPUT": os.path.join(OUT, "route.gpkg")})

    reach = service_area(graph, snapped[0], max_cost=3000.0)
    print(f"\n  service area within 3 km of start: "
          f"{len(reach)} reachable intersections")
    print(f"  Output -> {os.path.join(OUT, 'route.gpkg')}")


if __name__ == "__main__" or "__file__" not in globals():
    main()
