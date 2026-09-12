"""Run a full comparison between the manual TP3 and TinForge output."""

from pathlib import Path
import sys

__test__ = False


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from src.compare_tin_files import compare_tin_files, render_comparison_report
from src.test_real_workflow import run_real_workflow


MANUAL_TP3_PATH = REPOSITORY_ROOT / "real_survey_data" / "Purolator NP 2026.tp3"
OUTPUT_DIR = REPOSITORY_ROOT / "tests" / "output"
REPORT_PATH = OUTPUT_DIR / "COMPARISON_REPORT.txt"


def main() -> int:
    """Generate TinForge outputs, compare them, and persist the report."""
    workflow_results = run_real_workflow(output_dir=OUTPUT_DIR)
    generated_path = workflow_results["output_files"]["topcon_tin"]

    comparison = compare_tin_files(MANUAL_TP3_PATH, generated_path)
    report_text = render_comparison_report(comparison)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report_text, encoding="utf-8")

    print(report_text, end="")
    print(f"Report saved to: {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
