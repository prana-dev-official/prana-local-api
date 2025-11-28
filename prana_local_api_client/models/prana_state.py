from dataclasses import dataclass
from typing import Optional, Any, Dict


@dataclass
class FanState:
    speed: int
    is_on: bool
    max_speed: int

    @classmethod
    def from_dict(cls, data: Dict[str, Any], max_speed: Optional[int] = None) -> "FanState":
        # If max_speed provided, use it; otherwise try to derive from data (raw device may be in tenths)
        if max_speed is None:
            raw_max = data.get("max_speed", 0)
            try:
                # If raw_max is in tenths (e.g. 100 -> 10), convert; otherwise fallback to int
                max_val = int(raw_max) // 10 if isinstance(raw_max, (int, float)) and int(raw_max) >= 10 else int(raw_max or 0)
            except Exception:
                max_val = int(raw_max or 0)
        else:
            max_val = int(max_speed)

        return cls(
            speed=int(data.get("speed", 0)),
            is_on=bool(data.get("is_on", False)),
            max_speed=max_val,
        )


@dataclass
class PranaState:
    extract: FanState
    supply: FanState
    bounded: FanState

    bound: bool
    heater: bool
    auto: bool
    auto_plus: bool
    winter: bool
    brightness: int

    # Optional (positional / not required) environmental sensors
    inside_temperature: Optional[float] = None
    outside_temperature: Optional[float] = None
    inside_temperature_2: Optional[float] = None
    outside_temperature_2: Optional[float] = None
    humidity: Optional[int] = None
    co2: Optional[int] = None
    voc: Optional[int] = None
    air_pressure: Optional[int] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any], max_speed: Optional[int] = None) -> "PranaState":
        # Build nested FanState objects, passing computed max_speed if available
        extract = FanState.from_dict(data.get("extract", {}), max_speed=max_speed)
        supply = FanState.from_dict(data.get("supply", {}), max_speed=max_speed)
        bounded = FanState.from_dict(data.get("bounded", {}), max_speed=max_speed)

        def parse_temp(key: str) -> Optional[float]:
            if key in data and isinstance(data[key], (int, float)):
                try:
                    return float(data[key]) / 10.0  # device reports tenths of °C
                except Exception:
                    return None
            return None

        return cls(
            extract=extract,
            supply=supply,
            bounded=bounded,
            bound=bool(data.get("bound", False)),
            heater=bool(data.get("heater", False)),
            auto=bool(data.get("auto", False)),
            auto_plus=bool(data.get("auto_plus", False)),
            winter=bool(data.get("winter", False)),
            brightness=int(data.get("brightness", 0)),
            inside_temperature=parse_temp("inside_temperature"),
            outside_temperature=parse_temp("outside_temperature"),
            inside_temperature_2=parse_temp("inside_temperature_2"),
            outside_temperature_2=parse_temp("outside_temperature_2"),
            humidity=(None if "humidity" not in data else int(data["humidity"])),
            co2=(None if "co2" not in data else int(data["co2"])),
            voc=(None if "voc" not in data else int(data["voc"])),
            air_pressure=(None if "air_pressure" not in data else int(data["air_pressure"])),
        )
