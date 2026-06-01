"""Tests for the in-process event bus."""

import asyncio
import pytest
from predict.core.events.event_bus import EventBus


@pytest.fixture
def bus():
    return EventBus()


@pytest.mark.asyncio
async def test_event_emitted_to_listener(bus):
    received = []

    @bus.on("test_event")
    async def handler(data):
        received.append(data)

    await bus.emit("test_event", {"key": "value"})
    assert len(received) == 1
    assert received[0]["key"] == "value"


@pytest.mark.asyncio
async def test_multiple_listeners(bus):
    results = []

    @bus.on("multi")
    async def handler_a(data):
        results.append("a")

    @bus.on("multi")
    async def handler_b(data):
        results.append("b")

    count = await bus.emit("multi", {})
    assert count == 2
    assert set(results) == {"a", "b"}


@pytest.mark.asyncio
async def test_listener_error_doesnt_crash(bus):
    results = []

    @bus.on("error_test")
    async def bad_handler(data):
        raise ValueError("boom")

    @bus.on("error_test")
    async def good_handler(data):
        results.append("ok")

    count = await bus.emit("error_test", {})
    assert count == 1  # Only good_handler succeeded
    assert results == ["ok"]


@pytest.mark.asyncio
async def test_sync_listener(bus):
    results = []

    @bus.on("sync")
    def sync_handler(data):
        results.append(data["val"])

    await bus.emit("sync", {"val": 42})
    assert results == [42]


@pytest.mark.asyncio
async def test_no_listeners_returns_zero(bus):
    count = await bus.emit("nobody_listening", {})
    assert count == 0


@pytest.mark.asyncio
async def test_event_history(bus):
    @bus.on("tracked")
    async def handler(data):
        pass

    await bus.emit("tracked", {"a": 1})
    await bus.emit("tracked", {"b": 2})

    history = bus.get_history()
    assert len(history) == 2
    assert history[0]["event"] == "tracked"


@pytest.mark.asyncio
async def test_register_imperative(bus):
    results = []

    async def my_handler(data):
        results.append(data)

    bus.register("imp", my_handler)
    await bus.emit("imp", {"x": 1})
    assert len(results) == 1


@pytest.mark.asyncio
async def test_listener_count(bus):
    @bus.on("a")
    async def h1(data): pass

    @bus.on("a")
    async def h2(data): pass

    @bus.on("b")
    async def h3(data): pass

    assert bus.listener_count("a") == 2
    assert bus.listener_count("b") == 1
    assert bus.listener_count() == 3
