"""Version 1 parser implementation."""

from .otomoto_vehicle_identity import fetch_otomoto_vehicle_identity
from .parser import parse_pages

__all__ = ["fetch_otomoto_vehicle_identity", "parse_pages"]
