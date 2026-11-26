"""Device state returned by ``GET /getState``."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

# The device reports speeds and temperatures scaled by 10.
_SCALE = 10


def _optional_int(data: dict[str, Any], key: str) -> int | None:
    """Return ``data[key]`` as int, or None when the device does not report it."""
    value = data.get(key)
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_temperature(data: dict[str, Any], key: str) -> float | None:
    """Return a temperature in °C (device reports tenths of °C), or None."""
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) / _SCALE


@dataclass
class FanState:
    """State of one motor (supply, extract or both together when bound).

    ``speed`` and ``max_speed`` are speed steps (e.g. 1..7). In Prana Neo
    Fresh air / Extract mode the forced motor reports ``max_speed + 1``.
    """

    speed: int
    is_on: bool
    max_speed: int

    @classmethod
    def from_dict(cls, data: dict[str, Any], max_speed: int | None = None) -> FanState:
        """Build from a fan object of ``/getState``.

        The device reports ``max_speed`` in tenths (``70`` -> 7 steps); values
        below 10 are taken as steps already. ``max_speed`` overrides it.
        """
        if max_speed is None:
            raw_max = _optional_int(data, "max_speed") or 0
            max_speed = raw_max // _SCALE if raw_max >= _SCALE else raw_max
        return cls(
            speed=_optional_int(data, "speed") or 0,
            is_on=bool(data.get("is_on", False)),
            max_speed=int(max_speed),
        )


@dataclass
class PranaState:
    """Full device state.

    Optional fields are None when the model does not report them, so callers can
    tell "not supported" apart from a real value.
    """

    extract: FanState
    supply: FanState
    bounded: FanState

    bound: bool
    heater: bool
    auto: bool
    auto_plus: bool
    winter: bool
    brightness: int  # display brightness level 0..6
    night: bool
    boost: bool

    # Sensors (temperatures in °C).
    inside_temperature: float | None = None
    outside_temperature: float | None = None
    inside_temperature_2: float | None = None
    outside_temperature_2: float | None = None
    humidity: int | None = None
    co2: int | None = None
    voc: int | None = None
    air_pressure: int | None = None

    # Prana Neo only: Fresh air / Extract mode position (0 = off, 1-3).
    fresh_air_position: int | None = None
    extract_position: int | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any], max_speed: int | None = None) -> PranaState:
        """Build from the ``/getState`` JSON payload."""
        return cls(
            extract=FanState.from_dict(data.get("extract") or {}, max_speed),
            supply=FanState.from_dict(data.get("supply") or {}, max_speed),
            bounded=FanState.from_dict(data.get("bounded") or {}, max_speed),
            bound=bool(data.get("bound", False)),
            heater=bool(data.get("heater", False)),
            auto=bool(data.get("auto", False)),
            auto_plus=bool(data.get("auto_plus", False)),
            winter=bool(data.get("winter", False)),
            night=bool(data.get("night", False)),
            boost=bool(data.get("boost", False)),
            brightness=_optional_int(data, "brightness") or 0,
            inside_temperature=_optional_temperature(data, "inside_temperature"),
            outside_temperature=_optional_temperature(data, "outside_temperature"),
            inside_temperature_2=_optional_temperature(data, "inside_temperature_2"),
            outside_temperature_2=_optional_temperature(data, "outside_temperature_2"),
            humidity=_optional_int(data, "humidity"),
            co2=_optional_int(data, "co2"),
            voc=_optional_int(data, "voc"),
            air_pressure=_optional_int(data, "air_pressure"),
            fresh_air_position=_optional_int(data, "fresh_air_position"),
            extract_position=_optional_int(data, "extract_position"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return the fields as a plain (nested) dict."""
        return asdict(self)
