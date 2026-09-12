"""Run the full TinForge workflow against the uploaded real survey PDFs."""

from pathlib import Path
import re
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


def _calculate_overall_success(validation: Dict[str, object]) -> bool:
    """Return True when every validation check except the rollup passed."""
    return all(
        value
        for key, value in validation.items()
        if key != "overall_success"
    )


def _replace_validation_line(report_text: str, label: str, passed: bool) -> str:
    """Replace a validation line in the rendered report."""
    status = "PASS" if passed else "FAIL"
    pattern = rf"^- {re.escape(label)}: (PASS|FAIL)$"
    return re.sub(pattern, f"- {label}: {status}", report_text, flags=re.MULTILINE)


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


def _build_report(
    extracted: List[Dict[str, object]],
    tin_stats: Dict[str, object],
    output_files: Dict[str, Path],
    validation: Dict[str, object],
    output_dir: Path,
) -> str:
    """Create a readable workflow report."""
    total_input_points = sum(item["summary"]["point_count"] for item in extracted)
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
            f"- extracted input points total: {total_input_points}",
            f"- final TIN points: {tin_stats['point_count']}",
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
            f"- output directory: {output_dir}",
        ]
    )

    for label, output_path in output_files.items():
        if output_path.exists():
            lines.extend(
                [
                    f"- {label}: {output_path.name}",
                    f"  path: {output_path}",
                    f"  size: {format_bytes(output_path.stat().st_size)}",
                    "  status: OK",
                ]
            )
        else:
            lines.extend(
                [
                    f"- {label}: {output_path.name}",
                    f"  path: {output_path}",
                    "  size: 0 B",
                    "  status: MISSING",
                ]
            )

    lines.extend(
        [
            "",
            "Validation",
            "----------",
            f"- minimum 10+ extracted points: {'PASS' if validation['minimum_points_met'] else 'FAIL'}",
            f"- valid TIN with triangles: {'PASS' if validation['triangles_created'] else 'FAIL'}",
            f"- all 6 exports successful: {'PASS' if validation['all_exports_successful'] else 'FAIL'}",
            f"- readable report created: {'PASS' if validation['report_created'] else 'FAIL'}",
            f"- descriptive files saved in tests/output: {'PASS' if validation['output_naming_ok'] else 'FAIL'}",
            f"- overall result: {'PASS' if validation['overall_success'] else 'FAIL'}",
        ]
    )

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
        "topcon_tp3": destination / "final_survey_topcon_tp3.tp3",
        "topcon_tin": destination / "final_survey_topcon_tin.tin",
        "topcon_xml": destination / "final_survey_topcon_xml.xml",
        "licai_tin": destination / "final_survey_licai_tin.tin",
        "licai_dat": destination / "final_survey_licai_dat.dat",
        "licai_xyz": destination / "final_survey_licai_xyz.xyz",
    }

    app.export_to_topcon(tin_model, str(output_files["topcon_tp3"]), "tp3")
    app.export_to_topcon(tin_model, str(output_files["topcon_tin"]), "tin")
    app.export_to_topcon(tin_model, str(output_files["topcon_xml"]), "xml")
    app.export_to_licai(tin_model, str(output_files["licai_tin"]), "tin")
    app.export_to_licai(tin_model, str(output_files["licai_dat"]), "dat")
    app.export_to_licai(tin_model, str(output_files["licai_xyz"]), "xyz")

    report_path = destination / "FINAL_TEST_REPORT.txt"

    validation = {
        "minimum_points_met": tin_stats["point_count"] >= 10,
        "triangles_created": tin_stats["triangle_count"] >= 1,
        "all_exports_successful": len(output_files) == 6 and all(
            path.exists() and path.stat().st_size > 0 for path in output_files.values()
        ),
        "report_created": False,
        "output_naming_ok": all(path.parent == destination and path.name.startswith("final_survey_") for path in output_files.values()),
    }
    validation["overall_success"] = _calculate_overall_success(validation)
    report_text = _build_report(extracted, tin_stats, output_files, validation, destination)
    report_path.write_text(report_text, encoding="utf-8")
    validation["report_created"] = report_path.exists() and report_path.stat().st_size > 0
    validation["overall_success"] = _calculate_overall_success(validation)
    report_text = _replace_validation_line(report_text, "readable report created", validation["report_created"])
    report_text = _replace_validation_line(report_text, "overall result", validation["overall_success"])
    report_path.write_text(report_text, encoding="utf-8")

    return {
        "inputs": extracted,
        "combined_points": combined_points,
        "tin_model": tin_model,
        "tin_statistics": tin_stats,
        "output_files": output_files,
        "report_path": report_path,
        "report_text": report_text,
        "validation": validation,
    }


def main() -> int:
    """CLI entry point for the real workflow."""
    results = run_real_workflow()
    print(results["report_text"])
    print(f"Report saved to: {results['report_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
