"""Position-based modes (Prana Neo only)."""

from __future__ import annotations

from ._str_enum import PranaStrEnum


class PranaPositionType(PranaStrEnum):
    """Prana Neo modes set with ``/setPosition`` (0 = off, 1-3 = position)."""

    FRESH_AIR = "fresh_air"
    EXTRACT = "extract"
