from aiohttp import ClientSession, ClientError, ClientTimeout
from typing import Any
import json
import logging
from .exceptions import PranaApiUpdateFailed, PranaApiCommunicationError

_LOGGER = logging.getLogger(__name__)


class PranaLocalApiClient:
    """Client for interacting with the Prana device API."""

    def __init__(self, host: str, port: int = 80) -> None:
        """Initialize the API client."""
        self.base_url = f"http://{host}:{port}"
        self.session = None  # Session is created externally or on first request

    async def __aenter__(self):
        """Context manager entry for ClientSession."""
        self.session = ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Closing the ClientSession."""
        await self.session.close()
        self.session = None

    # --- HTTP Methods, extracted from Coordinator and async_get_state ---

    async def get_state(self) -> dict[str, Any]:
        """Performs a GET to retrieve the raw device state."""
        url = f"{self.base_url}/getState"
        return await self._async_request("GET", url)

    async def set_speed(self, speed: int, fan_type: str) -> None:
        """Sends the speed change command."""
        url = f"{self.base_url}/setSpeed"
        data = {"speed": speed, "fanType": fan_type}
        await self._async_request("POST", url, json_data=data)

    async def set_switch(self, switch_type: str, value: bool) -> None:
        """Sends the switch state change command."""
        url = f"{self.base_url}/setSwitch"
        data = {"switchType": switch_type, "value": value}
        await self._async_request("POST", url, json_data=data)

    async def set_brightness(self, brightness: int) -> None:
        """Sends the brightness change command."""
        url = f"{self.base_url}/setBrightness"
        data = {"brightness": brightness}
        await self._async_request("POST", url, json_data=data)

    # --- General method for executing requests ---

    async def _async_request(
            self,
            method: str,
            url: str,
            json_data: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Base async method for HTTP requests, handles errors."""

        # Check if a session needs to be created internally
        session_was_created = False
        if not self.session:
            self.session = ClientSession()
            session_was_created = True

        try:
            async with self.session.request(
                    method, url, json=json_data, timeout=ClientTimeout(total=10)
            ) as resp:
                if resp.status != 200:
                    _LOGGER.error("Request failed: %s %s with status %s", method, url, resp.status)
                    raise PranaApiUpdateFailed(resp.status, "HTTP error from device")

                if resp.content_type == "application/json":
                    return await resp.json()

                return None  # For POST requests that don't return JSON

        except (ClientError, ClientTimeout) as err:
            _LOGGER.error("Network or timeout error: %s", err)
            raise PranaApiCommunicationError(f"Network error: {err}") from err
        finally:
            # Close the session if it was created internally by this method
            if session_was_created:
                await self.session.close()
                self.session = None