"""Versioned Otomoto parser package."""

from .otomoto_vehicle_identity import fetch_otomoto_vehicle_identity
from .v1.parser import parse_pages

__all__ = ["fetch_otomoto_vehicle_identity", "parse_pages"]
