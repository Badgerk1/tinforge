"""Focused tests for PDF parser OCR fallback behavior."""

from pathlib import Path
import sys

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from src.parsers.pdf_parser import PDFParser
from src.process_real_data import summarize_points


def test_extract_elevation_points_from_ocr_rows_filters_noise():
    parser = PDFParser(ocr_value_range=(100.0, 400.0))
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
    assert [round(point.x, 1) for point in points] == [86.4, 165.6, 266.4]
    assert [round(point.y, 1) for point in points] == [924.4, 910.0, 895.6]


def test_summarize_points_handles_empty_collections():
    summary = summarize_points([])

    assert summary["point_count"] == 0
    assert summary["bounds"] is None
    assert summary["sample_points"] == []


def test_parse_normalizes_duplicate_ocr_points(monkeypatch):
    parser = PDFParser(ocr_value_range=(100.0, 400.0))

    class FakePage:
        def extract_tables(self):
            return []

        def extract_text(self):
            return None

    class FakePDF:
        pages = [FakePage()]

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    parser.pdfplumber = type("FakePdfPlumber", (), {"open": staticmethod(lambda _: FakePDF())})
    monkeypatch.setattr("src.parsers.pdf_parser.shutil.which", lambda _: "/usr/bin/tesseract")
    parser._extract_from_ocr = lambda page, page_idx: [
        parser._parse_coordinate_row(["10.0", "20.0", "170.0"], 0),
        parser._parse_coordinate_row(["10.0", "20.0", "170.0"], 1),
        parser._parse_coordinate_row(["30.0", "40.0", "171.0"], 2),
    ]
    points = parser.parse("unused.pdf")

    assert len(points) == 2
    assert [point.id for point in points] == [1, 2]
    assert [(point.x, point.y, point.z) for point in points] == [(10.0, 20.0, 170.0), (30.0, 40.0, 171.0)]


def test_extract_from_ocr_requires_tesseract(monkeypatch):
    parser = PDFParser(ocr_value_range=(100.0, 400.0))
    monkeypatch.setattr("src.parsers.pdf_parser.shutil.which", lambda _: None)

    with pytest.raises(RuntimeError, match="tesseract"):
        parser._extract_from_ocr(object(), 0)


def test_extract_from_ocr_requires_tsv_output(monkeypatch):
    parser = PDFParser(ocr_value_range=(100.0, 400.0))

    class FakeImage:
        def save(self, path):
            Path(path).write_bytes(b"png")

    class FakePage:
        def to_image(self, resolution):
            return type("FakePageImage", (), {"original": FakeImage()})()

    monkeypatch.setattr("src.parsers.pdf_parser.shutil.which", lambda _: "/usr/bin/tesseract")
    monkeypatch.setattr("src.parsers.pdf_parser.subprocess.run", lambda *args, **kwargs: None)

    with pytest.raises(RuntimeError, match="did not produce TSV"):
        parser._extract_from_ocr(FakePage(), 0)


def test_parse_uses_annotation_points_before_ocr(monkeypatch, tmp_path):
    parser = PDFParser(ocr_value_range=(100.0, 400.0))
    pdf_path = tmp_path / "survey.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")

    class FakePage:
        images = []
        lines = [{}] * 800
        curves = [{}] * 400
        rects = [{}] * 20
        annots = [
            {"contents": "(170.25)", "x0": 10, "x1": 20, "y0": 30, "y1": 40},
            {"contents": "ELEV 170.40", "x0": 30, "x1": 40, "y0": 50, "y1": 60},
            {"contents": "NOT A POINT", "x0": 0, "x1": 0, "y0": 0, "y1": 0},
        ]

        def extract_tables(self):
            return []

        def extract_text(self):
            return None

    class FakePDF:
        pages = [FakePage()]

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    parser.pdfplumber = type("FakePdfPlumber", (), {"open": staticmethod(lambda _: FakePDF())})
    monkeypatch.setattr("src.parsers.pdf_parser.shutil.which", lambda _: None)

    points = parser.parse(str(pdf_path))

    assert len(points) == 2
    assert [round(point.z, 2) for point in points] == [170.25, 170.40]
    assert parser.last_parse_details["source"] == "pdf_annotations"


def test_parse_uses_ocr_when_pdf_extraction_finds_no_points(monkeypatch, tmp_path):
    parser = PDFParser(ocr_value_range=(100.0, 400.0))
    pdf_path = tmp_path / "survey.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")

    class FakePage:
        images = [{}]
        lines = []
        curves = []
        rects = []
        annots = [{"contents": "not numeric"}]

        def extract_tables(self):
            return []

        def extract_text(self):
            return None

    class FakePDF:
        pages = [FakePage()]

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    parser.pdfplumber = type("FakePdfPlumber", (), {"open": staticmethod(lambda _: FakePDF())})
    monkeypatch.setattr("src.parsers.pdf_parser.shutil.which", lambda _: "/usr/bin/tesseract")
    parser._extract_from_ocr = lambda page, page_idx: [
        parser._parse_coordinate_row(["10.0", "20.0", "170.0"], 0),
        parser._parse_coordinate_row(["30.0", "40.0", "171.0"], 1),
    ]

    points = parser.parse(str(pdf_path))

    assert len(points) == 2
    assert parser.last_parse_details["source"] == "ocr"


def test_extract_from_annotations_ignores_non_spot_values():
    parser = PDFParser(ocr_value_range=(100.0, 400.0))
    class FakePage:
        annots = [
            {"contents": "ELEV 170.30", "x0": 10, "x1": 20, "y0": 30, "y1": 40},
            {"contents": "P.I.N. 07367-0090 (LT)", "x0": 50, "x1": 60, "y0": 70, "y1": 80},
            {"contents": "100 200 300", "x0": 90, "x1": 100, "y0": 110, "y1": 120},
        ]

    points = parser._extract_from_annotations(FakePage())

    assert len(points) == 1
    assert round(points[0].z, 2) == 170.30
