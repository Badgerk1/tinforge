"""PDF point data parser."""

import re
import shutil
import subprocess
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import List, Optional
from ..core.tin_model import Point3D
from .point_parser import PointParser

SURVEY_ANNOTATION_PATTERNS = (
    re.compile(r"\belev\b", re.IGNORECASE),
    re.compile(r"\bgrade\b", re.IGNORECASE),
    re.compile(r"\bspot\b", re.IGNORECASE),
    re.compile(r"\bbm\b", re.IGNORECASE),
    re.compile(r"\blp\s*=", re.IGNORECASE),
    re.compile(r"\bt/?g\s*=", re.IGNORECASE),
    re.compile(r"\bex\b", re.IGNORECASE),
    re.compile(r"\)\s*ex\b", re.IGNORECASE),
)


class PDFParser(PointParser):
    """Extract survey points from PDF documents."""
    
    def __init__(
        self,
        ocr_value_range: Optional[tuple[float, float]] = None,
        dedupe_precision: int = 3,
    ):
        """Initialize PDF parser."""
        self.ocr_value_range = ocr_value_range
        self.dedupe_precision = dedupe_precision
        try:
            import pdfplumber
            self.pdfplumber = pdfplumber
        except ImportError:
            raise ImportError("pdfplumber required for PDF parsing. Install with: pip install pdfplumber")
    
    def parse(self, filepath: str) -> List[Point3D]:
        """
        Parse points from PDF file.
        
        Looks for coordinate tables or coordinate listings in PDF.
        
        Args:
            filepath: Path to PDF file
            
        Returns:
            List of Point3D objects
        """
        points = []
        
        try:
            with self.pdfplumber.open(filepath) as pdf:
                for page_idx, page in enumerate(pdf.pages):
                    page_points = []

                    # Try to extract table data
                    tables = page.extract_tables()
                    if tables:
                        for table in tables:
                            page_points.extend(self._extract_from_table(table, page_idx))

                    # Also try to extract text and find coordinates
                    text = page.extract_text()
                    if text:
                        page_points.extend(self._extract_from_text(text, page_idx))

                    if not page_points:
                        page_points = self._extract_from_ocr(page, page_idx)

                    points.extend(page_points)

        except FileNotFoundError:
            raise FileNotFoundError(f"PDF file not found: {filepath}")
        except (RuntimeError, ValueError):
            raise
        except Exception as e:
            raise RuntimeError(f"Error parsing PDF: {e}")

        points = self._normalize_points(points)

        if points and not all(self._validate_point(point) for point in points):
            raise ValueError("Extracted points validation failed")

        return points
    
    def _extract_from_table(self, table: list, page_idx: int) -> List[Point3D]:
        """
        Extract points from PDF table.
        
        Args:
            table: Table data from pdfplumber
            page_idx: Page index
            
        Returns:
            List of Point3D objects
        """
        points = []
        
        for row_idx, row in enumerate(table):
            if row_idx == 0:  # Skip header
                continue
            
            try:
                # Try to parse row as: ID, X, Y, Z or X, Y, Z
                values = [v for v in row if v and str(v).strip()]
                
                if len(values) >= 3:
                    point = self._parse_coordinate_row(values, row_idx)
                    if point:
                        points.append(point)
            except (ValueError, IndexError):
                continue
        
        return points
    
    def _extract_from_text(self, text: str, page_idx: int) -> List[Point3D]:
        """
        Extract points from unstructured PDF text.
        
        Looks for patterns like "123.45  456.78  789.01" (X Y Z coordinates)
        
        Args:
            text: Extracted text from PDF page
            page_idx: Page index
            
        Returns:
            List of Point3D objects
        """
        points = []
        
        # Regex pattern for numeric coordinate sequences
        # Matches: digit(s).digit(s) whitespace digit(s).digit(s) ...
        pattern = r'([+-]?\d+\.?\d*)\s+([+-]?\d+\.?\d*)\s+([+-]?\d+\.?\d*)'
        
        matches = re.findall(pattern, text)
        
        for match_idx, match in enumerate(matches):
            try:
                x = float(match[0])
                y = float(match[1])
                z = float(match[2])
                point = Point3D(x=x, y=y, z=z, id=match_idx + 1)
                points.append(point)
            except ValueError:
                continue
        
        return points

    def _extract_from_ocr(self, page: object, page_idx: int, resolution: int = 100) -> List[Point3D]:
        """
        Extract spot elevations from OCR when embedded PDF text is unavailable.

        Args:
            page: pdfplumber page object
            page_idx: Page index
            resolution: Rasterization resolution for OCR

        Returns:
            List of Point3D objects using page-space X/Y with OCR-derived Z
        """
        if not shutil.which("tesseract"):
            raise RuntimeError("OCR fallback requires the 'tesseract' binary to be installed")

        with tempfile.TemporaryDirectory(prefix="tinforge-ocr-") as tmp_dir:
            tmp_path = Path(tmp_dir)
            image_path = tmp_path / f"page_{page_idx + 1}.png"
            output_base = tmp_path / f"page_{page_idx + 1}"

            try:
                page.to_image(resolution=resolution).original.save(image_path)
            except Exception as exc:
                raise RuntimeError(f"OCR fallback could not render PDF page {page_idx + 1}: {exc}") from exc

            try:
                subprocess.run(
                    ["tesseract", str(image_path), str(output_base), "--psm", "11", "tsv"],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
            except subprocess.CalledProcessError as exc:
                error_details = exc.stderr.strip() if exc.stderr else str(exc)
                raise RuntimeError(f"OCR fallback failed for PDF page {page_idx + 1}: {error_details}") from exc
            except OSError as exc:
                raise RuntimeError(f"OCR fallback failed for PDF page {page_idx + 1}: {exc}") from exc

            tsv_path = output_base.with_suffix(".tsv")
            if not tsv_path.exists():
                raise RuntimeError(f"OCR fallback did not produce TSV output for PDF page {page_idx + 1}")

            rows = self._read_ocr_tsv(tsv_path)

        return self._extract_elevation_points_from_ocr_rows(rows, page.height, resolution)
    
    def _parse_coordinate_row(self, values: list, row_idx: int) -> Optional[Point3D]:
        """
        Parse coordinate row.
        
        Args:
            values: Row values
            row_idx: Row index
            
        Returns:
            Point3D object or None
        """
        try:
            if len(values) >= 4:
                # Try ID, X, Y, Z
                point_id = int(values[0])
                x = float(values[1])
                y = float(values[2])
                z = float(values[3])
                return Point3D(x=x, y=y, z=z, id=point_id)
            elif len(values) >= 3:
                # Try X, Y, Z
                x = float(values[0])
                y = float(values[1])
                z = float(values[2])
                return Point3D(x=x, y=y, z=z, id=row_idx)
        except (ValueError, IndexError):
            pass

        return None

    def _normalize_points(self, points: List[Point3D]) -> List[Point3D]:
        """De-duplicate points and ensure sequential point IDs."""
        normalized_points = []
        seen = set()

        for point in points:
            key = (
                round(point.x, self.dedupe_precision),
                round(point.y, self.dedupe_precision),
                round(point.z, self.dedupe_precision),
            )
            if key in seen:
                continue
            seen.add(key)
            normalized_points.append(
                Point3D(
                    x=point.x,
                    y=point.y,
                    z=point.z,
                    id=len(normalized_points) + 1,
                    description=point.description,
                    code=point.code,
                )
            )

        return normalized_points

    def _extract_elevation_points_from_ocr_rows(
        self,
        rows: List[dict],
        page_height: float,
        resolution: int,
    ) -> List[Point3D]:
        """Convert OCR TSV rows into page-space elevation points."""
        line_rows = defaultdict(list)
        for row in rows:
            text = (row.get("text") or "").strip()
            if not text:
                continue
            line_key = (
                row.get("block_num", ""),
                row.get("par_num", ""),
                row.get("line_num", ""),
            )
            line_rows[line_key].append(row)

        scale = resolution / 72.0
        points = []

        for line in line_rows.values():
            tokens = [(row.get("text") or "").strip() for row in line if (row.get("text") or "").strip()]
            normalized_line = " ".join(tokens).lower()
            short_context = len(tokens) <= 8
            keyword_context = short_context and any(keyword in normalized_line for keyword in ("elev", "grade", "spot", "bm"))

            for row in line:
                token = (row.get("text") or "").strip().replace(",", "")
                match = re.search(r'([+-]?\d+\.\d+)', token)
                if not match:
                    continue

                try:
                    value = float(match.group(1))
                    confidence = float(row.get("conf", "-1"))
                    left = int(row.get("left", "0"))
                    top = int(row.get("top", "0"))
                    width = int(row.get("width", "0"))
                    height = int(row.get("height", "0"))
                except ValueError:
                    continue

                prefix = token[:match.start()].strip()
                suffix = token[match.end():].strip()
                parenthesized = prefix.endswith("(") or suffix.startswith(")") or suffix.endswith(")")
                survey_annotated = any(
                    pattern.search(token)
                    for pattern in SURVEY_ANNOTATION_PATTERNS
                )
                if confidence < 40 and not (parenthesized or keyword_context or survey_annotated):
                    continue
                if self.ocr_value_range is not None:
                    min_value, max_value = self.ocr_value_range
                    if not min_value <= value <= max_value:
                        continue
                if len(tokens) > 4 and not parenthesized and not keyword_context:
                    continue

                center_x = (left + (width / 2.0)) / scale
                center_y = (top + (height / 2.0)) / scale

                points.append(
                    Point3D(
                        x=center_x,
                        y=max(page_height - center_y, 0.0),
                        z=value,
                    )
                )

        return points

    def _read_ocr_tsv(self, tsv_path: Path) -> List[dict]:
        """Read Tesseract TSV output defensively."""
        with tsv_path.open("r", encoding="utf-8", errors="ignore") as tsv_file:
            lines = [line.rstrip("\n") for line in tsv_file]

        if not lines:
            return []

        headers = lines[0].split("\t")
        rows = []

        for line in lines[1:]:
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) < len(headers) - 1:
                continue

            row = {header: parts[index] if index < len(parts) else "" for index, header in enumerate(headers[:-1])}
            row[headers[-1]] = "\t".join(parts[len(headers) - 1:]) if len(parts) >= len(headers) else ""
            rows.append(row)

        return rows
