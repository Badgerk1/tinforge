"""Extract and summarize point data from the uploaded real survey PDFs."""

from pathlib import Path
import sys
from typing import Dict, List

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from src.core.tin_model import Point3D
from src.parsers.pdf_parser import PDFParser


REAL_SURVEY_DIR = REPOSITORY_ROOT / "real_survey_data"


def get_real_survey_files() -> List[Path]:
    """Discover uploaded real survey PDF files."""
    return sorted(REAL_SURVEY_DIR.glob("*.pdf"))


def format_bytes(size: int) -> str:
    """Format a byte count for display."""
    units = ("B", "KB", "MB", "GB")
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} B"


def summarize_points(points: List[Point3D]) -> Dict[str, object]:
    """Summarize a point collection."""
    if not points:
        return {
            "point_count": 0,
            "bounds": None,
            "sample_points": [],
        }

    x_values = [point.x for point in points]
    y_values = [point.y for point in points]
    z_values = [point.z for point in points]
    return {
        "point_count": len(points),
        "bounds": {
            "x_min": min(x_values),
            "x_max": max(x_values),
            "y_min": min(y_values),
            "y_max": max(y_values),
            "z_min": min(z_values),
            "z_max": max(z_values),
        },
        "sample_points": points[:5],
    }


def extract_real_survey_data(pdf_paths: List[Path] | None = None) -> List[Dict[str, object]]:
    """Extract points from the uploaded real survey PDFs."""
    parser = PDFParser(ocr_value_range=(100.0, 400.0))
    survey_files = [Path(path) for path in (get_real_survey_files() if pdf_paths is None else pdf_paths)]
    extracted = []

    for pdf_path in survey_files:
        points = parser.parse(str(pdf_path))
        extracted.append(
            {
                "file_path": pdf_path,
                "file_size": pdf_path.stat().st_size,
                "points": points,
                "parse_details": dict(parser.last_parse_details),
                "summary": summarize_points(points),
            }
        )

    return extracted


def main() -> int:
    """Run the real-survey extraction summary."""
    print("TinForge real survey PDF extraction")
    print(f"Survey folder: {REAL_SURVEY_DIR}")
    print()

    extracted = extract_real_survey_data()
    total_points = 0

    for item in extracted:
        summary = item["summary"]
        bounds = summary["bounds"]
        print(f"File: {item['file_path'].name}")
        print(f"  Path: {item['file_path']}")
        print(f"  Size: {format_bytes(item['file_size'])}")
        print(f"  Extraction source: {item['parse_details'].get('source', 'unknown')}")
        print(f"  Points extracted: {summary['point_count']}")
        if bounds:
            print(
                "  Bounds: "
                f"X[{bounds['x_min']:.2f}, {bounds['x_max']:.2f}] "
                f"Y[{bounds['y_min']:.2f}, {bounds['y_max']:.2f}] "
                f"Z[{bounds['z_min']:.3f}, {bounds['z_max']:.3f}]"
            )
        else:
            print("  Bounds: none")
        print("  Sample points:")
        for point in summary["sample_points"]:
            print(f"    - {point}")
        print()
        total_points += summary["point_count"]

    print(f"Total extracted points: {total_points}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
