"""Tests for PranaLocalApiClient against the simulator and failing servers."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable

from aiohttp import ClientSession, web
from aiohttp.test_utils import TestServer
import pytest

from prana_local_api_client import (
    PranaApiCommunicationError,
    PranaApiInvalidResponse,
    PranaApiUpdateFailed,
    PranaFanType,
    PranaLocalApiClient,
    PranaPositionType,
    PranaSwitchType,
    UpdateFailed,
)

from .conftest import SimulatedSetup


async def test_get_device_info(simulated: SimulatedSetup) -> None:
    info = await simulated.client.get_device_info()
    assert info.manufactureId == "ABC123"
    assert info.label == "Test"
    assert info.is_neo


@pytest.mark.parametrize("model", ["200"])
async def test_get_state_regular_model(simulated: SimulatedSetup) -> None:
    info = await simulated.client.get_device_info()
    state = await simulated.client.get_state()
    assert not info.is_neo
    assert state.bound
    assert state.supply.max_speed == 10
    assert state.inside_temperature == 21.7
    assert state.fresh_air_position is None


async def test_speed_commands(simulated: SimulatedSetup) -> None:
    client = simulated.client
    await client.set_switch(PranaSwitchType.BOUND, False)
    await client.set_speed(50, PranaFanType.SUPPLY)
    await client.set_speed_is_on(False, "extract")
    state = await client.get_state()
    assert state.supply.speed == 5
    assert not state.extract.is_on


async def test_switch_brightness_and_position(simulated: SimulatedSetup) -> None:
    client = simulated.client
    await client.set_switch("auto", True)
    await client.set_brightness(32)
    await client.set_position(PranaPositionType.FRESH_AIR, 3)
    state = await client.get_state()
    assert state.brightness == 6
    assert state.fresh_air_position == 3
    assert not state.auto
    assert state.supply.speed == state.supply.max_speed + 1


@pytest.mark.parametrize(
    "call",
    [
        lambda c: c.set_speed(15, "supply"),
        lambda c: c.set_speed(-10, "supply"),
        lambda c: c.set_speed(10, "sideways"),
        lambda c: c.set_switch("turbo", True),
        lambda c: c.set_brightness(3),
        lambda c: c.set_position("fresh_air", 4),
        lambda c: c.set_position("bypass", 1),
    ],
)
async def test_invalid_arguments_raise_before_request(
    call: Callable[[PranaLocalApiClient], Awaitable[None]],
) -> None:
    client = PranaLocalApiClient("192.0.2.1")  # never contacted
    with pytest.raises(ValueError):  # noqa: PT011
        await call(client)


async def test_device_rejection_is_update_failed(simulated: SimulatedSetup) -> None:
    # Neo has no heater, so the device answers 400.
    with pytest.raises(PranaApiUpdateFailed) as exc:
        await simulated.client.set_switch(PranaSwitchType.HEATER, True)
    assert exc.value.status == 400


async def test_connection_refused_is_communication_error(unused_tcp_port: int) -> None:
    client = PranaLocalApiClient("127.0.0.1", unused_tcp_port)
    with pytest.raises(PranaApiCommunicationError):
        await client.get_state()


@pytest.fixture
async def custom_server() -> AsyncIterator[Callable[[web.Application], Awaitable[TestServer]]]:
    servers: list[TestServer] = []

    async def start(app: web.Application) -> TestServer:
        server = TestServer(app)
        await server.start_server()
        servers.append(server)
        return server

    yield start
    for server in servers:
        await server.close()


def _app(handler: Callable[[web.Request], Awaitable[web.StreamResponse]]) -> web.Application:
    app = web.Application()
    app.router.add_route("*", "/{tail:.*}", handler)
    return app


@pytest.mark.parametrize(
    "body",
    [web.Response(text="not json"), web.json_response([1, 2, 3])],
    ids=["invalid-json", "not-an-object"],
)
async def test_invalid_payload(
    custom_server: Callable[[web.Application], Awaitable[TestServer]], body: web.Response
) -> None:
    async def handler(request: web.Request) -> web.Response:
        return body

    server = await custom_server(_app(handler))
    with pytest.raises(PranaApiInvalidResponse):
        await PranaLocalApiClient(server.host, server.port).get_state()


async def test_http_error_status(
    custom_server: Callable[[web.Application], Awaitable[TestServer]],
) -> None:
    async def handler(request: web.Request) -> web.Response:
        return web.Response(status=503)

    server = await custom_server(_app(handler))
    with pytest.raises(PranaApiUpdateFailed) as exc:
        await PranaLocalApiClient(server.host, server.port).get_device_info()
    assert exc.value.status == 503


async def test_timeout_is_communication_error(
    custom_server: Callable[[web.Application], Awaitable[TestServer]],
) -> None:
    async def handler(request: web.Request) -> web.Response:
        await asyncio.sleep(1)
        return web.json_response({})

    server = await custom_server(_app(handler))
    with pytest.raises(PranaApiCommunicationError):
        await PranaLocalApiClient(server.host, server.port, timeout=0.05).get_state()


def test_request_errors_share_update_failed_base() -> None:
    for cls in (PranaApiCommunicationError, PranaApiUpdateFailed, PranaApiInvalidResponse):
        assert issubclass(cls, UpdateFailed)


async def test_external_session_is_not_closed(simulated: SimulatedSetup) -> None:
    async with ClientSession() as session:
        async with PranaLocalApiClient(
            simulated.server.host, simulated.server.port, session=session
        ) as client:
            await client.get_state()
        assert not session.closed


async def test_context_manager_closes_own_session(simulated: SimulatedSetup) -> None:
    client = PranaLocalApiClient(simulated.server.host, simulated.server.port)
    async with client:
        session = client.session
        assert session is not None
    assert session.closed
    assert client.session is None


async def test_without_context_manager_uses_temporary_session(simulated: SimulatedSetup) -> None:
    client = PranaLocalApiClient(simulated.server.host, simulated.server.port)
    assert (await client.get_state()).bound
    assert client.session is None
