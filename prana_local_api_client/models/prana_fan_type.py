"""Fan (motor) types accepted by the device API."""

from __future__ import annotations

from ._str_enum import PranaStrEnum


class PranaFanType(PranaStrEnum):
    """Motor addressed by speed commands."""

    SUPPLY = "supply"
    EXTRACT = "extract"
    # Both motors together while the device is in bound mode.
    BOUNDED = "bounded"
