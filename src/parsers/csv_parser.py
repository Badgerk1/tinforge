"""CSV/TXT point data parser."""

import csv
from typing import List
from ..core.tin_model import Point3D
from .point_parser import PointParser


class CSVParser(PointParser):
    """Parse survey points from CSV/TXT files."""
    
    def __init__(self, delimiter: str = ',', skip_header: bool = True):
        """
        Initialize CSV parser.
        
        Args:
            delimiter: Field delimiter (comma, tab, etc.)
            skip_header: Skip first row if True
        """
        self.delimiter = delimiter
        self.skip_header = skip_header
    
    def parse(self, filepath: str) -> List[Point3D]:
        """
        Parse points from CSV file.
        
        Expected format: ID, X, Y, Z, [Description], [Code]
        or: X, Y, Z
        
        Args:
            filepath: Path to CSV file
            
        Returns:
            List of Point3D objects
        """
        points = []
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.reader(f, delimiter=self.delimiter)
                
                # Skip header if specified
                if self.skip_header:
                    next(reader, None)
                
                for row_idx, row in enumerate(reader, start=1):
                    # Skip empty rows
                    if not row or all(not cell.strip() for cell in row):
                        continue
                    
                    try:
                        point = self._parse_row(row, row_idx)
                        if point:
                            points.append(point)
                    except ValueError as e:
                        print(f"Warning: Skipping row {row_idx}: {e}")
                        continue
        
        except FileNotFoundError:
            raise FileNotFoundError(f"CSV file not found: {filepath}")
        except Exception as e:
            raise RuntimeError(f"Error parsing CSV file: {e}")
        
        if not self.validate_points(points):
            raise ValueError("Parsed points validation failed")
        
        return points
    
    def _parse_row(self, row: list, row_idx: int) -> Point3D:
        """
        Parse single CSV row.
        
        Args:
            row: CSV row as list of strings
            row_idx: Row number for error reporting
            
        Returns:
            Point3D object
        """
        # Filter out empty cells
        row = [cell.strip() for cell in row if cell.strip()]
        
        if len(row) < 3:
            raise ValueError(f"Insufficient columns. Expected at least 3, got {len(row)}")
        
        # Try parsing as: ID, X, Y, Z
        if len(row) >= 4:
            try:
                point_id = int(row[0])
                x = float(row[1])
                y = float(row[2])
                z = float(row[3])
                description = row[4] if len(row) > 4 else None
                code = row[5] if len(row) > 5 else None
                
                return Point3D(
                    x=x, y=y, z=z,
                    id=point_id,
                    description=description,
                    code=code
                )
            except (ValueError, IndexError):
                pass
        
        # Try parsing as: X, Y, Z
        if len(row) >= 3:
            try:
                x = float(row[0])
                y = float(row[1])
                z = float(row[2])
                return Point3D(x=x, y=y, z=z, id=row_idx)
            except ValueError as e:
                raise ValueError(f"Could not parse coordinates: {e}")
        
        raise ValueError("Could not parse row format")
