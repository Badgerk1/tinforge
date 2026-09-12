"""Run the full TinForge workflow against the uploaded real survey PDFs."""

from pathlib import Path
import sys
from typing import Dict, List

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from src.app import TinForgeApp
from src.core.tin_model import Point3D
from src.core.triangulation import DelaunayTriangulator
from src.process_real_data import extract_real_survey_data, format_bytes


OUTPUT_DIR = REPOSITORY_ROOT / "tests" / "output"


def _renumber_points(points: List[Point3D]) -> List[Point3D]:
    """Assign sequential IDs across all extracted files."""
    return [
        Point3D(
            x=point.x,
            y=point.y,
            z=point.z,
            id=index,
            description=point.description,
            code=point.code,
        )
        for index, point in enumerate(points, start=1)
    ]


def _build_report(extracted: List[Dict[str, object]], tin_stats: Dict[str, object], output_files: Dict[str, Path]) -> str:
    """Create a readable workflow report."""
    lines = [
        "TinForge Real Survey Workflow Report",
        "===================================",
        "",
        "Input Files",
        "-----------",
    ]

    for item in extracted:
        summary = item["summary"]
        bounds = summary["bounds"]
        lines.extend([
            f"- {item['file_path'].name}",
            f"  path: {item['file_path']}",
            f"  size: {format_bytes(item['file_size'])}",
            f"  extracted points: {summary['point_count']}",
        ])
        if bounds:
            lines.append(
                "  bounds: "
                f"X[{bounds['x_min']:.2f}, {bounds['x_max']:.2f}] "
                f"Y[{bounds['y_min']:.2f}, {bounds['y_max']:.2f}] "
                f"Z[{bounds['z_min']:.3f}, {bounds['z_max']:.3f}]"
            )
        else:
            lines.append("  bounds: none")

    lines.extend(
        [
            "",
            "TIN Statistics",
            "--------------",
            f"- points: {tin_stats['point_count']}",
            f"- triangles: {tin_stats['triangle_count']}",
            f"- area: {tin_stats['area']:.2f}",
            (
                "- bounds: "
                f"X[{tin_stats['bounds']['x_min']:.2f}, {tin_stats['bounds']['x_max']:.2f}] "
                f"Y[{tin_stats['bounds']['y_min']:.2f}, {tin_stats['bounds']['y_max']:.2f}] "
                f"Z[{tin_stats['bounds']['z_min']:.3f}, {tin_stats['bounds']['z_max']:.3f}]"
            ),
            "",
            "Output Files",
            "------------",
        ]
    )

    for label, output_path in output_files.items():
        if output_path.exists():
            lines.append(f"- {label}: {output_path.name} ({format_bytes(output_path.stat().st_size)})")
        else:
            lines.append(f"- {label}: {output_path.name} (missing)")

    return "\n".join(lines) + "\n"


def run_real_workflow(output_dir: Path | None = None, input_paths: List[Path] | None = None) -> Dict[str, object]:
    """Execute the end-to-end real survey workflow."""
    extracted = extract_real_survey_data(input_paths)
    combined_points = []

    for item in extracted:
        combined_points.extend(item["points"])

    if len(combined_points) < 3:
        raise ValueError("At least 3 extracted points are required to build the real survey TIN workflow")

    combined_points = _renumber_points(combined_points)
    triangulator = DelaunayTriangulator(combined_points)
    tin_model = triangulator.triangulate()
    tin_model.name = "Real Survey Surface"
    tin_stats = triangulator.get_statistics()

    destination = Path(output_dir or OUTPUT_DIR)
    destination.mkdir(parents=True, exist_ok=True)

    app = TinForgeApp()
    output_files = {
        "topcon_tp3": destination / "real_survey_topcon.tp3",
        "topcon_tin": destination / "real_survey_topcon.tin",
        "topcon_xml": destination / "real_survey_topcon.xml",
        "licai_tin": destination / "real_survey_licai.tin",
        "licai_dat": destination / "real_survey_licai.dat",
        "licai_xyz": destination / "real_survey_licai.xyz",
    }

    app.export_to_topcon(tin_model, str(output_files["topcon_tp3"]), "tp3")
    app.export_to_topcon(tin_model, str(output_files["topcon_tin"]), "tin")
    app.export_to_topcon(tin_model, str(output_files["topcon_xml"]), "xml")
    app.export_to_licai(tin_model, str(output_files["licai_tin"]), "tin")
    app.export_to_licai(tin_model, str(output_files["licai_dat"]), "dat")
    app.export_to_licai(tin_model, str(output_files["licai_xyz"]), "xyz")

    report_path = destination / "real_survey_workflow_report.txt"
    report_text = _build_report(extracted, tin_stats, output_files)
    report_path.write_text(report_text, encoding="utf-8")

    return {
        "inputs": extracted,
        "combined_points": combined_points,
        "tin_model": tin_model,
        "tin_statistics": tin_stats,
        "output_files": output_files,
        "report_path": report_path,
        "report_text": report_text,
    }


def main() -> int:
    """CLI entry point for the real workflow."""
    results = run_real_workflow()
    print(results["report_text"])
    print(f"Report saved to: {results['report_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
