"""Simulated Prana device serving the local HTTP API.

Lets the client and integrations be developed without hardware. Supports the
regular models and Prana Neo (Fresh air / Extract positions, no heater/boost)::

    prana-simulator --model neo --host 0.0.0.0
    python -m prana_local_api_client.simulator --model 200 --port 8080

Endpoints: ``GET /info``, ``GET /getState``, ``POST /setSpeed``,
``/setSpeedIsOn``, ``/setSwitch``, ``/setBrightness`` and, on Neo only,
``POST /setPosition``. Invalid commands are answered with HTTP 400.

Mode rules (taken from the Prana Online app):

* Night, Boost, Auto and Auto+ exclude each other.
* Fresh air (Neo) forces the supply motor one step above its maximum and stops
  the extract motor; Extract mode is the mirror image. Each clears the other
  and Night/Boost/Auto/Auto+. Night/Boost/Auto/Auto+ or Bound clear both.
* Any manual fan command leaves the automatic modes and positions.
"""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import Awaitable, Callable
import contextlib
from dataclasses import dataclass, field
import logging
import math
import random
from typing import Any

from aiohttp import web

from .models.prana_device_info import PRANA_NEO_MODEL_ID
from .models.prana_fan_type import PranaFanType
from .models.prana_position_type import PranaPositionType
from .models.prana_switch_type import PranaSwitchType
from .prana_local_api_client import (
    BRIGHTNESS_VALUES,
    POSITION_MAX,
    POSITION_MIN,
    SPEED_SCALE,
)

_LOGGER = logging.getLogger(__name__)

# Modes that exclude each other and replace Fresh air / Extract positions.
_EXCLUSIVE_MODES = (
    PranaSwitchType.NIGHT,
    PranaSwitchType.BOOST,
    PranaSwitchType.AUTO,
    PranaSwitchType.AUTO_PLUS,
)


@dataclass(frozen=True)
class ModelProfile:
    """Static description of a simulated model."""

    model_id: int
    subtype_id: int
    max_speed: int  # in speed steps
    sensors: tuple[str, ...]
    unsupported_switches: frozenset[PranaSwitchType] = frozenset()

    @property
    def is_neo(self) -> bool:
        """Return True for Prana Neo."""
        return self.model_id == PRANA_NEO_MODEL_ID

    @property
    def switches(self) -> tuple[PranaSwitchType, ...]:
        """Return the switches this model has."""
        return tuple(s for s in PranaSwitchType if s not in self.unsupported_switches)


MODELS: dict[str, ModelProfile] = {
    # Neo reports supply (inside_temperature) and extract (outside_temperature_2)
    # air temperatures, like the Prana Online app shows them.
    "neo": ModelProfile(
        model_id=PRANA_NEO_MODEL_ID,
        subtype_id=0x00,
        max_speed=7,
        sensors=("inside_temperature", "outside_temperature_2", "humidity", "co2", "voc"),
        unsupported_switches=frozenset({PranaSwitchType.HEATER, PranaSwitchType.BOOST}),
    ),
    "200": ModelProfile(
        model_id=0x00,
        subtype_id=0x00,
        max_speed=10,
        sensors=("inside_temperature", "outside_temperature", "humidity"),
    ),
    "340": ModelProfile(
        model_id=0x04,
        subtype_id=0x00,
        max_speed=10,
        sensors=(
            "inside_temperature",
            "outside_temperature",
            "inside_temperature_2",
            "outside_temperature_2",
            "humidity",
            "co2",
            "voc",
            "air_pressure",
        ),
    ),
}


@dataclass(frozen=True)
class SensorRange:
    """Random-walk parameters of a simulated sensor (raw device units)."""

    start: float
    low: float
    high: float
    step: float


# Temperatures are in tenths of °C, like the real device reports them.
SENSOR_RANGES: dict[str, SensorRange] = {
    "inside_temperature": SensorRange(217, 180, 260, 2),
    "outside_temperature": SensorRange(54, -150, 300, 3),
    "inside_temperature_2": SensorRange(205, 170, 250, 2),
    "outside_temperature_2": SensorRange(231, 180, 270, 2),
    "humidity": SensorRange(48, 25, 80, 1),
    "co2": SensorRange(650, 400, 1800, 25),
    "voc": SensorRange(120, 0, 600, 10),
    "air_pressure": SensorRange(745, 730, 770, 1),
}


class InvalidCommand(ValueError):
    """A command the simulated device rejects (answered with HTTP 400)."""


def _parse_enum(enum_cls: Any, value: Any, name: str) -> Any:
    try:
        return enum_cls(value)
    except ValueError:
        raise InvalidCommand(f"Unknown {name} {value!r}") from None


@dataclass
class FanMotor:
    """Manual setting of one motor (speed in steps)."""

    speed: int = 3
    is_on: bool = True


