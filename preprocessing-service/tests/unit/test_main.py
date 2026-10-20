import asyncio

import pytest

import main as main_module


class FakeConsumer:
    def __init__(self):
        self.started = False
        self.stopped = False
        self.closed = False
        self._running = asyncio.Event()

    async def start(self):
        self.started = True
        await self._running.wait()

    async def stop(self):
        self.stopped = True
        self._running.set()

    async def close(self):
        self.closed = True


class FakeServer:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True

    async def wait_closed(self):
        return None


@pytest.fixture
def fakes(monkeypatch):
    consumer = FakeConsumer()
    server = FakeServer()
    calls = {"producer_closed": False, "state_closed": False}

    async def fake_start_health_server(port=None):
        return server

    async def fake_close_producer():
        calls["producer_closed"] = True

    async def fake_close_state_client():
        calls["state_closed"] = True

    monkeypatch.setattr(main_module, "RedisConsumer", lambda: consumer)
    monkeypatch.setattr(main_module, "start_health_server", fake_start_health_server)
    monkeypatch.setattr(main_module, "close_producer", fake_close_producer)
    monkeypatch.setattr(main_module, "close_state_client", fake_close_state_client)
    return consumer, server, calls


async def test_run_worker_starts_consumer_and_health_server(fakes):
    consumer, server, _ = fakes
    stop = asyncio.Event()

    task = asyncio.create_task(main_module.run_worker(stop=stop))
    await asyncio.sleep(0.05)

    assert consumer.started is True
    assert server.closed is False

    stop.set()
    await asyncio.wait_for(task, timeout=5)


async def test_stop_event_shuts_everything_down_in_order(fakes):
    consumer, server, calls = fakes
    stop = asyncio.Event()

    task = asyncio.create_task(main_module.run_worker(stop=stop))
    await asyncio.sleep(0.05)
    stop.set()
    await asyncio.wait_for(task, timeout=5)

    assert consumer.stopped is True
    assert consumer.closed is True
    assert server.closed is True
    assert calls["producer_closed"] is True
    assert calls["state_closed"] is True


async def test_a_hung_consumer_is_cancelled_rather_than_hanging_shutdown(
    monkeypatch, fakes
):
    """
    stop() asks the loop to finish its current message. If the handler is
    wedged, shutdown must not wait forever — SIGTERM has a deadline before
    the orchestrator sends SIGKILL.
    """
    consumer, _, calls = fakes
    monkeypatch.setattr(main_module, "SHUTDOWN_TIMEOUT_SECONDS", 0.1)

    async def never_stops():
        self_stop_ignored = asyncio.Event()
        await self_stop_ignored.wait()

    monkeypatch.setattr(consumer, "stop", lambda: asyncio.sleep(0))
    monkeypatch.setattr(consumer, "start", never_stops)

    stop = asyncio.Event()
    task = asyncio.create_task(main_module.run_worker(stop=stop))
    await asyncio.sleep(0.05)
    stop.set()

    await asyncio.wait_for(task, timeout=5)
    assert calls["producer_closed"] is True
