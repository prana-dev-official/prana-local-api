# prana-api-client

[![CI](https://github.com/prana-dev-official/prana-local-api/actions/workflows/ci.yml/badge.svg)](https://github.com/prana-dev-official/prana-local-api/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/prana-api-client)](https://pypi.org/project/prana-api-client/)

Async Python client for the local HTTP API of Prana recuperators, used by the
Home Assistant `prana` integration. Includes a device simulator for development
without hardware.

- Python 3.10+, `aiohttp`, fully typed (`py.typed`)
- Regular models (150, 162, 200, 212, 340) and **Prana Neo**
- Device firmware **47+** (check it in the *Prana Online 2.0* app: press and
  hold the device card → **About Device**)

## Installation

```bash
pip install prana-api-client
```

The import name is `prana_local_api_client`.

## Quick start

```python
import asyncio

from prana_local_api_client import (
    PranaFanType,
    PranaLocalApiClient,
    PranaPositionType,
    PranaSwitchType,
)


async def main() -> None:
    async with PranaLocalApiClient("192.168.1.100") as client:
        info = await client.get_device_info()
        state = await client.get_state()
        print(info.pranaModel, state.supply.speed, state.inside_temperature)

        await client.set_speed(30, PranaFanType.SUPPLY)  # speed step 3 (x10)
        await client.set_switch(PranaSwitchType.NIGHT, True)

        if info.is_neo and state.fresh_air_position is not None:
            await client.set_position(PranaPositionType.FRESH_AIR, 2)


asyncio.run(main())
```

### Sessions

| Usage | Session |
| --- | --- |
| `PranaLocalApiClient(host, session=my_session)` | yours; never closed by the client (recommended in Home Assistant) |
| `async with PranaLocalApiClient(host) as client:` | opened for the block and closed on exit |
| plain calls without `async with` | a short-lived session per request |

## API

`PranaLocalApiClient(host, port=80, *, session=None, timeout=10.0)`

| Method | Endpoint | Notes |
| --- | --- | --- |
| `get_device_info() -> PranaDeviceInfo` | `GET /info` | |
| `get_state() -> PranaState` | `GET /getState` | |
| `set_speed(speed, fan_type)` | `POST /setSpeed` | `speed` in tenths of a step (`30` = step 3); `fan_type`: `supply`, `extract`, `bounded` (use `bounded` while bound mode is on) |
| `set_speed_is_on(on, fan_type)` | `POST /setSpeedIsOn` | turn a motor on/off |
| `set_switch(switch_type, value)` | `POST /setSwitch` | see `PranaSwitchType` |
| `set_brightness(value)` | `POST /setBrightness` | one of `0, 1, 2, 4, 8, 16, 32` (level *n* → `2 ** (n - 1)`) |
| `set_position(position_type, value)` | `POST /setPosition` | **Neo only**: `fresh_air` / `extract`, `0` (off) … `3` |

Invalid arguments raise `ValueError` before anything is sent.

### Models

- **`PranaDeviceInfo`**: `manufactureId` (serial), `isValid`, `fwVersion`,
  `pranaModel` (name, e.g. `"PRANA NEO"`), `label`, `model_id` (raw model byte),
  and the `is_neo` property.
- **`PranaState`**: `supply`, `extract` and `bounded` (`FanState`: `speed`,
  `is_on`, `max_speed` in steps); the `bound`, `heater`, `auto`, `auto_plus`,
  `winter`, `night` and `boost` flags; `brightness` (0–6); and sensors
  (`inside_temperature`, `outside_temperature`, `*_2`, `humidity`, `co2`, `voc`,
  `air_pressure`; temperatures in °C). On Neo it also has `fresh_air_position`
  and `extract_position`. Values the device does not report are `None`.

### Prana Neo

Neo reports `pranaModel = 5`. Compared with the regular models:

- It has no heater and no boost. `auto` is called *Auto turbo* and `auto_plus`
  *Auto comfort* in the Prana app.
- `inside_temperature` is the supply air temperature and `outside_temperature_2`
  is the extract air temperature.
- **Fresh air** and **Extract** modes have positions 1–3. Fresh air forces the
  supply motor to one step above its maximum and stops the extract motor;
  Extract mode does the opposite. Each clears the other, along with Night,
  Auto and Auto+. Turning on Night, Auto, Auto+ or Bound clears both.
- Firmware without the Neo local API does not send `fresh_air_position` or
  `extract_position`, so check for `None` before offering these modes.

### Exceptions

```
PranaApiClientException
└── UpdateFailed                    any failed request
    ├── PranaApiCommunicationError  connection error or timeout
    ├── PranaApiUpdateFailed        non-200 status (.status)
    └── PranaApiInvalidResponse     unexpected payload
```

## Simulator

The package includes a fake device that serves the whole API, with the mode
rules above:

```bash
prana-simulator --model neo --host 0.0.0.0   # or: python -m prana_local_api_client.simulator
prana-simulator --model 200 --port 8080      # models: neo, 200, 340
```

On macOS a regular user can bind port 80 only on `0.0.0.0`, which also makes
the simulator reachable from your local network. Sensor values drift every few
seconds, and each accepted command is logged.

## Development

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
ruff check . && ruff format --check . && mypy && pytest --cov
```

CI runs these checks on Python 3.10–3.14, along with `pip-audit` and a test
build of the package. To release, bump `version` in `pyproject.toml`, update
`CHANGELOG.md`, and push a `vX.Y.Z` tag. The release workflow checks that the
tag matches the version, then publishes to PyPI and creates a GitHub release.

## License

MIT
