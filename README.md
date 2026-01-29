# prana-local-api-client

An asynchronous Python client for the local HTTP API of Prana devices.

This library provides a small, well-documented async client to read the device state and control Prana recuperators over a local network using HTTP.

Quick links

- Installation: see the **Installation** section
- Quick start: see **Quick example (async)**
- API reference: see **API / Methods**

Requirements

- Python 3.10+
- aiohttp

Firmware compatibility

> ⚠️ This client works only with Prana recuperators running firmware **47+**.

To check firmware: open the `Prana Online 2.0` app → press and hold the device card → **About Device**.

Table of contents

- Features
- Installation
- Quick example (async)
- API / Methods
- Data models
- Exceptions
- License

Features

- Fetch device information (`get_device_info`).
- Retrieve structured device state (`get_state`) as `PranaState` / `FanState`.
- Control fan speed, toggles, and brightness (`set_speed`, `set_switch`, `set_brightness`).
- Fully asynchronous (`asyncio` + `aiohttp`).
- Helpful model parsing (e.g., temperature reported in tenths of °C is normalized).

Installation

Install from PyPI:

```bash
pip install prana-local-api-client
```

From a local checkout (editable, with dev extras):

```bash
pip install -e .[dev]
```

Quick example (async)

```python
import asyncio
from prana_local_api_client.prana_local_api_client import PranaLocalApiClient
from prana_local_api_client.models.prana_fan_type import PranaFanType
from prana_local_api_client.models.prana_switch_type import PranaSwitchType


async def main():
    # Device IP and optional port
    async with PranaLocalApiClient("192.168.1.100", port=80) as client:
        info = await client.get_device_info()
        print("Device:", info.to_dict())

        state = await client.get_state()
        print("State:", state.to_dict())

        # NOTE: the device expects speed values scaled by 10. For example,
        # to set speed '1' pass 10, for speed '3' pass 30.
        await client.set_speed(30, fan_type=PranaFanType.EXTRACT.value)

        # Enable a switch (e.g. BOOST)
        await client.set_switch(PranaSwitchType.BOOST.value, True)

        # Set backlight brightness (0-100)
        await client.set_brightness(50)

asyncio.run(main())
```

API / Methods

Top-level client: `PranaLocalApiClient` (module: `prana_local_api_client.prana_local_api_client`).

- `PranaLocalApiClient(host: str, port: int = 80)` — create client instance.
- `async with PranaLocalApiClient(...) as client:` — context manager that opens/closes an `aiohttp.ClientSession`.
- `get_device_info() -> PranaDeviceInfo` — returns device info as a `PranaDeviceInfo`.
- `get_state() -> PranaState` — returns the current device state as a `PranaState`.
- `set_speed(speed: int, fan_type: str)` — set fan speed; `fan_type` is one of: `supply`, `extract`, `bounded` (10, 20, 30 ... 100).
- `set_switch(switch_type: PranaSwitchType, value: bool)` — toggle a switch; use `PranaSwitchType` values.
- `set_brightness(brightness: int)` — set panel/backlight brightness (0, 1, 2, 4, 8, 16, 32).
- `set_speed_is_on(speed_is_on: bool, fan_type: str)` — enable/disable speed for a fan type.

Data models

Models are defined in `prana_local_api_client.models` and provide `from_dict` helpers:

- `PranaDeviceInfo` — fields: `manufactureId`, `isValid`, `fwVersion`, `pranaModel`, `label`.
- `PranaState` — contains `extract`, `supply`, `bounded` (`FanState`) plus flags and optional sensor fields (`inside_temperature`, `outside_temperature`, `humidity`, `co2`, etc.).
- `FanState` — `speed`, `is_on`, `max_speed`.

Notes on parsing

- Temperatures are often reported by the device in tenths of °C; `PranaState.from_dict` converts these to °C floats.
- `PranaDeviceInfo.from_dict` handles numeric strings and byte values for firmware/model fields.

Exceptions

Defined in `prana_local_api_client.models.exceptions`:

- `PranaApiClientException` — base exception class.
- `PranaApiCommunicationError` — network/timeout related errors.
- `PranaApiUpdateFailed` — HTTP error returned by device (status != 200).
- `UpdateFailed` — wrapper for higher-level update failures.
- `ValueError` — invalid values encountered.

Wrap client calls in `try/except` and handle these exceptions depending on your application needs.
