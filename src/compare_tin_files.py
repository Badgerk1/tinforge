"""Compare TinForge-generated TIN output with a manual Topcon TP3 file."""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import permutations
import math
from pathlib import Path
import re
import struct
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from src.core.tin_model import Point3D, Triangle
from src.core.triangulation import DelaunayTriangulator

try:
    from scipy.spatial import cKDTree
except ImportError:  # pragma: no cover - fallback used only when SciPy is unavailable
    cKDTree = None


@dataclass
class ParsedTIN:
    """Normalized TIN representation used for comparison."""

    path: Path
    source_format: str
    name: str
    points: List[Point3D]
    triangles: List[Tuple[int, int, int]]
    metadata: Dict[str, object] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)

    @property
    def bounds(self) -> Optional[Dict[str, float]]:
        """Return coordinate bounds for the parsed points."""
        if not self.points:
            return None

        x_values = [point.x for point in self.points]
        y_values = [point.y for point in self.points]
        z_values = [point.z for point in self.points]
        return {
            "x_min": min(x_values),
            "x_max": max(x_values),
            "y_min": min(y_values),
            "y_max": max(y_values),
            "z_min": min(z_values),
            "z_max": max(z_values),
        }

    @property
    def total_area(self) -> float:
        """Return total 2D area covered by the triangles."""
        if not self.triangles or not self.points:
            return 0.0

        point_map = {point.id: point for point in self.points if point.id is not None}
        area = 0.0
        for point1_id, point2_id, point3_id in self.triangles:
            point1 = point_map.get(point1_id)
            point2 = point_map.get(point2_id)
            point3 = point_map.get(point3_id)
            if point1 is None or point2 is None or point3 is None:
                continue
            area += Triangle(point1=point1, point2=point2, point3=point3).get_area_2d()
        return area

    @property
    def point_id_sequence_ok(self) -> bool:
        """Check whether point IDs are sequential from 1..N."""
        point_ids = [point.id for point in self.points if point.id is not None]
        return point_ids == list(range(1, len(point_ids) + 1))


@dataclass
class ComparisonResult:
    """Detailed comparison output for report rendering."""

    manual: ParsedTIN
    generated: ParsedTIN
    coordinate_tolerance: float
    point_count_match: bool
    coordinate_match_percent: float
    coordinate_matches_within_tolerance: int
    bounds_difference_percent: float
    triangle_count_match: bool
    triangle_match_percent: float
    area_difference_percent: float
    equivalent: bool
    differences: List[str]


def parse_tin_file(path: Path | str) -> ParsedTIN:
    """Parse a supported TIN file."""
    file_path = Path(path)
    data = file_path.read_bytes()

    if data.startswith(b"Topcon TP3"):
        return _parse_binary_topcon_tp3(file_path, data)

    text = data.decode("utf-8", errors="replace")
    if "TOPCON_TP3_FORMAT" in text and "[POINTS]" in text:
        return _parse_text_topcon_tp3(file_path, text)
    if "POINTS" in text and "TRIANGLES" in text:
        return _parse_text_tin(file_path, text)

    raise ValueError("Unsupported TIN file format")


