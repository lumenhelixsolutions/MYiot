import asyncio
import threading

import pytest
from fastapi.testclient import TestClient

from discovery.listener import NetworkDiscoveryListener
from main import app


@pytest.mark.asyncio
async def test_schedule_coroutine_from_background_thread():
    seen: list[str] = []

    async def on_device_found(device_info):
        seen.append(device_info["device_id"])

    listener = NetworkDiscoveryListener(
        on_device_found=on_device_found,
        on_state_change=lambda d: None,
    )
    await listener.start()

    try:
        barrier = threading.Barrier(2)
        errors: list[BaseException] = []

        def worker():
            try:
                barrier.wait(timeout=5)
                listener._schedule_coroutine(
                    listener._emit_device_found(
                        {"device_id": "mdns_test._hap._tcp.local."}
                    )
                )
            except BaseException as exc:
                errors.append(exc)

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        barrier.wait(timeout=5)
        await asyncio.sleep(0.2)
        thread.join(timeout=5)

        assert not errors
        assert "mdns_test._hap._tcp.local." in seen
    finally:
        await listener.stop()


@pytest.mark.asyncio
async def test_discovery_scan_completes():
    listener = NetworkDiscoveryListener(
        on_device_found=lambda d: None,
        on_state_change=lambda d: None,
    )
    listener._running = True

    await listener.start_active_scan()
    assert listener.get_scan_status()["active"] is True

    if listener._scan_task:
        try:
            await asyncio.wait_for(listener._scan_task, timeout=20)
        except asyncio.TimeoutError:
            await listener.stop_active_scan()

    final = listener.get_scan_status()
    assert final["active"] is False
    assert final["progress"] == 100


def test_discovery_rest_endpoints():
    with TestClient(app) as client:
        status = client.get("/api/discovery/status")
        assert status.status_code == 200
        body = status.json()
        assert "active" in body
        assert "progress" in body

        devices = client.get("/api/discovery/devices")
        assert devices.status_code == 200
        assert isinstance(devices.json(), list)