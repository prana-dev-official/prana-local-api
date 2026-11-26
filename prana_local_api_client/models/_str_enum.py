"""String enum base shared by the public enums."""

from __future__ import annotations

from enum import Enum


class PranaStrEnum(str, Enum):
    """``str`` enum whose ``str()`` and f-string form is the raw value.

    ``enum.StrEnum`` needs Python 3.11; this keeps 3.10 support while making
    ``f"{PranaFanType.SUPPLY}"`` give ``"supply"`` rather than the member name.
    """

    def __str__(self) -> str:
        """Return the raw value."""
        return str(self.value)
