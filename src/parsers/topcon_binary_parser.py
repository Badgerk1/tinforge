"""Topcon TP3 binary parsing helpers used by comparison tooling."""

from __future__ import annotations

from itertools import permutations
import math
from pathlib import Path
import re
import struct
from typing import Dict, List, Optional, Sequence, Tuple

from ..core.tin_model import Point3D
from ..core.triangulation import DelaunayTriangulator


def extract_binary_topcon_tp3_data(
    path: Path,
    data: bytes,
) -> Tuple[str, List[Point3D], List[Tuple[int, int, int]], Dict[str, object], List[str]]:
    """Extract project name, points, triangles, metadata, and warnings from a binary TP3."""
    utf16_strings = _extract_utf16_strings(data)
    project_name = _extract_project_name(utf16_strings) or path.stem
    elevation_hints = _extract_numeric_hints(utf16_strings)
    points, run_metadata = _extract_binary_points(data, elevation_hints)
    warnings = [
        "Binary Topcon TP3 parsing is heuristic.",
        "Triangle connectivity is inferred with Delaunay when explicit triangle records are unavailable.",
    ]
    metadata: Dict[str, object] = {
        "project_name": project_name,
        "candidate_point_runs": run_metadata,
        "utf16_strings_sample": utf16_strings[:20],
    }

    triangles: List[Tuple[int, int, int]] = []
    if len(points) >= 3:
        triangles = _infer_triangles(points)
        metadata["triangle_source"] = "inferred_delaunay"
    else:
        warnings.append("No reliable point run was detected in the TP3 file.")
        metadata["triangle_source"] = "unavailable"

    return project_name, points, triangles, metadata, warnings


def _extract_utf16_strings(data: bytes) -> List[str]:
    """Extract UTF-16LE strings embedded in the binary file."""
    matches = re.findall(rb"(?:[\x20-\x7E]\x00){4,}", data)
    strings: List[str] = []
    for match in matches:
        try:
            strings.append(match.decode("utf-16le").strip("\x00 ").strip())
        except UnicodeDecodeError:
            continue
    return strings


def _extract_project_name(strings: Sequence[str]) -> Optional[str]:
    """Return the first plausible project name."""
    for value in strings:
        if "Topcon" in value:
            continue
        if len(value) >= 6 and not re.fullmatch(r"[0-9.\- ]+", value):
            return value
    return None


def _extract_numeric_hints(strings: Sequence[str]) -> List[float]:
    """Extract decimal values embedded as UTF-16 strings."""
    hints: List[float] = []
    for value in strings:
        if re.fullmatch(r"[+-]?\d+(?:\.\d+)?", value):
            numeric_value = float(value)
            if 50.0 <= numeric_value <= 1000.0:
                hints.append(numeric_value)
    return hints


def _extract_binary_points(data: bytes, elevation_hints: Sequence[float]) -> Tuple[List[Point3D], List[Dict[str, object]]]:
    """Extract plausible point runs from a binary TP3 file."""
    z_min = min(elevation_hints) - 10.0 if elevation_hints else 50.0
    z_max = max(elevation_hints) + 10.0 if elevation_hints else 1000.0
    candidate_runs = []
    used_offsets = set()

    for remainder in range(24):
        for order in permutations((0, 1, 2)):
            current_run = []
            for offset in range(remainder, len(data) - 24, 24):
                values = struct.unpack_from("<ddd", data, offset)
                point = _to_candidate_point(values, order, z_min, z_max)
                if point is not None:
                    current_run.append((offset, point))
                else:
                    if len(current_run) >= 4:
                        run_info = _build_run_info(current_run, remainder, order)
                        if run_info is not None:
                            candidate_runs.append(run_info)
                    current_run = []
            if len(current_run) >= 4:
                run_info = _build_run_info(current_run, remainder, order)
                if run_info is not None:
                    candidate_runs.append(run_info)

    candidate_runs.sort(key=lambda item: item["score"], reverse=True)
    if not elevation_hints and candidate_runs:
        candidate_runs = candidate_runs[:1]
    selected_runs = []
    merged_points: List[Point3D] = []
    seen_points = set()

    for run in candidate_runs:
        run_offsets = set(run["offsets"])
        if run_offsets & used_offsets:
            continue
        selected_runs.append(run)
        used_offsets.update(run_offsets)
        for point in run["points"]:
            key = (round(point.x, 3), round(point.y, 3), round(point.z, 3))
            if key in seen_points:
                continue
            seen_points.add(key)
            merged_points.append(
                Point3D(
                    id=len(merged_points) + 1,
                    x=point.x,
                    y=point.y,
                    z=point.z,
                )
            )

    return merged_points, [
        {
            "remainder": run["remainder"],
            "order": run["order"],
            "point_count": len(run["points"]),
            "score": run["score"],
        }
        for run in selected_runs[:10]
    ]


def _to_candidate_point(
    values: Tuple[float, float, float],
    order: Tuple[int, int, int],
    z_min: float,
    z_max: float,
) -> Optional[Point3D]:
    """Convert unpacked doubles into a plausible survey point."""
    reordered = [values[index] for index in order]
    x_value, y_value, z_value = reordered
    if not all(math.isfinite(value) for value in reordered):
        return None
    if not (0.0 <= x_value <= 10000.0 and 0.0 <= y_value <= 10000.0 and z_min <= z_value <= z_max):
        return None
    if abs(x_value - y_value) < 1e-9 and abs(y_value - z_value) < 1e-9:
        return None
    return Point3D(x=x_value, y=y_value, z=z_value)


def _build_run_info(
    run: Sequence[Tuple[int, Point3D]],
    remainder: int,
    order: Tuple[int, int, int],
) -> Optional[Dict[str, object]]:
    """Score a candidate point run."""
    points = [point for _, point in run]
    x_values = [point.x for point in points]
    y_values = [point.y for point in points]
    z_values = [point.z for point in points]
    x_range = max(x_values) - min(x_values)
    y_range = max(y_values) - min(y_values)
    z_range = max(z_values) - min(z_values)
    unique_xy = len({(round(point.x, 3), round(point.y, 3)) for point in points})

    if unique_xy < 4:
        return None
    if x_range <= 0.0 or y_range <= 0.0:
        return None
    if z_range > x_range or z_range > y_range:
        return None

    score = float(len(points) * 10 + unique_xy * 2 - z_range)
    if x_range + y_range < z_range:
        score -= z_range * 10.0

    return {
        "remainder": remainder,
        "order": order,
        "offsets": [offset for offset, _ in run],
        "points": points,
        "score": score,
    }


def _infer_triangles(points: List[Point3D]) -> List[Tuple[int, int, int]]:
    """Infer triangles using the repository triangulation engine."""
    triangulator = DelaunayTriangulator(points)
    tin_model = triangulator.triangulate()
    triangles = []
    for triangle in tin_model.triangles:
        if triangle.point1.id is None or triangle.point2.id is None or triangle.point3.id is None:
            continue
        triangles.append((triangle.point1.id, triangle.point2.id, triangle.point3.id))
    return triangles
