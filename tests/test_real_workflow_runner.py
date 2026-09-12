"""Pytest coverage for the real survey workflow runner."""

from pathlib import Path
import shutil
import sys

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from src.test_real_workflow import run_real_workflow


def test_run_real_workflow_creates_expected_outputs(tmp_path):
    if shutil.which("tesseract") is None:
        pytest.skip("tesseract is required for PDF-only extraction workflow validation")

    results = run_real_workflow(output_dir=tmp_path)

    input_summaries = {item["file_path"].name: item for item in results["inputs"]}
    topo_summary = input_summaries["63287_002-TB1-ElevationsOn-24x30-Horiz-Topo.pdf"]
    plan_summary = input_summaries["63287_001-C1.1 -R1.pdf"]

    assert len(results["combined_points"]) >= 3
    assert plan_summary["summary"]["point_count"] >= 1
    assert topo_summary["summary"]["point_count"] >= 1
    assert plan_summary["parse_details"]["source"].startswith("pdf_")
    assert topo_summary["parse_details"]["source"].startswith("pdf_")
    assert results["tin_statistics"]["triangle_count"] >= 1
    assert results["report_path"].exists()
    assert "extraction source:" in results["report_text"]
    for output_path in results["output_files"].values():
        assert output_path.exists()
        assert output_path.stat().st_size > 0
