import logging
from enum import Enum
from typing import Any, Dict, Optional, Tuple

from .exceptions import (
    PranaApiUpdateFailed,
    PranaApiCommunicationError,
    UpdateFailed,
)

_LOGGER = logging.getLogger(__name__)

class PranaFanType(str, Enum):
    BOUNDED = "bounded"
    SUPPLY = "supply"
    EXTRACT = "extract"

class PranaSensorType(str, Enum):
    INSIDE_TEMPERATURE = "inside_temperature"
    OUTSIDE_TEMPERATURE = "outside_temperature"
    INSIDE_TEMPERATURE_2 = "inside_temperature_2"
    OUTSIDE_TEMPERATURE_2 = "outside_temperature_2"

def normalize_state(raw_state: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a raw state dict in-place and return it."""
    state = dict(raw_state) if isinstance(raw_state, dict) else {}
    # Compute normalized max_speed from extract fan if present
    max_speed: Optional[int] = None
    try:
        extract = state.get(PranaFanType.EXTRACT.value)
        if isinstance(extract, dict) and "max_speed" in extract:
            raw_val = extract.get("max_speed")
            if isinstance(raw_val, (int, float)):
                max_speed = int(raw_val) // 10
    except Exception:
        _LOGGER.exception("Error computing max_speed from state")

    if max_speed is not None:
        for fan in (PranaFanType.BOUNDED.value, PranaFanType.SUPPLY.value, PranaFanType.EXTRACT.value):
            if fan in state and isinstance(state[fan], dict):
                state[fan]["max_speed"] = max_speed

    for temp_key in (
        PranaSensorType.INSIDE_TEMPERATURE.value,
        PranaSensorType.OUTSIDE_TEMPERATURE.value,
        PranaSensorType.INSIDE_TEMPERATURE_2.value,
        PranaSensorType.OUTSIDE_TEMPERATURE_2.value,
    ):
        if temp_key in state and isinstance(state[temp_key], (int, float)):
            try:
                state[temp_key] = state[temp_key] / 10
            except Exception:
                _LOGGER.exception("Error converting temperature for key %s", temp_key)

    return state

async def fetch_and_normalize_state(api_client) -> Tuple[Dict[str, Any], Optional[int]]:
    """
    Fetch state from api_client and normalize it:
    - map errors to UpdateFailed
    - compute and propagate max_speed
    - convert temperature sensors from tenths of °C -> °C
    Returns (state, max_speed) where max_speed may be None if not available.
    """
    _LOGGER.debug("Fetching data from Prana device")

    try:
        # Prefer an internal raw fetcher to avoid recursion; fallback to get_state if not available
        raw_fetch = getattr(api_client, "_get_raw_state", None)
        if raw_fetch is None:
            # fallback (may raise or cause recursion if client.get_state delegates here)
            raw = await api_client.get_state()
        else:
            print("Using internal raw fetcher")
            raw = await raw_fetch()
    except PranaApiUpdateFailed as err:
        raise UpdateFailed(f"HTTP error communicating with device: {err}") from err
    except PranaApiCommunicationError as err:
        raise UpdateFailed(f"Network error communicating with device: {err}") from err
    except Exception as err:
        raise UpdateFailed(f"Unexpected error updating device: {err}") from err

    if not isinstance(raw, dict):
        _LOGGER.debug("Received non-dict state: %s", raw)
        return {}, None

    # Normalize and compute max_speed
    normalized = normalize_state(raw)
    max_speed = None
    try:
        extract = raw.get(PranaFanType.EXTRACT.value)
        if isinstance(extract, dict) and "max_speed" in extract:
            raw_val = extract.get("max_speed")
            if isinstance(raw_val, (int, float)):
                max_speed = int(raw_val) // 10
    except Exception:
        _LOGGER.exception("Error computing max_speed from state")

    _LOGGER.debug("Fetched state: %s", normalized)
    return normalized, max_speed
