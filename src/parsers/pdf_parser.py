"""PDF point data parser."""

import re
from typing import List, Optional
from ..core.tin_model import Point3D
from .point_parser import PointParser


class PDFParser(PointParser):
    """Extract survey points from PDF documents."""
    
    def __init__(self):
        """Initialize PDF parser."""
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
                    # Try to extract table data
                    tables = page.extract_tables()
                    if tables:
                        for table in tables:
                            page_points = self._extract_from_table(table, page_idx)
                            points.extend(page_points)
                    
                    # Also try to extract text and find coordinates
                    text = page.extract_text()
                    if text:
                        text_points = self._extract_from_text(text, page_idx)
                        points.extend(text_points)
        
        except FileNotFoundError:
            raise FileNotFoundError(f"PDF file not found: {filepath}")
        except Exception as e:
            raise RuntimeError(f"Error parsing PDF: {e}")
        
        if not self.validate_points(points):
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
