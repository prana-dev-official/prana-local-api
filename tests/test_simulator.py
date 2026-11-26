"""Tests for the device-side rules implemented by the simulator."""

from __future__ import annotations

from aiohttp.test_utils import TestClient, TestServer
import pytest

from prana_local_api_client.simulator import (
    MODELS,
    InvalidCommand,
    SimulatedPrana,
    build_app,
    main,
)


def _device(model: str = "neo") -> SimulatedPrana:
    return SimulatedPrana(profile=MODELS[model])


def test_fresh_air_forces_supply_and_clears_modes() -> None:
    device = _device()
    device.set_switch("auto", True)
    device.set_position("fresh_air", 2)
    state = device.state_json()
    assert (state["fresh_air_position"], state["extract_position"]) == (2, 0)
    assert state["auto"] is False
    assert state["bound"] is False
    assert state["supply"] == {"speed": 8, "is_on": True, "max_speed": 70}
    assert state["extract"] == {"speed": 0, "is_on": False, "max_speed": 70}


def test_extract_replaces_fresh_air_and_restores_manual_state() -> None:
    device = _device()
    device.set_position("fresh_air", 1)
    device.set_position("extract", 3)
    state = device.state_json()
    assert (state["fresh_air_position"], state["extract_position"]) == (0, 3)
    assert state["extract"]["speed"] == 8
    device.set_position("extract", 0)
    state = device.state_json()
    assert state["bound"] is True
    assert state["supply"]["speed"] == 3


@pytest.mark.parametrize("mode", ["night", "auto", "auto_plus", "bound"])
def test_modes_clear_positions(mode: str) -> None:
    device = _device()
    device.set_position("extract", 2)
    device.set_switch(mode, True)
    assert device.state_json()["extract_position"] == 0


def test_automatic_modes_exclude_each_other() -> None:
    device = _device("200")
    device.set_switch("auto", True)
    device.set_switch("boost", True)
    state = device.state_json()
    assert state["boost"]
    assert not state["auto"]
    device.set_switch("boost", False)
    assert not device.state_json()["boost"]


def test_manual_speed_leaves_automatic_modes() -> None:
    device = _device()
    device.set_switch("auto_plus", True)
    device.set_position("fresh_air", 1)
    device.set_speed(90, "supply")  # bound: goes to bounded, capped at max
    state = device.state_json()
    assert state["bounded"]["speed"] == 7
    assert not state["auto_plus"]
    assert state["fresh_air_position"] == 0


def test_bound_copies_supply_setting() -> None:
    device = _device("340")
    device.set_switch("bound", False)
    device.set_speed(40, "supply")
    device.set_speed_is_on(False, "extract")
    device.set_switch("bound", True)
    assert device.state_json()["bounded"]["speed"] == 4


@pytest.mark.parametrize("switch", ["heater", "boost"])
def test_neo_has_no_heater_or_boost(switch: str) -> None:
    assert switch not in _device().state_json()
    with pytest.raises(InvalidCommand):
        _device().set_switch(switch, True)
    regular = _device("200")
    regular.set_switch(switch, True)
    assert regular.state_json()[switch] is True


@pytest.mark.parametrize(
    "command",
    [
        lambda d: d.set_speed(15, "supply"),
        lambda d: d.set_speed("10", "supply"),
        lambda d: d.set_speed(10, "sideways"),
        lambda d: d.set_switch("turbo", True),
        lambda d: d.set_brightness(3),
        lambda d: d.set_position("fresh_air", 4),
        lambda d: d.set_position("bypass", 1),
    ],
)
def test_invalid_commands(command: object) -> None:
    with pytest.raises(InvalidCommand):
        command(_device())  # type: ignore[operator]


def test_regular_model_has_no_positions() -> None:
    device = _device("200")
    assert "fresh_air_position" not in device.state_json()
    with pytest.raises(InvalidCommand):
        device.set_position("fresh_air", 1)


def test_sensors_drift_within_range() -> None:
    import random

    device = _device("340")
    rng = random.Random(1)
    for _ in range(500):
        device.drift_sensors(rng)
    assert 400 <= device.sensors["co2"] <= 1800
    assert device.summary().startswith("supply=")
    assert "fresh_air=" in _device().summary()


def test_info_pads_label_like_firmware() -> None:
    info = _device().info_json("test", "ID")
    assert info["label"] == "test".ljust(16)
    assert info["pranaModel"] == 5


@pytest.mark.parametrize(
    ("path", "body"),
    [
        ("/setSwitch", {"switchType": "heater", "value": True}),
        ("/setSwitch", {"value": True}),
        ("/setSpeed", [1]),
        ("/setBrightness", "not json"),
    ],
)
async def test_http_rejects_bad_commands(path: str, body: object) -> None:
    async with TestClient(TestServer(build_app(_device()))) as client:
        kwargs = {"data": body} if isinstance(body, str) else {"json": body}
        resp = await client.post(path, **kwargs)
        assert resp.status == 400


async def test_http_accepts_command() -> None:
    device = _device()
    async with TestClient(TestServer(build_app(device))) as client:
        resp = await client.post("/setPosition", json={"positionType": "extract", "value": 1})
        assert resp.status == 200
    assert device.extract_position == 1


def test_main_rejects_unknown_model() -> None:
    with pytest.raises(SystemExit):
        main(["--model", "999"])
