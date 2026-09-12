"""Delaunay Triangulation Engine for TIN generation."""

import numpy as np
from scipy.spatial import Delaunay
from typing import List, Tuple
from .tin_model import Point3D, Triangle, TINModel


class DelaunayTriangulator:
    """Generate Delaunay triangulation from survey points."""
    
    def __init__(self, points: List[Point3D]):
        """
        Initialize triangulator with survey points.
        
        Args:
            points: List of Point3D objects with X, Y, Z coordinates
        """
        if len(points) < 3:
            raise ValueError("At least 3 points required for triangulation")
        
        self.points = points
        self.triangles = []
        self.tin_model = None
    
    def triangulate(self) -> TINModel:
        """
        Generate Delaunay triangulation from points.
        
        Returns:
            TINModel: Generated TIN surface model
        """
        # Extract 2D coordinates (X, Y) for triangulation
        coords_2d = np.array([(p.x, p.y) for p in self.points])
        
        # Perform Delaunay triangulation
        delaunay = Delaunay(coords_2d)
        
        # Convert scipy simplices to Triangle objects
        self.triangles = []
        for simplex in delaunay.simplices:
            # Each simplex is a triangle defined by 3 point indices
            p1 = self.points[simplex[0]]
            p2 = self.points[simplex[1]]
            p3 = self.points[simplex[2]]
            
            triangle = Triangle(
                point1=p1,
                point2=p2,
                point3=p3,
                id=len(self.triangles) + 1
            )
            self.triangles.append(triangle)
        
        # Create TIN model
        self.tin_model = TINModel(
            points=self.points,
            triangles=self.triangles,
            name="Delaunay TIN"
        )
        
        return self.tin_model
    
    def add_breaklines(self, breaklines: List[List[Point3D]]) -> TINModel:
        """
        Add breaklines (ridges, edges, ditches) to TIN.
        
        Args:
            breaklines: List of breakline point sequences
            
        Returns:
            TINModel: Updated TIN model with breaklines
        """
        if self.tin_model is None:
            raise RuntimeError("Must call triangulate() first")
        
        for breakline in breaklines:
            self.tin_model.add_breakline(breakline)
        
        return self.tin_model
    
    def add_boundary(self, boundary_points: List[Point3D]) -> TINModel:
        """
        Define survey area boundary.
        
        Args:
            boundary_points: Points defining the survey boundary polygon
            
        Returns:
            TINModel: Updated TIN model with boundary
        """
        if self.tin_model is None:
            raise RuntimeError("Must call triangulate() first")
        
        self.tin_model.set_boundary(boundary_points)
        return self.tin_model
    
    def get_statistics(self) -> dict:
        """
        Get triangulation statistics.
        
        Returns:
            dict: Statistics including point count, triangle count, bounds
        """
        if not self.points:
            return {}
        
        x_coords = [p.x for p in self.points]
        y_coords = [p.y for p in self.points]
        z_coords = [p.z for p in self.points]
        
        return {
            'point_count': len(self.points),
            'triangle_count': len(self.triangles),
            'bounds': {
                'x_min': min(x_coords),
                'x_max': max(x_coords),
                'y_min': min(y_coords),
                'y_max': max(y_coords),
                'z_min': min(z_coords),
                'z_max': max(z_coords),
            },
            'area': self._calculate_area(),
        }
    
    def _calculate_area(self) -> float:
        """Calculate total area covered by triangles."""
        total_area = 0.0
        for triangle in self.triangles:
            total_area += triangle.get_area_2d()
        return total_area
