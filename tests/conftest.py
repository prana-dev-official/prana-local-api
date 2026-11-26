"""Shared fixtures: a simulated device served over real HTTP."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass

from aiohttp.test_utils import TestServer
import pytest

from prana_local_api_client import PranaLocalApiClient
from prana_local_api_client.simulator import MODELS, SimulatedPrana, build_app


@dataclass
class SimulatedSetup:
    """A running simulator plus a client pointing at it."""

    device: SimulatedPrana
    client: PranaLocalApiClient
    server: TestServer


@pytest.fixture
def model() -> str:
    """Model to simulate; override with ``@pytest.mark.parametrize("model", ...)``."""
    return "neo"


@pytest.fixture
async def simulated(model: str) -> AsyncIterator[SimulatedSetup]:
    """Serve a simulated device and yield a client connected to it."""
    device = SimulatedPrana(profile=MODELS[model])
    server = TestServer(build_app(device, label="Test", manufacture_id="ABC123"))
    await server.start_server()
    try:
        async with PranaLocalApiClient(server.host, server.port) as client:
            yield SimulatedSetup(device, client, server)
    finally:
        await server.close()
