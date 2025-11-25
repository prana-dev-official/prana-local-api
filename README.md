# Prana Local API Client

Prana Local API Client is a small asynchronous Python library to interact with a local HTTP API exposed by a Prana device. It uses aiohttp and provides a simple interface to read device state and send control commands.

## Requirements
- Python 3.9+
- aiohttp

Install dependencies:
```bash
pip install aiohttp
```

## Overview
Primary class: `PranaLocalApiClient`

Constructor:
- `PranaLocalApiClient(host: str, port: int = 80)`

Behavior summary:
- Uses an aiohttp ClientSession. You can provide/retain a session by using the client as an async context manager (`async with`) or let the client create and close a temporary session for each call.
- Requests use a total timeout of 10 seconds.
- Non-200 HTTP responses raise `PranaApiUpdateFailed`.
- Network errors and timeouts raise `PranaApiCommunicationError`.

## API (async)

- `async def get_state() -> dict[str, Any] | None`
  - GET /getState
  - Returns parsed JSON when the server responds with `application/json`. Returns `None` for responses without JSON body.

- `async def set_speed(speed: int, fan_type: str) -> None`
  - POST /setSpeed
  - JSON body: `{"speed": speed, "fanType": fan_type}`

- `async def set_switch(switch_type: str, value: bool) -> None`
  - POST /setSwitch
  - JSON body: `{"switchType": switch_type, "value": value}`

- `async def set_brightness(brightness: int) -> None`
  - POST /setBrightness
  - JSON body: `{"brightness": brightness}`

Notes:
- All methods call a shared internal `_async_request` which handles creating/closing sessions when needed, error handling and JSON parsing.

## Exceptions
The library exposes a small exception hierarchy in `prana_local_api_client.exceptions`:

- `PranaApiClientException` — base exception class.
- `PranaApiCommunicationError` — network-level issues (wrapping aiohttp ClientError / timeout).
- `PranaApiUpdateFailed(status: int)` — HTTP request completed but device returned non-200 status.

Example of catching errors:
```python
from prana_local_api_client.exceptions import PranaApiCommunicationError, PranaApiUpdateFailed

try:
    state = await client.get_state()
except PranaApiUpdateFailed as e:
    # HTTP-level error (server returned non-200)
    print("Device returned error status:", getattr(e, "status", None))
except PranaApiCommunicationError as e:
    # Network/timeout/etc.
    print("Communication error:", e)
```

## Usage examples

Using the client as a context manager (recommended when performing multiple requests):
```python
import asyncio
from prana_local_api_client.prana_api_client import PranaLocalApiClient

async def main():
    async with PranaLocalApiClient("192.168.1.100", 80) as client:
        state = await client.get_state()
        await client.set_speed(3, fan_type="main")
        await client.set_switch("power", True)
        await client.set_brightness(70)

asyncio.run(main())
```

Using the client without context manager (client will create and close a session per call):
```python
from prana_local_api_client.prana_api_client import PranaLocalApiClient
import asyncio

async def short_run():
    client = PranaLocalApiClient("192.168.1.100")
    # session will be created internally for each call and closed afterwards
    state = await client.get_state()
    print(state)

asyncio.run(short_run())
```

## Logging and debugging
The module uses a logger under its package name. Enable debugging in your application to see detailed logs:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Timeouts and retries
- Default request timeout is 10 seconds (ClientTimeout(total=10)).
- This library does not implement automatic retries. If you need retries, implement them in your caller code (e.g., with tenacity) or wrap calls in retry logic.

## Type hints
The client uses Python 3.9+ type hints (`dict[str, Any]`). Adjust your type checks accordingly.

## Contributing