def compare_tin_files(
    manual_path: Path | str,
    generated_path: Path | str,
    coordinate_tolerance: float = 0.01,
    bounds_tolerance_percent: float = 1.0,
    area_tolerance_percent: float = 1.0,
) -> ComparisonResult:
    """Parse two files and compare them."""
    manual = parse_tin_file(manual_path)
    generated = parse_tin_file(generated_path)

    shared_point_count = min(len(manual.points), len(generated.points))
    matched_points, coordinate_match_percent = _match_points(
        manual.points,
        generated.points,
        tolerance=coordinate_tolerance,
    )
    bounds_difference_percent = _calculate_bounds_difference_percent(manual.bounds, generated.bounds)
    triangle_match_percent = _calculate_triangle_match_percent(manual.triangles, generated.triangles)
    area_difference_percent = _percent_difference(manual.total_area, generated.total_area)

    differences = _build_differences(
        manual=manual,
        generated=generated,
        coordinate_tolerance=coordinate_tolerance,
        matched_points=matched_points,
        shared_point_count=shared_point_count,
        bounds_difference_percent=bounds_difference_percent,
        triangle_match_percent=triangle_match_percent,
        area_difference_percent=area_difference_percent,
    )

    equivalent = (
        not differences
        and len(manual.points) == len(generated.points)
        and len(manual.triangles) == len(generated.triangles)
        and coordinate_match_percent >= 100.0
        and bounds_difference_percent <= bounds_tolerance_percent
        and area_difference_percent <= area_tolerance_percent
    )

    return ComparisonResult(
        manual=manual,
        generated=generated,
        coordinate_tolerance=coordinate_tolerance,
        point_count_match=len(manual.points) == len(generated.points),
        coordinate_match_percent=coordinate_match_percent,
        coordinate_matches_within_tolerance=matched_points,
        bounds_difference_percent=bounds_difference_percent,
        triangle_count_match=len(manual.triangles) == len(generated.triangles),
        triangle_match_percent=triangle_match_percent,
        area_difference_percent=area_difference_percent,
        equivalent=equivalent,
        differences=differences,
    )


def render_comparison_report(result: ComparisonResult) -> str:
    """Render a human-readable comparison report."""
    manual_bounds = _format_bounds(result.manual.bounds)
    generated_bounds = _format_bounds(result.generated.bounds)
    lines = [
        "=== TIN FILE COMPARISON REPORT ===",
        f"Manual TP3: {result.manual.path.name}",
        f"TinForge Output: {result.generated.path.name}",
        "",
        "POINTS COMPARISON:",
        f"  Manual Points: {len(result.manual.points)}",
        f"  TinForge Points: {len(result.generated.points)}",
        f"  Match: {_checkmark(result.point_count_match)}",
        f"  Point IDs Sequential: manual={_checkmark(result.manual.point_id_sequence_ok)} "
        f"tinforge={_checkmark(result.generated.point_id_sequence_ok)}",
        "",
        "COORDINATES COMPARISON:",
        f"  Manual Bounds: {manual_bounds}",
        f"  TinForge Bounds: {generated_bounds}",
        f"  Difference: {result.bounds_difference_percent:.2f}%",
        f"  Within Tolerance ({result.coordinate_tolerance:.4f}): "
        f"{result.coordinate_matches_within_tolerance}/{min(len(result.manual.points), len(result.generated.points))}",
        "",
        "TRIANGLES COMPARISON:",
        f"  Manual Triangles: {len(result.manual.triangles)}",
        f"  TinForge Triangles: {len(result.generated.triangles)}",
        f"  Match Quality: {result.triangle_match_percent:.2f}%",
        f"  Area Difference: {result.area_difference_percent:.2f}%",
        "",
        "ACCURACY METRICS:",
        f"  Coordinate Match: {result.coordinate_match_percent:.2f}%",
        "  Tolerance Levels: "
        f"coordinate={result.coordinate_tolerance:.4f}, bounds=1.00%, area=1.00%",
        "",
        "DIFFERENCES FOUND:",
    ]

    if result.differences:
        lines.extend(f"  - {difference}" for difference in result.differences)
    else:
        lines.append("  - None")

    if result.manual.warnings or result.generated.warnings:
        lines.extend(["", "PARSER NOTES:"])
        for warning in result.manual.warnings:
            lines.append(f"  - Manual: {warning}")
        for warning in result.generated.warnings:
            lines.append(f"  - TinForge: {warning}")

    lines.extend(
        [
            "",
            f"VALIDATION RESULT: {_checkmark(result.equivalent)} "
            f"{'FILES MATCH' if result.equivalent else 'DIFFERENCES FOUND'}",
        ]
    )
    return "\n".join(lines) + "\n"


