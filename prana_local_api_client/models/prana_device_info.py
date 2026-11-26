"""Device information returned by ``GET /info``."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

#: Raw ``pranaModel`` byte of a Prana Neo.
PRANA_NEO_MODEL_ID = 0x05

#: Model name used when the (model, subtype) bytes are unknown.
DEFAULT_MODEL_NAME = "PRANA RECUPERATOR 200"

# (model byte, subtype byte) -> name. A ``None`` subtype matches any subtype.
_MODEL_NAMES: dict[tuple[int, int | None], str] = {
    (0x02, 0x00): "PRANA RECUPERATOR 150",
    (0x02, 0x01): "PRANA RECUPERATOR 200C",
    (0x02, 0x02): "PRANA RECUPERATOR 200G",
    (0x02, 0x03): "PRANA RECUPERATOR 162",
    (0x02, 0x04): "PRANA RECUPERATOR 212C",
    (0x02, 0x05): "PRANA RECUPERATOR 212G",
    (0x04, None): "PRANA RECUPERATOR 340",
    (PRANA_NEO_MODEL_ID, None): "PRANA NEO",
}


def model_name(model_id: int, subtype_id: int | None = None) -> str:
    """Return the human-readable model name for the raw model/subtype bytes."""
    return _MODEL_NAMES.get(
        (model_id, subtype_id), _MODEL_NAMES.get((model_id, None), DEFAULT_MODEL_NAME)
    )


def _to_int(value: Any, default: int = 0) -> int:
    """Convert a device value (int, numeric/hex string or bytes) to ``int``."""
    if isinstance(value, bool) or value is None:
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, (bytes, bytearray)):
        return int.from_bytes(value, byteorder="big") if value else default
    if isinstance(value, str):
        try:
            return int(value.strip(), 0)  # accepts "5", "0x05"
        except ValueError:
            return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@dataclass
class PranaDeviceInfo:
    """Static information about a device.

    Field names mirror the device JSON (camelCase) for backwards compatibility.
    """

    manufactureId: str  # noqa: N815 - serial number, used as unique ID
    isValid: bool  # noqa: N815
    fwVersion: int  # noqa: N815
    pranaModel: str  # noqa: N815 - human-readable name, see model_name()
    label: str = ""
    #: Raw model byte reported by the device (``PRANA_NEO_MODEL_ID`` for Neo).
    model_id: int = field(default=0)

    def __post_init__(self) -> None:
        """Strip the padding the firmware adds to the label."""
        self.label = self.label.rstrip()

    @property
    def is_neo(self) -> bool:
        """Return True if the device is a Prana Neo."""
        return self.model_id == PRANA_NEO_MODEL_ID

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PranaDeviceInfo:
        """Build from the ``/info`` JSON payload."""
        model_id = _to_int(data.get("pranaModel"))
        subtype_id = _to_int(data.get("pranaSubtype"))
        return cls(
            manufactureId=str(data.get("manufactureId", "")),
            isValid=bool(data.get("isValid", False)),
            fwVersion=_to_int(data.get("fwVersion")),
            pranaModel=model_name(model_id, subtype_id),
            label=str(data.get("label", "")),
            model_id=model_id,
        )

    def to_dict(self) -> dict[str, Any]:
        """Return the fields as a plain dict."""
        return asdict(self)
