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


def test_parse_uses_companion_tp3_for_vector_heavy_pdf(monkeypatch, tmp_path):
    parser = PDFParser(ocr_value_range=(100.0, 400.0))
    pdf_path = tmp_path / "survey.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")
    tp3_path = tmp_path / "survey.tp3"
    tp3_path.write_bytes(b"Topcon TP3")

    class FakePage:
        images = []
        lines = [{}] * 800
        curves = [{}] * 400
        rects = [{}] * 20
        annots = []

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

    fake_points = [
        parser._parse_coordinate_row(["1.0", "2.0", "170.0"], 0),
        parser._parse_coordinate_row(["3.0", "4.0", "171.0"], 1),
    ]

    parser.pdfplumber = type("FakePdfPlumber", (), {"open": staticmethod(lambda _: FakePDF())})
    monkeypatch.setattr("src.parsers.pdf_parser.shutil.which", lambda _: None)
    monkeypatch.setattr("src.parsers.pdf_parser.PDFParser._extract_from_companion_tp3", lambda self, path: fake_points)

    points = parser.parse(str(pdf_path))

    assert points == fake_points
    assert parser.last_parse_details["source"] == "companion_tp3"
    assert parser.last_parse_details["companion_tp3_path"] == str(tp3_path)


def test_parse_skips_ocr_for_raster_reference_sheet_when_companion_tp3_exists(monkeypatch, tmp_path):
    parser = PDFParser(ocr_value_range=(100.0, 400.0))
    pdf_path = tmp_path / "reference.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")
    (tmp_path / "reference.tp3").write_bytes(b"Topcon TP3")

    class FakePage:
        images = [{}]
        lines = []
        curves = []
        rects = []
        annots = []

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

    assert points == []
    assert parser.last_parse_details["source"] == "empty_reference_sheet"


def test_find_companion_tp3_prefers_annotation_token_match(tmp_path):
    parser = PDFParser(ocr_value_range=(100.0, 400.0))
    pdf_path = tmp_path / "63287_002-TB1-ElevationsOn.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")
    wanted_tp3 = tmp_path / "Purolator NP 2026.TP3"
    wanted_tp3.write_bytes(b"Topcon TP3")
    other_tp3 = tmp_path / "Other Project.tp3"
    other_tp3.write_bytes(b"Topcon TP3")

    class FakePage:
        annots = [{"contents": "PUROLATOR WAREHOUSE"}]

        def extract_text(self):
            return None

    companion = parser._find_companion_tp3(pdf_path, [FakePage()])

    assert companion == wanted_tp3


def test_find_companion_tp3_can_inherit_single_match_from_sibling_pdf(tmp_path):
    parser = PDFParser(ocr_value_range=(100.0, 400.0))
    current_pdf = tmp_path / "63287_001-C1.1-R1.pdf"
    current_pdf.write_bytes(b"%PDF-1.4")
    sibling_pdf = tmp_path / "63287_002-TB1-ElevationsOn.pdf"
    sibling_pdf.write_bytes(b"%PDF-1.4")
    wanted_tp3 = tmp_path / "Purolator NP 2026.tp3"
    wanted_tp3.write_bytes(b"Topcon TP3")

    class ReferencePage:
        annots = []
        images = [{}]
        lines = []
        curves = []
        rects = []

        def extract_text(self):
            return None

    class SiblingPage:
        annots = [{"contents": "PUROLATOR WAREHOUSE"}]
        images = []
        lines = [{}] * 1000
        curves = []
        rects = []

        def extract_text(self):
            return None

    class FakePDF:
        def __init__(self, pages):
            self.pages = pages

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    parser.pdfplumber = type(
        "FakePdfPlumber",
        (),
        {
            "open": staticmethod(
                lambda path: FakePDF([SiblingPage()]) if Path(path) == sibling_pdf else FakePDF([ReferencePage()])
            )
        },
    )

    companion = parser._find_companion_tp3(current_pdf, [ReferencePage()], [""])

    assert companion == wanted_tp3
