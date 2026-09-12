"""Core TinForge modules for TIN generation and surface processing."""

from .triangulation import DelaunayTriangulator
from .tin_model import TINModel, Point3D, Triangle

Surface = TINModel

__all__ = [
    'DelaunayTriangulator',
    'TINModel',
    'Point3D',
    'Triangle',
    'Surface',
]
