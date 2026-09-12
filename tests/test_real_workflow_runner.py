"""Pytest coverage for the real survey workflow runner."""

from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from src.test_real_workflow import run_real_workflow


def test_run_real_workflow_creates_expected_outputs(tmp_path):
    results = run_real_workflow(output_dir=tmp_path)

    assert len(results["combined_points"]) >= 3
    assert results["tin_statistics"]["triangle_count"] >= 1
    assert results["report_path"].exists()
    assert results["report_path"].name == "FINAL_TEST_REPORT.txt"
    assert results["validation"]["all_exports_successful"] is True
    for output_path in results["output_files"].values():
        assert output_path.exists()
        assert output_path.stat().st_size > 0
        assert output_path.name.startswith("final_survey_")