def _parse_text_topcon_tp3(path: Path, text: str) -> ParsedTIN:
    """Parse TinForge's text TP3 export."""
    lines = [line.strip() for line in text.splitlines()]
    name = path.stem
    points: List[Point3D] = []
    triangles: List[Tuple[int, int, int]] = []
    section = None

    for line in lines:
        if line.startswith("Name:"):
            name = line.split(":", 1)[1].strip() or name
        elif line == "[POINTS]":
            section = "points"
            continue
        elif line == "[TRIANGLES]":
            section = "triangles"
            continue
        elif not line or line.startswith("TOPCON_TP3_FORMAT") or ":" in line:
            continue

        if section == "points":
            point_id, x_value, y_value, z_value = line.split("\t")[:4]
            points.append(
                Point3D(
                    id=int(point_id),
                    x=float(x_value),
                    y=float(y_value),
                    z=float(z_value),
                )
            )
        elif section == "triangles":
            triangle_values = line.split("\t")[:4]
            if len(triangle_values) == 4:
                _, point1_id, point2_id, point3_id = triangle_values
                triangles.append((int(point1_id), int(point2_id), int(point3_id)))

    return ParsedTIN(path=path, source_format="tinforge_text_tp3", name=name, points=points, triangles=triangles)


def _parse_text_tin(path: Path, text: str) -> ParsedTIN:
    """Parse the generic text TIN export."""
    name = path.stem
    points: List[Point3D] = []
    triangles: List[Tuple[int, int, int]] = []
    section = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("# TIN File:"):
            name = line.split(":", 1)[1].strip() or name
            continue
        if line.startswith("#"):
            continue
        if line == "POINTS":
            section = "points"
            continue
        if line == "TRIANGLES":
            section = "triangles"
            continue

        if section == "points":
            tokens = line.split("#", 1)[0].split()
            if len(tokens) >= 4:
                point_id, x_value, y_value, z_value = tokens[:4]
                points.append(
                    Point3D(
                        id=int(point_id),
                        x=float(x_value),
                        y=float(y_value),
                        z=float(z_value),
                    )
                )
        elif section == "triangles":
            tokens = line.split()
            if len(tokens) >= 4:
                _, point1_id, point2_id, point3_id = tokens[:4]
                triangles.append((int(point1_id), int(point2_id), int(point3_id)))

    return ParsedTIN(path=path, source_format="tinforge_text_tin", name=name, points=points, triangles=triangles)


def _parse_binary_topcon_tp3(path: Path, data: bytes) -> ParsedTIN:
    """Best-effort parser for a binary Topcon TP3 file."""
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

    return ParsedTIN(
        path=path,
        source_format="topcon_binary_tp3",
        name=project_name,
        points=points,
        triangles=triangles,
        metadata=metadata,
        warnings=warnings,
    )


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
                    if len(current_run) >= 5:
                        run_info = _build_run_info(current_run, remainder, order)
                        if run_info is not None:
                            candidate_runs.append(run_info)
                    current_run = []
            if len(current_run) >= 5:
                run_info = _build_run_info(current_run, remainder, order)
                if run_info is not None:
                    candidate_runs.append(run_info)

    candidate_runs.sort(key=lambda item: item["score"], reverse=True)
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


def _match_points(
    points_a: Sequence[Point3D],
    points_b: Sequence[Point3D],
    tolerance: float,
) -> Tuple[int, float]:
    """Match points between two collections using nearest-neighbor distance."""
    if not points_a or not points_b:
        return 0, 0.0

    if cKDTree is not None:
        target_tree = cKDTree([(point.x, point.y, point.z) for point in points_b])
        distances, _ = target_tree.query([(point.x, point.y, point.z) for point in points_a], k=1)
        matched = sum(1 for distance in distances if distance <= tolerance)
    else:
        matched = 0
        for point in points_a:
            best_distance = min(
                _distance_3d(point, candidate)
                for candidate in points_b
            )
            if best_distance <= tolerance:
                matched += 1

    denominator = max(len(points_a), len(points_b))
    percent = (matched / denominator) * 100.0 if denominator else 0.0
    return matched, percent


