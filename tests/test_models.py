"""Tests for parsing the device payloads into models."""

from __future__ import annotations

import pytest

from prana_local_api_client import (
    PRANA_NEO_MODEL_ID,
    FanState,
    PranaDeviceInfo,
    PranaFanType,
    PranaPositionType,
    PranaState,
    PranaSwitchType,
)
from prana_local_api_client.models.prana_device_info import DEFAULT_MODEL_NAME, model_name


def _info(**data: object) -> PranaDeviceInfo:
    return PranaDeviceInfo.from_dict({"manufactureId": "X", "isValid": True, **data})


class TestDeviceInfo:
    def test_neo(self) -> None:
        info = _info(pranaModel=5, pranaSubtype=0)
        assert info.is_neo
        assert info.model_id == PRANA_NEO_MODEL_ID
        assert info.pranaModel == "PRANA NEO"

    @pytest.mark.parametrize(
        ("model", "subtype", "name"),
        [
            (0x02, 0x00, "PRANA RECUPERATOR 150"),
            (0x02, 0x01, "PRANA RECUPERATOR 200C"),
            (0x02, 0x05, "PRANA RECUPERATOR 212G"),
            (0x04, 0x07, "PRANA RECUPERATOR 340"),  # any subtype
            (0x02, 0x99, DEFAULT_MODEL_NAME),  # unknown subtype
            (0x00, 0x00, DEFAULT_MODEL_NAME),
            (0x7F, None, DEFAULT_MODEL_NAME),
        ],
    )
    def test_model_names(self, model: int, subtype: int | None, name: str) -> None:
        assert model_name(model, subtype) == name
        assert not _info(pranaModel=model, pranaSubtype=subtype).is_neo

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            (5, 5),
            ("5", 5),
            ("0x05", 5),
            (b"\x05", 5),
            (b"", 0),
            ("junk", 0),
            (None, 0),
            (True, 0),
            (5.0, 5),
            ([1], 0),
        ],
    )
    def test_model_byte_formats(self, raw: object, expected: int) -> None:
        assert _info(pranaModel=raw).model_id == expected

    def test_fields_and_label_padding(self) -> None:
        info = PranaDeviceInfo.from_dict(
            {
                "manufactureId": "ECC9",
                "isValid": True,
                "fwVersion": "75",
                "pranaModel": 2,
                "pranaSubtype": 2,
                "label": "test             ",
            }
        )
        assert info == PranaDeviceInfo("ECC9", True, 75, "PRANA RECUPERATOR 200G", "test", 2)
        assert info.to_dict()["label"] == "test"

    def test_defaults_for_empty_payload(self) -> None:
        info = PranaDeviceInfo.from_dict({})
        assert (info.manufactureId, info.isValid, info.fwVersion, info.label) == ("", False, 0, "")


class TestState:
    def test_full_payload(self) -> None:
        state = PranaState.from_dict(
            {
                "supply": {"speed": 8, "is_on": True, "max_speed": 70},
                "extract": {"speed": 0, "is_on": False, "max_speed": 70},
                "bounded": {"speed": 3, "is_on": True, "max_speed": 70},
                "bound": False,
                "auto_plus": True,
                "brightness": 4,
                "inside_temperature": 215,
                "outside_temperature_2": -31,
                "humidity": 45,
                "co2": "600",
                "fresh_air_position": 2,
                "extract_position": 0,
            }
        )
        assert state.supply == FanState(speed=8, is_on=True, max_speed=7)
        assert state.extract == FanState(speed=0, is_on=False, max_speed=7)
        assert state.auto_plus
        assert not state.auto
        assert state.inside_temperature == 21.5
        assert state.outside_temperature_2 == -3.1
        assert state.co2 == 600
        assert (state.fresh_air_position, state.extract_position) == (2, 0)
        assert state.to_dict()["supply"] == {"speed": 8, "is_on": True, "max_speed": 7}

    def test_missing_optional_fields_are_none(self) -> None:
        state = PranaState.from_dict({})
        assert state.supply == FanState(0, False, 0)
        assert state.brightness == 0
        for name in (
            "inside_temperature",
            "outside_temperature",
            "humidity",
            "co2",
            "voc",
            "air_pressure",
            "fresh_air_position",
            "extract_position",
        ):
            assert getattr(state, name) is None, name

    @pytest.mark.parametrize("value", [None, "abc", True, [1]])
    def test_invalid_values_are_none(self, value: object) -> None:
        state = PranaState.from_dict({"humidity": value, "inside_temperature": value})
        assert state.humidity is None
        assert state.inside_temperature is None

    @pytest.mark.parametrize(("raw", "steps"), [(100, 10), (70, 7), (7, 7), (0, 0)])
    def test_max_speed_scaling(self, raw: int, steps: int) -> None:
        assert FanState.from_dict({"max_speed": raw}).max_speed == steps

    def test_max_speed_override(self) -> None:
        state = PranaState.from_dict({"supply": {"max_speed": 100}}, max_speed=5)
        assert state.supply.max_speed == 5


@pytest.mark.parametrize(
    ("member", "value"),
    [
        (PranaFanType.BOUNDED, "bounded"),
        (PranaSwitchType.AUTO_PLUS, "auto_plus"),
        (PranaPositionType.FRESH_AIR, "fresh_air"),
    ],
)
def test_enums_format_as_value(member: object, value: str) -> None:
    assert str(member) == value
    assert f"{member}" == value
    assert member == value
