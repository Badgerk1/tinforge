"""Pytest coverage for the real survey workflow runner."""

from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from src.test_real_workflow import run_real_workflow


def test_run_real_workflow_creates_expected_outputs(tmp_path):
    results = run_real_workflow(output_dir=tmp_path)

    input_summaries = {item["file_path"].name: item for item in results["inputs"]}

    assert len(results["combined_points"]) == 4477
    assert input_summaries["63287_001-C1.1 -R1.pdf"]["summary"]["point_count"] == 0
    assert input_summaries["63287_002-TB1-ElevationsOn-24x30-Horiz-Topo.pdf"]["summary"]["point_count"] == 4477
    assert input_summaries["63287_002-TB1-ElevationsOn-24x30-Horiz-Topo.pdf"]["parse_details"]["source"] == "companion_tp3"
    assert results["tin_statistics"]["triangle_count"] >= 1
    assert results["report_path"].exists()
    assert "extraction source: companion_tp3" in results["report_text"]
    for output_path in results["output_files"].values():
        assert output_path.exists()
        assert output_path.stat().st_size > 0
