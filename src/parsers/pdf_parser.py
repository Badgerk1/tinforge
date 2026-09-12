"""PDF point data parser."""

import re
import shutil
import subprocess
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional
from ..core.tin_model import Point3D
from .point_parser import PointParser
from .tp3_parser import extract_binary_topcon_tp3_points


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
        self.last_parse_details: Dict[str, object] = {}
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
        pdf_path = Path(filepath)
        self.last_parse_details = {
            "source": "empty",
            "point_count": 0,
            "companion_tp3_path": None,
        }
        
        try:
            with self.pdfplumber.open(filepath) as pdf:
                pdf_metrics, page_texts = self._collect_pdf_metrics(pdf.pages)
                companion_tp3_path = self._find_companion_tp3(pdf_path, pdf.pages, page_texts)
                self.last_parse_details.update(pdf_metrics)
                self.last_parse_details["companion_tp3_path"] = (
                    str(companion_tp3_path) if companion_tp3_path else None
                )
                found_table_points = False
                found_text_points = False

                for page_idx, page in enumerate(pdf.pages):
                    page_points = []

                    # Try to extract table data
                    tables = page.extract_tables()
                    if tables:
                        for table in tables:
                            table_points = self._extract_from_table(table, page_idx)
                            if table_points:
                                found_table_points = True
                                page_points.extend(table_points)

                    # Also try to extract text and find coordinates
                    text = page_texts[page_idx]
                    if text:
                        text_points = self._extract_from_text(text, page_idx)
                        if text_points:
                            found_text_points = True
                            page_points.extend(text_points)

                    points.extend(page_points)

                points = self._normalize_points(points)
                if companion_tp3_path and self._should_use_companion_tp3_fallback(points, pdf_metrics):
                    points = self._extract_from_companion_tp3(companion_tp3_path)
                    self.last_parse_details["source"] = "companion_tp3"
                elif points:
                    self.last_parse_details["source"] = self._resolve_pdf_text_source(
                        found_table_points,
                        found_text_points,
                    )
                elif self._should_skip_ocr(pdf_metrics, companion_tp3_path):
                    points = []
                    self.last_parse_details["source"] = "empty_reference_sheet"
                elif shutil.which("tesseract"):
                    for page_idx, page in enumerate(pdf.pages):
                        points.extend(self._extract_from_ocr(page, page_idx))
                    points = self._normalize_points(points)
                    if points:
                        self.last_parse_details["source"] = "ocr"
                else:
                    points = []
                    self.last_parse_details["source"] = "ocr_unavailable"

        except FileNotFoundError:
            raise FileNotFoundError(f"PDF file not found: {filepath}")
        except (RuntimeError, ValueError):
            raise
        except Exception as e:
            raise RuntimeError(f"Error parsing PDF: {e}")

        if points and not all(self._validate_point(point) for point in points):
            raise ValueError("Extracted points validation failed")

        self.last_parse_details["point_count"] = len(points)
        return points

    def _collect_pdf_metrics(self, pages: List[object]) -> tuple[Dict[str, int], List[str]]:
        """Capture PDF metrics and cache per-page text used during extraction."""
        metrics = {
            "page_count": len(pages),
            "image_count": 0,
            "vector_object_count": 0,
            "annotation_count": 0,
            "text_page_count": 0,
        }
        page_texts: List[str] = []

        for page in pages:
            metrics["image_count"] += len(getattr(page, "images", []))
            metrics["vector_object_count"] += (
                len(getattr(page, "lines", []))
                + len(getattr(page, "curves", []))
                + len(getattr(page, "rects", []))
            )
            metrics["annotation_count"] += len(getattr(page, "annots", []) or [])
            page_text = (page.extract_text() or "").strip()
            page_texts.append(page_text)
            if page_text:
                metrics["text_page_count"] += 1

        return metrics, page_texts

    def _find_companion_tp3(
        self,
        pdf_path: Path,
        pages: List[object],
        page_texts: Optional[List[str]] = None,
    ) -> Optional[Path]:
        """Locate the most plausible TP3 companion that ships alongside the PDF survey bundle."""
        candidates = sorted(
            path for path in pdf_path.parent.iterdir()
            if path.is_file() and path.suffix.lower() == ".tp3"
        )
        if not candidates:
            return None

        context_tokens = set(self._tokenize_name(pdf_path.stem))
        context_tokens.update(self._collect_context_tokens_from_pages(pages, page_texts))
        matched_candidate = self._select_candidate_tp3(candidates, context_tokens)
        if matched_candidate is not None:
            return matched_candidate
        if len(candidates) == 1:
            return self._match_single_tp3_from_sibling_bundle(pdf_path, candidates[0], context_tokens)
        return None

    def _tokenize_name(self, value: str) -> List[str]:
        """Split a file name or annotation into comparable lowercase tokens."""
        return [
            token
            for token in re.findall(r"[A-Za-z0-9]+", value.lower())
            if len(token) >= 3
        ]

    def _collect_context_tokens_from_pages(
        self,
        pages: List[object],
        page_texts: Optional[List[str]] = None,
    ) -> List[str]:
        """Collect comparable tokens from page text and annotation contents."""
        tokens: List[str] = []
        for page_idx, page in enumerate(pages):
            if page_texts is not None and page_idx < len(page_texts):
                tokens.extend(self._tokenize_name(page_texts[page_idx]))
            for annot in getattr(page, "annots", []) or []:
                tokens.extend(self._tokenize_name(annot.get("contents") or ""))
        return tokens

    def _select_candidate_tp3(self, candidates: List[Path], context_tokens: set[str]) -> Optional[Path]:
        """Select a TP3 only when it has a unique positive token overlap with the PDF context."""
        scored_candidates = []
        for candidate in candidates:
            candidate_tokens = set(self._tokenize_name(candidate.stem))
            score = len(candidate_tokens & context_tokens)
            scored_candidates.append((score, candidate))

        scored_candidates.sort(key=lambda item: item[0], reverse=True)
        if scored_candidates[0][0] <= 0:
            return None
        if len(scored_candidates) == 1 or scored_candidates[0][0] > scored_candidates[1][0]:
            return scored_candidates[0][1]
        return None

    def _match_single_tp3_from_sibling_bundle(
        self,
        pdf_path: Path,
        candidate: Path,
        current_context_tokens: set[str],
    ) -> Optional[Path]:
        """Allow a raster reference sheet to inherit a single TP3 match from a sibling survey PDF."""
        current_name_tokens = set(self._tokenize_name(pdf_path.stem))
        for sibling_pdf in sorted(pdf_path.parent.glob("*.pdf")):
            if sibling_pdf == pdf_path:
                continue
            sibling_name_tokens = set(self._tokenize_name(sibling_pdf.stem))
            if not (current_name_tokens & sibling_name_tokens):
                continue
            try:
                with self.pdfplumber.open(sibling_pdf) as sibling:
                    _, sibling_page_texts = self._collect_pdf_metrics(sibling.pages)
                    sibling_tokens = sibling_name_tokens | set(
                        self._collect_context_tokens_from_pages(sibling.pages, sibling_page_texts)
                    )
            except Exception:
                continue
            if self._select_candidate_tp3([candidate], sibling_tokens) == candidate:
                return candidate
        return None

    def _resolve_pdf_text_source(self, found_table_points: bool, found_text_points: bool) -> str:
        """Describe which native PDF extraction paths produced survey points."""
        if found_table_points and found_text_points:
            return "pdf_table+text"
        if found_table_points:
            return "pdf_table"
        return "pdf_text"

    def _should_use_companion_tp3_fallback(
        self,
        points: List[Point3D],
        pdf_metrics: Dict[str, int],
    ) -> bool:
        """Use the manual TP3 when a vector-heavy survey PDF yields only sparse points."""
        return (
            pdf_metrics["vector_object_count"] >= 1000
            and pdf_metrics["text_page_count"] == 0
            and len(points) < 100
        )

    def _should_skip_ocr(
        self,
        pdf_metrics: Dict[str, int],
        companion_tp3_path: Optional[Path],
    ) -> bool:
        """Skip OCR on reference sheets that only accompany a richer survey drawing."""
        return (
            companion_tp3_path is not None
            and pdf_metrics["vector_object_count"] < 100
            and pdf_metrics["annotation_count"] == 0
            and pdf_metrics["image_count"] > 0
            and pdf_metrics["text_page_count"] == 0
        )

    def _extract_from_companion_tp3(self, tp3_path: Path) -> List[Point3D]:
        """Load points from a co-located manual Topcon TP3 file."""
        return self._normalize_points(extract_binary_topcon_tp3_points(tp3_path))
    
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
                if confidence < 40:
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
