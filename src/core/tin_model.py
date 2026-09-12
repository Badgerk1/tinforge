"""TIN Data Model and Structure."""

from typing import List, Optional
from dataclasses import dataclass
import math


@dataclass
class Point3D:
    """3D point with X, Y, Z coordinates."""
    x: float
    y: float
    z: float
    id: Optional[int] = None
    description: Optional[str] = None
    code: Optional[str] = None
    
    def distance_to(self, other: 'Point3D') -> float:
        """Calculate 3D distance to another point."""
        return math.sqrt(
            (self.x - other.x)**2 + 
            (self.y - other.y)**2 + 
            (self.z - other.z)**2
        )
    
    def distance_2d(self, other: 'Point3D') -> float:
        """Calculate 2D distance (X, Y only) to another point."""
        return math.sqrt(
            (self.x - other.x)**2 + 
            (self.y - other.y)**2
        )
    
    def __repr__(self) -> str:
        return f"Point3D(id={self.id}, x={self.x:.2f}, y={self.y:.2f}, z={self.z:.2f})"


@dataclass
class Triangle:
    """Triangle face in TIN mesh defined by 3 points."""
    point1: Point3D
    point2: Point3D
    point3: Point3D
    id: Optional[int] = None
    
    def get_area_2d(self) -> float:
        """Calculate 2D area using cross product."""
        x1, y1 = self.point1.x, self.point1.y
        x2, y2 = self.point2.x, self.point2.y
        x3, y3 = self.point3.x, self.point3.y
        
        return abs((x2 - x1) * (y3 - y1) - (x3 - x1) * (y2 - y1)) / 2.0
    
    def get_centroid(self) -> Point3D:
        """Get triangle centroid."""
        cx = (self.point1.x + self.point2.x + self.point3.x) / 3.0
        cy = (self.point1.y + self.point2.y + self.point3.y) / 3.0
        cz = (self.point1.z + self.point2.z + self.point3.z) / 3.0
        return Point3D(x=cx, y=cy, z=cz)
    
    def interpolate_z(self, x: float, y: float) -> float:
        """Interpolate Z value at X, Y location using barycentric coordinates."""
        x1, y1, z1 = self.point1.x, self.point1.y, self.point1.z
        x2, y2, z2 = self.point2.x, self.point2.y, self.point2.z
        x3, y3, z3 = self.point3.x, self.point3.y, self.point3.z
        
        denom = (y2 - y3) * (x1 - x3) + (x3 - x2) * (y1 - y3)
        if abs(denom) < 1e-10:
            return (z1 + z2 + z3) / 3.0  # Degenerate triangle
        
        a = ((y2 - y3) * (x - x3) + (x3 - x2) * (y - y3)) / denom
        b = ((y3 - y1) * (x - x3) + (x1 - x3) * (y - y3)) / denom
        c = 1 - a - b
        
        return a * z1 + b * z2 + c * z3
    
    def __repr__(self) -> str:
        return f"Triangle(id={self.id}, points=[{self.point1.id}, {self.point2.id}, {self.point3.id}])"


class TINModel:
    """Triangulated Irregular Network model."""
    
    def __init__(self, points: List[Point3D], triangles: List[Triangle], name: str = "TIN"):
        """
        Initialize TIN model.
        
        Args:
            points: List of 3D points
            triangles: List of triangles connecting points
            name: Model name
        """
        self.name = name
        self.points = points
        self.triangles = triangles
        self.breaklines: List[List[Point3D]] = []
        self.boundary: Optional[List[Point3D]] = None
    
    def add_breakline(self, breakline_points: List[Point3D]) -> None:
        """Add breakline (ridge, edge, ditch) to TIN."""
        if len(breakline_points) < 2:
            raise ValueError("Breakline must have at least 2 points")
        self.breaklines.append(breakline_points)
    
    def set_boundary(self, boundary_points: List[Point3D]) -> None:
        """Set survey area boundary."""
        if len(boundary_points) < 3:
            raise ValueError("Boundary must have at least 3 points")
        self.boundary = boundary_points
    
    def get_elevation_at(self, x: float, y: float) -> Optional[float]:
        """
        Interpolate elevation at given X, Y coordinates.
        
        Args:
            x: X coordinate
            y: Y coordinate
            
        Returns:
            float: Interpolated Z elevation, or None if outside TIN
        """
        for triangle in self.triangles:
            # Simple point-in-triangle check (could be optimized)
            if self._point_in_triangle_2d(x, y, triangle):
                return triangle.interpolate_z(x, y)
        return None
    
    def _point_in_triangle_2d(self, x: float, y: float, triangle: Triangle) -> bool:
        """Check if 2D point is inside triangle using barycentric coordinates."""
        x1, y1 = triangle.point1.x, triangle.point1.y
        x2, y2 = triangle.point2.x, triangle.point2.y
        x3, y3 = triangle.point3.x, triangle.point3.y
        
        denom = (y2 - y3) * (x1 - x3) + (x3 - x2) * (y1 - y3)
        if abs(denom) < 1e-10:
            return False
        
        a = ((y2 - y3) * (x - x3) + (x3 - x2) * (y - y3)) / denom
        b = ((y3 - y1) * (x - x3) + (x1 - x3) * (y - y3)) / denom
        c = 1 - a - b
        
        return (0 <= a <= 1) and (0 <= b <= 1) and (0 <= c <= 1)
    
    def get_statistics(self) -> dict:
        """Get TIN model statistics."""
        if not self.points:
            return {}
        
        x_coords = [p.x for p in self.points]
        y_coords = [p.y for p in self.points]
        z_coords = [p.z for p in self.points]
        
        return {
            'name': self.name,
            'point_count': len(self.points),
            'triangle_count': len(self.triangles),
            'breakline_count': len(self.breaklines),
            'bounds': {
                'x_min': min(x_coords),
                'x_max': max(x_coords),
                'y_min': min(y_coords),
                'y_max': max(y_coords),
                'z_min': min(z_coords),
                'z_max': max(z_coords),
            },
        }
