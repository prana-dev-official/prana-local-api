"""Async client for the local HTTP API of Prana recuperators."""

from __future__ import annotations

import asyncio
import logging
from types import TracebackType
from typing import Any

from aiohttp import ClientError, ClientSession, ClientTimeout, ContentTypeError

from .exceptions import (
    PranaApiCommunicationError,
    PranaApiInvalidResponse,
    PranaApiUpdateFailed,
)
from .models.prana_device_info import PranaDeviceInfo
from .models.prana_fan_type import PranaFanType
from .models.prana_position_type import PranaPositionType
from .models.prana_state import PranaState
from .models.prana_switch_type import PranaSwitchType

_LOGGER = logging.getLogger(__name__)

DEFAULT_PORT = 80
DEFAULT_TIMEOUT = 10.0

#: Values accepted by ``/setBrightness`` (level n -> 2 ** (n - 1), 0 = off).
BRIGHTNESS_VALUES = (0, 1, 2, 4, 8, 16, 32)
#: Range of Prana Neo Fresh air / Extract positions (0 = off).
POSITION_MIN = 0
POSITION_MAX = 3
#: ``/setSpeed`` expects speed steps multiplied by this factor.
SPEED_SCALE = 10


class PranaLocalApiClient:
    """Client for one Prana device on the local network.

    Session handling, in order of preference:

    * pass an existing ``aiohttp.ClientSession`` as ``session`` (it is never
      closed by the client - the owner closes it);
    * use ``async with PranaLocalApiClient(...)``, which opens one session for
      the block and closes it on exit;
    * call methods directly, in which case a short-lived session is opened
      per request.
    """

    def __init__(
        self,
        host: str,
        port: int = DEFAULT_PORT,
        *,
        session: ClientSession | None = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        """Initialize the client for ``http://host:port``."""
        self.base_url = f"http://{host}:{port}"
        self.session = session
        self._owns_session = False
        self._timeout = ClientTimeout(total=timeout)

    async def __aenter__(self) -> PranaLocalApiClient:
        """Open a session for the ``async with`` block unless one was given."""
        if self.session is None:
            self.session = ClientSession()
            self._owns_session = True
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Close the session if the client opened it."""
        await self.close()

    async def close(self) -> None:
        """Close the session if it was opened by the client."""
        if self._owns_session and self.session is not None:
            await self.session.close()
            self.session = None
            self._owns_session = False

    # --- Reading -----------------------------------------------------------

    async def get_device_info(self) -> PranaDeviceInfo:
        """Return static device information (``GET /info``)."""
        return PranaDeviceInfo.from_dict(await self._get_json("/info"))

    async def get_state(self) -> PranaState:
        """Return the current device state (``GET /getState``)."""
        return PranaState.from_dict(await self._get_json("/getState"))

    # --- Commands ----------------------------------------------------------

    async def set_speed(self, speed: int, fan_type: PranaFanType | str) -> None:
        """Set a motor speed.

        ``speed`` is in tenths of a step: pass ``30`` for speed step 3.
        """
        if speed < 0 or speed % SPEED_SCALE:
            raise ValueError(f"Speed must be a non-negative multiple of {SPEED_SCALE}")
        await self._post("/setSpeed", {"speed": speed, "fanType": PranaFanType(fan_type).value})

    async def set_speed_is_on(self, speed_is_on: bool, fan_type: PranaFanType | str) -> None:
        """Turn a motor on or off."""
        await self._post(
            "/setSpeedIsOn",
            {"value": speed_is_on, "fanType": PranaFanType(fan_type).value},
        )

    async def set_switch(self, switch_type: PranaSwitchType | str, value: bool) -> None:
        """Turn a mode on or off (see :class:`PranaSwitchType`)."""
        await self._post(
            "/setSwitch",
            {"switchType": PranaSwitchType(switch_type).value, "value": value},
        )

    async def set_brightness(self, brightness: int) -> None:
        """Set the display brightness; one of :data:`BRIGHTNESS_VALUES`."""
        if brightness not in BRIGHTNESS_VALUES:
            raise ValueError(f"Brightness must be one of {BRIGHTNESS_VALUES}")
        await self._post("/setBrightness", {"brightness": brightness})

    async def set_position(self, position_type: PranaPositionType | str, value: int) -> None:
        """Set a Prana Neo Fresh air / Extract position; ``0`` turns it off."""
        if not POSITION_MIN <= value <= POSITION_MAX:
            raise ValueError(f"Position must be between {POSITION_MIN} and {POSITION_MAX}")
        await self._post(
            "/setPosition",
            {"positionType": PranaPositionType(position_type).value, "value": value},
        )

    # --- Transport ---------------------------------------------------------

    async def _get_json(self, path: str) -> dict[str, Any]:
        """GET ``path`` and return its JSON object body."""
        data = await self._request("GET", path, expect_json=True)
        if not isinstance(data, dict):
            raise PranaApiInvalidResponse(
                f"Expected a JSON object from {path}, got {type(data).__name__}"
            )
        return data

    async def _post(self, path: str, payload: dict[str, Any]) -> None:
        """POST a JSON command; the device answers with an empty 200."""
        await self._request("POST", path, json_data=payload)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_data: dict[str, Any] | None = None,
        expect_json: bool = False,
    ) -> Any:
        """Send a request and map transport failures to library exceptions."""
        url = f"{self.base_url}{path}"
        session = self.session
        temporary = session is None
        if session is None:
            session = ClientSession()
        try:
            async with session.request(method, url, json=json_data, timeout=self._timeout) as resp:
                if resp.status != 200:
                    raise PranaApiUpdateFailed(resp.status, f"{method} {path} failed with HTTP")
                if not expect_json:
                    return None
                try:
                    # The firmware does not always send a JSON content type.
                    return await resp.json(content_type=None)
                except (ContentTypeError, ValueError) as err:
                    raise PranaApiInvalidResponse(f"Invalid JSON from {path}") from err
        except (ClientError, asyncio.TimeoutError) as err:
            _LOGGER.debug("%s %s failed: %r", method, url, err)
            raise PranaApiCommunicationError(f"Error communicating with {url}: {err!r}") from err
        finally:
            if temporary:
                await session.close()
