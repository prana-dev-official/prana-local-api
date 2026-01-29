from enum import Enum


class PranaSwitchType(str, Enum):
    """Prana Switch Type Enum."""

    BOUND = "bound"
    HEATER = "heater"
    NIGHT = "night"
    BOOST = "boost"
    AUTO = "auto"
    AUTO_PLUS = "auto_plus"
    WINTER = "winter"