@dataclass
class SimulatedPrana:
    """In-memory device state implementing the device-side mode rules."""

    profile: ModelProfile
    supply: FanMotor = field(default_factory=FanMotor)
    extract: FanMotor = field(default_factory=FanMotor)
    bounded: FanMotor = field(default_factory=FanMotor)
    switches: dict[PranaSwitchType, bool] = field(default_factory=dict)
    brightness_level: int = 4
    fresh_air_position: int = 0
    extract_position: int = 0
    sensors: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Seed switches (bound on) and sensors for the model."""
        if not self.switches:
            self.switches = dict.fromkeys(self.profile.switches, False)
            self.switches[PranaSwitchType.BOUND] = True
        if not self.sensors:
            self.sensors = {name: SENSOR_RANGES[name].start for name in self.profile.sensors}

    # --- Commands ----------------------------------------------------------

    def set_speed(self, speed: Any, fan_type: Any) -> None:
        """Handle ``/setSpeed`` (speed in tenths of a step)."""
        if not isinstance(speed, int) or speed <= 0 or speed % SPEED_SCALE:
            raise InvalidCommand(f"speed must be a positive multiple of {SPEED_SCALE}")
        motor = self._motor(fan_type)
        motor.speed = min(speed // SPEED_SCALE, self.profile.max_speed)
        motor.is_on = True
        self._leave_automatic_modes()

    def set_speed_is_on(self, value: Any, fan_type: Any) -> None:
        """Handle ``/setSpeedIsOn``."""
        self._motor(fan_type).is_on = bool(value)
        self._leave_automatic_modes()

    def set_switch(self, switch_type: Any, value: Any) -> None:
        """Handle ``/setSwitch``."""
        switch = _parse_enum(PranaSwitchType, switch_type, "switchType")
        if switch not in self.switches:
            raise InvalidCommand(f"switchType {switch.value!r} is not supported by this model")
        self.switches[switch] = bool(value)
        if not value:
            return
        if switch in _EXCLUSIVE_MODES:
            self._turn_off(*(mode for mode in _EXCLUSIVE_MODES if mode != switch))
            self._clear_positions()
        elif switch is PranaSwitchType.BOUND:
            # Entering bound mode continues at the current supply setting.
            self.bounded = FanMotor(self.supply.speed, self.supply.is_on)
            self._clear_positions()

    def set_brightness(self, brightness: Any) -> None:
        """Handle ``/setBrightness`` (0, 1, 2, 4 ... 32 -> level 0..6)."""
        if brightness not in BRIGHTNESS_VALUES:
            raise InvalidCommand(f"brightness must be one of {BRIGHTNESS_VALUES}")
        self.brightness_level = 0 if brightness == 0 else int(math.log2(brightness)) + 1

    def set_position(self, position_type: Any, value: Any) -> None:
        """Handle ``/setPosition`` (Prana Neo Fresh air / Extract)."""
        if not self.profile.is_neo:
            raise InvalidCommand("setPosition is only supported on Prana Neo")
        position = _parse_enum(PranaPositionType, position_type, "positionType")
        if not isinstance(value, int) or not POSITION_MIN <= value <= POSITION_MAX:
            raise InvalidCommand(f"value must be between {POSITION_MIN} and {POSITION_MAX}")
        if position is PranaPositionType.FRESH_AIR:
            self.fresh_air_position = value
        else:
            self.extract_position = value
        if value:
            if position is PranaPositionType.FRESH_AIR:
                self.extract_position = 0
            else:
                self.fresh_air_position = 0
            self._turn_off(*_EXCLUSIVE_MODES)

    # --- Helpers -----------------------------------------------------------

    def _motor(self, fan_type: Any) -> FanMotor:
        fan = _parse_enum(PranaFanType, fan_type, "fanType")
        if fan is PranaFanType.BOUNDED or self.switches[PranaSwitchType.BOUND]:
            # In bound mode both motors follow the bounded setting.
            return self.bounded
        return self.supply if fan is PranaFanType.SUPPLY else self.extract

    def _turn_off(self, *switches: PranaSwitchType) -> None:
        for switch in switches:
            if switch in self.switches:
                self.switches[switch] = False

    def _clear_positions(self) -> None:
        self.fresh_air_position = 0
        self.extract_position = 0

    def _leave_automatic_modes(self) -> None:
        self._turn_off(*_EXCLUSIVE_MODES)
        self._clear_positions()

    # --- Reporting ---------------------------------------------------------

    def _fan_json(self, speed: int, is_on: bool) -> dict[str, Any]:
        return {
            "speed": speed,
            "is_on": is_on,
            "max_speed": self.profile.max_speed * SPEED_SCALE,
        }

    def info_json(self, label: str, manufacture_id: str) -> dict[str, Any]:
        """Build the ``/info`` payload (label padded like the firmware does)."""
        return {
            "manufactureId": manufacture_id,
            "isValid": True,
            "fwVersion": 75,
            "pranaModel": self.profile.model_id,
            "pranaSubtype": self.profile.subtype_id,
            "label": label.ljust(16),
        }

    def state_json(self) -> dict[str, Any]:
        """Build the ``/getState`` payload."""
        supply = self._fan_json(self.supply.speed, self.supply.is_on)
        extract = self._fan_json(self.extract.speed, self.extract.is_on)
        bound = self.switches[PranaSwitchType.BOUND]

        # Fresh air / Extract override the motors without touching the stored
        # manual settings, which come back once the mode is turned off.
        forced = self._fan_json(self.profile.max_speed + 1, True)
        stopped = self._fan_json(0, False)
        if self.fresh_air_position:
            supply, extract, bound = forced, stopped, False
        elif self.extract_position:
            supply, extract, bound = stopped, forced, False

        state: dict[str, Any] = {
            "supply": supply,
            "extract": extract,
            "bounded": self._fan_json(self.bounded.speed, self.bounded.is_on),
            "bound": bound,
            **{
                switch.value: on
                for switch, on in self.switches.items()
                if switch is not PranaSwitchType.BOUND
            },
            "brightness": self.brightness_level,
            **{name: round(value) for name, value in self.sensors.items()},
        }
        if self.profile.is_neo:
            state["fresh_air_position"] = self.fresh_air_position
            state["extract_position"] = self.extract_position
        return state

    def summary(self) -> str:
        """Return a one-line description for the log."""
        state = self.state_json()

        def fan(key: str) -> str:
            return f"{key}={state[key]['speed']}{'' if state[key]['is_on'] else '(off)'}"

        on = [switch.value for switch in self.switches if state.get(switch.value)]
        parts = [fan("supply"), fan("extract"), f"bounded={state['bounded']['speed']}", f"on={on}"]
        if self.profile.is_neo:
            parts.append(
                f"fresh_air={self.fresh_air_position} extract_mode={self.extract_position}"
            )
        return " ".join(parts)

    def drift_sensors(self, rng: random.Random) -> None:
        """Random-walk the sensors so updates are visible in clients."""
        for name, value in self.sensors.items():
            spec = SENSOR_RANGES[name]
            self.sensors[name] = min(
                spec.high, max(spec.low, value + rng.uniform(-spec.step, spec.step))
            )


Handler = Callable[[web.Request], Awaitable[web.StreamResponse]]


def build_app(
    device: SimulatedPrana,
    *,
    label: str = "Prana simulator",
    manufacture_id: str = "SIMULATOR",
) -> web.Application:
    """Create the aiohttp application serving ``device``."""

    async def get_info(request: web.Request) -> web.Response:
        return web.json_response(device.info_json(label, manufacture_id))

    async def get_state(request: web.Request) -> web.Response:
        return web.json_response(device.state_json())

    def command(apply: Callable[[dict[str, Any]], None]) -> Handler:
        async def handler(request: web.Request) -> web.Response:
            try:
                body = await request.json()
                if not isinstance(body, dict):
                    raise InvalidCommand("body must be a JSON object")
                apply(body)
            except (ValueError, KeyError) as err:  # InvalidCommand, bad JSON, missing key
                _LOGGER.warning("%s rejected: %r", request.path, err)
                return web.Response(status=400, text=str(err))
            _LOGGER.info("%s %s -> %s", request.path, body, device.summary())
            return web.Response()

        return handler

    app = web.Application()
    app.router.add_get("/info", get_info)
    app.router.add_get("/getState", get_state)
    app.router.add_post("/setSpeed", command(lambda b: device.set_speed(b["speed"], b["fanType"])))
    app.router.add_post(
        "/setSpeedIsOn", command(lambda b: device.set_speed_is_on(b["value"], b["fanType"]))
    )
    app.router.add_post(
        "/setSwitch", command(lambda b: device.set_switch(b["switchType"], b["value"]))
    )
    app.router.add_post("/setBrightness", command(lambda b: device.set_brightness(b["brightness"])))
    app.router.add_post(
        "/setPosition", command(lambda b: device.set_position(b["positionType"], b["value"]))
    )
    return app


async def _serve(args: argparse.Namespace) -> None:
    device = SimulatedPrana(profile=MODELS[args.model])
    label = args.label or f"Prana {args.model.upper()} simulator"
    runner = web.AppRunner(
        build_app(
            device,
            label=label,
            manufacture_id=args.manufacture_id or f"SIM{args.model.upper()}{args.port}",
        )
    )
    await runner.setup()
    try:
        await web.TCPSite(runner, args.host, args.port).start()
        _LOGGER.info("Simulating %s on http://%s:%s", label, args.host, args.port)
        _LOGGER.info("Initial state: %s", device.summary())
        rng = random.Random()
        while True:
            await asyncio.sleep(args.drift_interval)
            device.drift_sensors(rng)
    finally:
        await runner.cleanup()


def main(argv: list[str] | None = None) -> None:
    """Run the simulator from the command line."""
    parser = argparse.ArgumentParser(description="Simulated Prana device (local HTTP API).")
    parser.add_argument("--model", choices=sorted(MODELS), default="neo")
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="address to bind; on macOS port 80 needs 0.0.0.0 without root",
    )
    parser.add_argument("--port", type=int, default=80)
    parser.add_argument("--label", default="", help="device label reported by /info")
    parser.add_argument("--manufacture-id", default="", help="serial reported by /info")
    parser.add_argument(
        "--drift-interval", type=float, default=5.0, help="seconds between sensor updates"
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(_serve(args))


if __name__ == "__main__":
    main()
