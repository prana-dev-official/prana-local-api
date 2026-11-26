"""Switch types accepted by the device API."""

from __future__ import annotations

from ._str_enum import PranaStrEnum


class PranaSwitchType(PranaStrEnum):
    """On/off modes toggled with ``/setSwitch``.

    Not every model has every switch: Prana Neo has no ``HEATER`` and no ``BOOST``.
    """

    BOUND = "bound"
    HEATER = "heater"
    NIGHT = "night"
    BOOST = "boost"
    AUTO = "auto"  # "Auto turbo" on Prana Neo
    AUTO_PLUS = "auto_plus"  # "Auto comfort" on Prana Neo
    WINTER = "winter"
