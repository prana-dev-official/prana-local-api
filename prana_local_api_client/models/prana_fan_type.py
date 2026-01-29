from enum import Enum


class PranaFanType(str, Enum):
    """Enumeration of Prana fan types."""

    SUPPLY = "supply"
    EXTRACT = "extract"
    BOUNDED = "bounded"