def _distance_3d(point_a: Point3D, point_b: Point3D) -> float:
    """Calculate 3D distance between two points."""
    return math.sqrt(
        (point_a.x - point_b.x) ** 2
        + (point_a.y - point_b.y) ** 2
        + (point_a.z - point_b.z) ** 2
    )


def _calculate_bounds_difference_percent(
    bounds_a: Optional[Dict[str, float]],
    bounds_b: Optional[Dict[str, float]],
) -> float:
    """Calculate aggregate percentage difference between file bounds."""
    if not bounds_a or not bounds_b:
        return 100.0

    differences = []
    for key in ("x_min", "x_max", "y_min", "y_max", "z_min", "z_max"):
        differences.append(_percent_difference(bounds_a[key], bounds_b[key]))
    return max(differences) if differences else 0.0


def _calculate_triangle_match_percent(
    triangles_a: Sequence[Tuple[int, int, int]],
    triangles_b: Sequence[Tuple[int, int, int]],
) -> float:
    """Calculate exact triangle match percentage."""
    if not triangles_a and not triangles_b:
        return 100.0
    if not triangles_a or not triangles_b:
        return 0.0

    normalized_a = {tuple(sorted(triangle)) for triangle in triangles_a}
    normalized_b = {tuple(sorted(triangle)) for triangle in triangles_b}
    matched = len(normalized_a & normalized_b)
    denominator = max(len(normalized_a), len(normalized_b))
    return (matched / denominator) * 100.0 if denominator else 0.0


def _percent_difference(left: float, right: float) -> float:
    """Return the percentage difference between two numeric values."""
    baseline = max(abs(left), abs(right), 1e-9)
    return abs(left - right) / baseline * 100.0


def _build_differences(
    manual: ParsedTIN,
    generated: ParsedTIN,
    coordinate_tolerance: float,
    matched_points: int,
    shared_point_count: int,
    bounds_difference_percent: float,
    triangle_match_percent: float,
    area_difference_percent: float,
) -> List[str]:
    """Build a list of comparison differences."""
    differences = []
    if len(manual.points) != len(generated.points):
        differences.append(f"Point count differs ({len(manual.points)} vs {len(generated.points)}).")
    if matched_points < shared_point_count:
        differences.append(
            f"Only {matched_points} of {shared_point_count} comparable points matched within tolerance {coordinate_tolerance:.4f}."
        )
    if bounds_difference_percent > 1.0:
        differences.append(f"Bounds differ by {bounds_difference_percent:.2f}%.")
    if len(manual.triangles) != len(generated.triangles):
        differences.append(f"Triangle count differs ({len(manual.triangles)} vs {len(generated.triangles)}).")
    if triangle_match_percent < 100.0:
        differences.append(f"Triangle definitions match at {triangle_match_percent:.2f}%.")
    if area_difference_percent > 1.0:
        differences.append(f"Area differs by {area_difference_percent:.2f}%.")
    if not manual.point_id_sequence_ok or not generated.point_id_sequence_ok:
        differences.append("Point ID sequences are not fully sequential.")
    return differences


def _format_bounds(bounds: Optional[Dict[str, float]]) -> str:
    """Format bounds for display."""
    if not bounds:
        return "unavailable"
    return (
        f"X[{bounds['x_min']:.4f}-{bounds['x_max']:.4f}], "
        f"Y[{bounds['y_min']:.4f}-{bounds['y_max']:.4f}], "
        f"Z[{bounds['z_min']:.4f}-{bounds['z_max']:.4f}]"
    )


def _checkmark(value: bool) -> str:
    """Return a check or cross symbol."""
    return "✓" if value else "✗"
