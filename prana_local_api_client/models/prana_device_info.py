from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Optional

@dataclass
class PranaDeviceInfo:
    manufactureId: str
    isValid: bool
    fwVersion: int
    pranaModel: str
    label: str = field(default="")

    def __post_init__(self) -> None:
        if isinstance(self.label, str):
            self.label = self.label.rstrip()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PranaDeviceInfo":
        def _to_int(value: Any, default: int = 0) -> int:
            if value is None:
                return default
            if isinstance(value, int):
                return value
            if isinstance(value, bytes):
                try:
                    return int.from_bytes(value, byteorder="big")
                except Exception:
                    return default
            if isinstance(value, str):
                try:
                    # handle hex strings like "0x02" or plain numeric strings
                    return int(value, 0)
                except Exception:
                    return default
            try:
                return int(value)
            except Exception:
                return default

        model_byte = _to_int(data.get("pranaModel", 0))
        subtype_byte = _to_int(data.get("pranaSubtype", 0))

        return cls(
            manufactureId=str(data.get("manufactureId", "")),
            isValid=bool(data.get("isValid", False)),
            fwVersion=_to_int(data.get("fwVersion", 0)),
            pranaModel=cls._get_model_by_byte(model_byte=model_byte, subtype_byte=subtype_byte),
            label=str(data.get("label", "")),
        )

    @staticmethod
    def _get_model_by_byte(model_byte: int, subtype_byte: Optional[int]) -> str:
        # mapping for known (model, subtype) combinations
        MODEL_DEFAULT = "PRANA RECUPERATOR 200"
        MODEL_MAP = {
            (0x04, None): "PRANA RECUPERATOR 340",
            (0x02, 0x00): "PRANA RECUPERATOR 150",
            (0x02, 0x01): "PRANA RECUPERATOR 200C",
            (0x02, 0x02): "PRANA RECUPERATOR 200G",
            (0x02, 0x03): "PRANA RECUPERATOR 162",
            (0x02, 0x04): "PRANA RECUPERATOR 212C",
            (0x02, 0x05): "PRANA RECUPERATOR 212G",
        }

        # try exact match (model, subtype)
        key = (model_byte, subtype_byte)
        if key in MODEL_MAP:
            return MODEL_MAP[key]

        # try (model, None) fallback
        key_default = (model_byte, None)
        return MODEL_MAP.get(key_default, MODEL_DEFAULT)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
