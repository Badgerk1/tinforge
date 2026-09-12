"""Focused tests for PDF parser OCR fallback behavior."""

from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from src.parsers.pdf_parser import PDFParser
from src.process_real_data import summarize_points


def test_extract_elevation_points_from_ocr_rows_filters_noise():
    parser = PDFParser()
    rows = [
        {
            "block_num": "1",
            "par_num": "1",
            "line_num": "1",
            "text": "(170.25)",
            "conf": "95",
            "left": "100",
            "top": "100",
            "width": "40",
            "height": "10",
        },
        {
            "block_num": "2",
            "par_num": "1",
            "line_num": "1",
            "text": "ELEV=170.40",
            "conf": "90",
            "left": "200",
            "top": "120",
            "width": "60",
            "height": "10",
        },
        {
            "block_num": "3",
            "par_num": "1",
            "line_num": "1",
            "text": "BENCHMARK",
            "conf": "90",
            "left": "300",
            "top": "140",
            "width": "40",
            "height": "10",
        },
        {
            "block_num": "3",
            "par_num": "1",
            "line_num": "1",
            "text": "ELEV=170.69",
            "conf": "90",
            "left": "345",
            "top": "140",
            "width": "50",
            "height": "10",
        },
        {
            "block_num": "3",
            "par_num": "1",
            "line_num": "1",
            "text": "METRES",
            "conf": "90",
            "left": "400",
            "top": "140",
            "width": "40",
            "height": "10",
        },
        {
            "block_num": "4",
            "par_num": "1",
            "line_num": "1",
            "text": "0.3048",
            "conf": "95",
            "left": "500",
            "top": "160",
            "width": "40",
            "height": "10",
        },
        {
            "block_num": "5",
            "par_num": "1",
            "line_num": "1",
            "text": "470.78",
            "conf": "95",
            "left": "600",
            "top": "180",
            "width": "40",
            "height": "10",
        },
        {
            "block_num": "6",
            "par_num": "1",
            "line_num": "1",
            "text": "170.00",
            "conf": "35",
            "left": "700",
            "top": "200",
            "width": "40",
            "height": "10",
        },
    ]

    points = parser._extract_elevation_points_from_ocr_rows(rows, page_height=1000.0, resolution=100)

    assert [round(point.z, 2) for point in points] == [170.25, 170.40, 170.69]


def test_summarize_points_handles_empty_collections():
    summary = summarize_points([])

    assert summary["point_count"] == 0
    assert summary["bounds"] is None
    assert summary["sample_points"] == []
