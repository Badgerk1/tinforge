"""Backward-compatible surface model."""

from .tin_model import TINModel


class Surface(TINModel):
    """Surface compatibility wrapper around TINModel."""

