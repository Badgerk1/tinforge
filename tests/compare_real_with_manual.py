"""Run staged validation for real-data extraction with manual TP3 context."""

from pathlib import Path
import sys
from typing import Optional

__test__ = False


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from src.compare_tin_files import parse_tin_file
from src.test_real_workflow import run_real_workflow


MANUAL_TP3_PATH = REPOSITORY_ROOT / "real_survey_data" / "Purolator NP 2026.tp3"
OUTPUT_DIR = REPOSITORY_ROOT / "tests" / "output"
REPORT_PATH = OUTPUT_DIR / "COMPARISON_REPORT.txt"


def _safe_point_count(path: Path) -> tuple[Optional[int], Optional[str]]:
    """Return parsed point count or an informational error message."""
    try:
        return len(parse_tin_file(path).points), None
    except Exception as exc:  # pragma: no cover - best effort for context reporting
        return None, str(exc)


def main() -> int:
    """Generate TinForge outputs and validate extraction-stage expectations."""
    workflow_results = run_real_workflow(output_dir=OUTPUT_DIR)

    points_extracted = len(workflow_results["combined_points"])
    triangles_created = workflow_results["tin_statistics"]["triangle_count"]
    output_files = workflow_results["output_files"]
    missing_outputs = [
        str(path)
        for path in output_files.values()
        if not (path.exists() and path.stat().st_size > 0)
    ]

    extraction_checks = [
        ("Extracted at least 3 points", points_extracted >= 3),
        ("Created at least 1 triangle", triangles_created >= 1),
        ("Generated all expected exports", len(missing_outputs) == 0),
    ]
    extraction_pass = all(result for _, result in extraction_checks)

    lines = [
        "=== REAL SURVEY STAGED VALIDATION REPORT ===",
        "Stage under validation: PDF extraction + TIN generation",
        "",
        "EXTRACTION-STAGE RESULTS:",
        f"  Extracted Points: {points_extracted}",
        f"  Generated Triangles: {triangles_created}",
        f"  Output Files: {len(output_files) - len(missing_outputs)}/{len(output_files)}",
        "",
        "EXTRACTION-STAGE CHECKS:",
    ]
    for label, passed in extraction_checks:
        lines.append(f"  - {'✓' if passed else '✗'} {label}")

    if missing_outputs:
        lines.extend(["", "MISSING OUTPUTS:"])
        lines.extend(f"  - {path}" for path in missing_outputs)

    manual_points, manual_parse_error = _safe_point_count(MANUAL_TP3_PATH)
    generated_tin_path = output_files.get("topcon_tin")
    if generated_tin_path is not None:
        generated_points, generated_parse_error = _safe_point_count(generated_tin_path)
    else:
        generated_points, generated_parse_error = None, "Missing output key: topcon_tin"

    lines.extend(
        [
            "",
            "MANUAL TP3 CONTEXT (INFORMATIONAL ONLY):",
            "  Note: Manual TP3 may include integrated design/finalized points and is not used for extraction-stage PASS/FAIL.",
            f"  Manual TP3 Points: {manual_points if manual_points is not None else 'unavailable'}",
            f"  Generated TIN Points: {generated_points if generated_points is not None else 'unavailable'}",
            "",
            f"VALIDATION RESULT: {'✓ PASS' if extraction_pass else '✗ FAIL'}",
        ]
    )
    if manual_parse_error or generated_parse_error:
        lines.append("  Context parse warnings:")
        if manual_parse_error:
            lines.append(f"    - Manual TP3 parse failed: {manual_parse_error}")
        if generated_parse_error:
            lines.append(f"    - Generated TIN parse failed: {generated_parse_error}")

    report_text = "\n".join(lines) + "\n"

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report_text, encoding="utf-8")

    print(report_text, end="")
    print(f"Report saved to: {REPORT_PATH}")
    return 0 if extraction_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
