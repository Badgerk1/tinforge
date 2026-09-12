"""Base point parser interface."""

from abc import ABC, abstractmethod
from typing import List
from ..core.tin_model import Point3D


class PointParser(ABC):
    """Abstract base class for point parsers."""
    
    @abstractmethod
    def parse(self, source: str) -> List[Point3D]:
        """
        Parse point data from source.
        
        Args:
            source: File path or data string
            
        Returns:
            List of Point3D objects
        """
        pass
    
    def validate_points(self, points: List[Point3D]) -> bool:
        """Validate parsed points."""
        if not points:
            return False
        if len(points) < 3:
            return False
        return all(self._validate_point(p) for p in points)
    
    def _validate_point(self, point: Point3D) -> bool:
        """Validate individual point."""
        return (
            isinstance(point.x, (int, float)) and
            isinstance(point.y, (int, float)) and
            isinstance(point.z, (int, float)) and
            not any(math.isnan(v) for v in [point.x, point.y, point.z])
        )


import math
