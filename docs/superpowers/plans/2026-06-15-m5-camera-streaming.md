# MyIoT M5 — Camera Streaming + Off-Market/EOOEIES Support

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Make camera streams real by adding a `go2rtc` bridge, a generic RTSP/MJPEG/snapshot driver with presets for EOOEIES/Reolink/Tapo/Hiseeu, and wiring the existing dashboard MJPEG/snapshot endpoints to actual camera hardware.

**Architecture:** Add a `go2rtc` container to the Docker Compose stack. Introduce a `GenericCameraDriver` that builds stream/snapshot URLs from presets and uses `aiohttp` to fetch snapshots. Extend `PluginLoader` so camera presets resolve by `model`. The existing `/api/cameras/{id}/mjpeg` endpoint proxies through go2rtc when a stream URL is available; `/api/cameras/{id}/snapshot` fetches from the driver directly. ONVIF auto-discovery is explicitly out of scope for this session and will be handled in a follow-up.

**Tech Stack:** Python 3.11+, FastAPI, aiohttp, go2rtc (Docker), SQLAlchemy 2.0, pytest, React + Vite.

---

## Existing files you will modify

| File | Why |
|------|-----|
| `docker-compose.yml` | Add `go2rtc` service and shared network/volume. |
| `hub/.env.example` | Document `GO2RTC_URL`. |
| `hub/core/plugin_loader.py` | Add per-model driver registration and lookup. |
| `hub/services/device_manager.py` | Hydrate registry state after instantiating a driver. |
| `hub/api/camera_stream.py` | Use driver snapshots and proxy MJPEG through go2rtc. |
| `hub/core/manufacturer_maps.py` | Add `generic_camera` manufacturer entry. |
| `app/src/pages/CameraMonitor.tsx` | Add a live-snapshot thumbnail refresher for the active camera. |

## New files you will create

| File | Responsibility |
|------|----------------|
| `data/go2rtc.yaml` | go2rtc base config mounted into the container. |
| `hub/plugins/generic_camera.py` | Generic camera driver with preset URL templates. |
| `hub/tests/test_generic_camera.py` | Unit tests for preset URL construction and state. |
| `hub/tests/test_camera_stream.py` | Tests for snapshot endpoint using a fake camera driver. |

---

## Task 1: Add go2rtc container and config

**Files:**
- Create: `data/go2rtc.yaml`
- Modify: `docker-compose.yml`, `hub/.env.example`

- [x] **Step 1: Create go2rtc base config**

Create `data/go2rtc.yaml`:

```yaml
# go2rtc base configuration — streams are added dynamically by the hub.
log:
  level: info
api:
  listen: ":1984"
rtsp:
  listen: ":8554"
streams: {}
```

- [x] **Step 2: Add go2rtc to Docker Compose**

Modify `docker-compose.yml` to add the service and a shared network:

```yaml
version: "3.9"

services:
  hub:
    build: ./hub
    container_name: myiot-hub
    ports:
      - "8000:8000"
    volumes:
      - ./hub:/app
      - hub-data:/app/data
    env_file:
      - ./hub/.env
    environment:
      - DEBUG=true
      - SEED_DEMO_DEVICES=false
      - GO2RTC_URL=http://go2rtc:1984
    command: uvicorn main:app --host 0.0.0.0 --port 8000 --reload
    depends_on:
      - go2rtc
    networks:
      - myiot

  frontend:
    build:
      context: ./app
      dockerfile: Dockerfile.dev
    container_name: myiot-frontend
    ports:
      - "5173:5173"
    volumes:
      - ./app:/app
      - /app/node_modules
    environment:
      - VITE_API_URL=http://localhost:8000
    command: npm run dev -- --host
    networks:
      - myiot

  go2rtc:
    image: alexxit/go2rtc:latest
    container_name: myiot-go2rtc
    ports:
      - "1984:1984"
      - "8554:8554"
    volumes:
      - ./data/go2rtc.yaml:/config/go2rtc.yaml
    environment:
      - TZ=UTC
    networks:
      - myiot
    restart: unless-stopped

volumes:
  hub-data:

networks:
  myiot:
    driver: bridge
```

- [x] **Step 3: Document GO2RTC_URL in .env.example**

Append to `hub/.env.example`:

```text
# go2rtc bridge URL (used inside Docker network by default)
GO2RTC_URL=http://go2rtc:1984
```

- [x] **Step 4: Verify Compose syntax**

Run:

```bash
docker compose config > /dev/null
```

Expected: no errors. (Docker is not required to run in this dev environment; the backend will fall back to synthetic frames when go2rtc is unreachable.)

---

## Task 2: Extend plugin loader for model-specific drivers

**Files:**
- Modify: `hub/core/plugin_loader.py`

- [x] **Step 1: Add model registry and registration methods**

Modify `hub/core/plugin_loader.py`:

```python
class PluginLoader:
    """Discovers and loads manufacturer plugin modules dynamically."""

    def __init__(self, plugin_package: str = "plugins"):
        self.plugin_package = plugin_package
        self._plugins: Dict[str, Type[BaseDriver]] = {}
        self._model_drivers: Dict[str, Type[BaseDriver]] = {}

    def register_model_driver(
        self, model: str, driver_cls: Type[BaseDriver]
    ) -> None:
        """Register a driver class for a specific device model string."""
        self._model_drivers[model] = driver_cls
        logger.info("Registered model driver '%s' -> %s", model, driver_cls.__name__)

    def get_driver_class(self, model: str) -> Optional[Type[BaseDriver]]:
        """Return the model-specific driver class, if any."""
        return self._model_drivers.get(model)
```

- [x] **Step 2: Call module register hooks during discovery**

Inside `discover()`, after the inner `for attr_name in dir(module):` loop, add:

```python
                if hasattr(module, "register"):
                    try:
                        module.register(self)
                    except Exception as exc:
                        logger.warning(
                            "Failed to register model drivers for plugin '%s': %s",
                            name,
                            exc,
                        )
```

The `discover()` method should now look like:

```python
            for _, name, ispkg in pkgutil.iter_modules(package_path):
                if ispkg or name.startswith("_"):
                    continue

                full_name = f"{self.plugin_package}.{name}"
                try:
                    module = importlib.import_module(full_name)
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if (
                            isinstance(attr, type)
                            and issubclass(attr, BaseDriver)
                            and attr is not BaseDriver
                        ):
                            self._plugins[name] = attr
                            logger.debug(
                                "Registered plugin '%s' -> %s.%s",
                                name,
                                full_name,
                                attr_name,
                            )
                    if hasattr(module, "register"):
                        try:
                            module.register(self)
                        except Exception as exc:
                            logger.warning(
                                "Failed to register model drivers for plugin '%s': %s",
                                name,
                                exc,
                            )
                except Exception as exc:
                    logger.warning("Failed to load plugin '%s': %s", full_name, exc)
                    continue
```

- [x] **Step 3: Run plugin loader tests**

Run:

```bash
cd hub && pytest tests/test_device_manager.py -v
```

Expected: all existing tests still pass.

---

## Task 3: Create the generic camera driver

**Files:**
- Create: `hub/plugins/generic_camera.py`
- Modify: `hub/core/manufacturer_maps.py`

- [x] **Step 1: Create the driver with presets**

Create `hub/plugins/generic_camera.py`:

```python
"""Generic local camera driver with preset URL templates.

Supports RTSP and HTTP-MJPEG cameras from Reolink, Tapo, Hiseeu,
EOOEIES, and other off-market brands that expose a local stream.
"""

import logging
import time
from typing import Any, Dict, Optional

import aiohttp

from core.base_driver import BaseDriver, DeviceState

logger = logging.getLogger(__name__)

CAMERA_PRESETS: Dict[str, Dict[str, Any]] = {
    "generic_onvif": {
        "protocol": "rtsp",
        "stream_template": "rtsp://{username}:{password}@{ip}:554/stream1",
        "snapshot_template": "http://{username}:{password}@{ip}/onvif/snapshot",
    },
    "reolink": {
        "protocol": "rtsp",
        "stream_template": "rtsp://{username}:{password}@{ip}:554/h264Preview_01_main",
        "snapshot_template": (
            "http://{ip}/cgi-bin/api.cgi?cmd=Snap&channel=0&rs=xyz"
            "&user={username}&password={password}"
        ),
    },
    "tapo": {
        "protocol": "rtsp",
        "stream_template": "rtsp://{username}:{password}@{ip}:554/stream1",
        "snapshot_template": "http://{username}:{password}@{ip}/onvif/snapshot",
    },
    "hiseeu": {
        "protocol": "rtsp",
        "stream_template": (
            "rtsp://{username}:{password}@{ip}:554/"
            "user={username}_password={password}_channel=1_stream=0.sdp"
        ),
        "snapshot_template": "http://{username}:{password}@{ip}/snapshot.jpg",
    },
    "eoeeies": {
        "protocol": "rtsp",
        "stream_template": "rtsp://{username}:{password}@{ip}:554/live",
        "snapshot_template": "http://{username}:{password}@{ip}/snapshot",
    },
    "mjpeg": {
        "protocol": "mjpeg",
        "stream_template": "http://{username}:{password}@{ip}/video",
        "snapshot_template": "http://{username}:{password}@{ip}/snapshot",
    },
}


class GenericCameraDriver(BaseDriver):
    """Driver for generic local IP cameras using preset URL templates."""

    def __init__(self, device_config: Dict[str, Any]):
        super().__init__(device_config)
        self._ip = device_config.get(
            "ip", device_config.get("ip_address", "192.168.1.100")
        )
        self._username = device_config.get("username", "")
        self._password = device_config.get("password", "")
        self._preset = device_config.get("model", "generic_onvif")
        self._stream_url = device_config.get("stream_url")
        self._snapshot_url = device_config.get("snapshot_url")
        self._power = device_config.get("power", True)

    def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None or getattr(self._session, "closed", True):
            self._session = aiohttp.ClientSession()
        return self._session

    def _format_url(self, template: str) -> str:
        return template.format(
            ip=self._ip,
            username=self._username,
            password=self._password,
        )

    async def authenticate(self, credentials: Dict[str, Any]) -> bool:
        """Verify camera is reachable by fetching a snapshot."""
        self._username = credentials.get("username", self._username)
        self._password = credentials.get("password", self._password)
        preset = CAMERA_PRESETS.get(self._preset)
        if not preset:
            logger.warning("Unknown camera preset '%s' for %s", self._preset, self.device_id)
            return False
        snapshot_url = self._snapshot_url or self._format_url(preset["snapshot_template"])
        try:
            session = self._ensure_session()
            async with session.get(
                snapshot_url, timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                self._connected = resp.status == 200
                return self._connected
        except Exception as exc:
            logger.warning(
                "GenericCamera authenticate failed for %s: %s", self.device_id, exc
            )
            self._connected = False
            return False

    async def get_state(self) -> DeviceState:
        """Return normalized state including stream and snapshot URLs."""
        preset = CAMERA_PRESETS.get(self._preset, {})
        stream_url = self._stream_url
        snapshot_url = self._snapshot_url
        if preset:
            stream_url = stream_url or self._format_url(preset["stream_template"])
            snapshot_url = snapshot_url or self._format_url(preset["snapshot_template"])
        return DeviceState(
            device_id=self.device_id,
            manufacturer=self.manufacturer,
            model=self._preset,
            device_type="camera",
            online=self._connected,
            state={
                "power": self._power,
                "stream_url": stream_url,
                "snapshot_url": snapshot_url,
                "ip_address": self._ip,
                "protocol": preset.get("protocol"),
            },
            last_updated=time.time(),
        )

    async def set_state(self, payload: Dict[str, Any]) -> bool:
        """Apply privacy (power) toggles."""
        power = payload.get("power")
        if power is not None:
            self._power = bool(power)
        return True

    async def capture_snapshot(self) -> Optional[bytes]:
        """Fetch a JPEG snapshot from the camera."""
        preset = CAMERA_PRESETS.get(self._preset)
        if not preset:
            return None
        snapshot_url = self._snapshot_url or self._format_url(preset["snapshot_template"])
        try:
            session = self._ensure_session()
            async with session.get(
                snapshot_url, timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    return await resp.read()
                logger.warning(
                    "Snapshot for %s returned HTTP %s", self.device_id, resp.status
                )
                return None
        except Exception as exc:
            logger.warning("Snapshot failed for %s: %s", self.device_id, exc)
            return None

    async def get_stream_url(self) -> Optional[str]:
        """Return the camera's RTSP/MJPEG stream URL."""
        if self._stream_url:
            return self._stream_url
        preset = CAMERA_PRESETS.get(self._preset)
        if not preset:
            return None
        return self._format_url(preset["stream_template"])

    async def disconnect(self) -> None:
        """Close the aiohttp session."""
        if self._session and not getattr(self._session, "closed", True):
            await self._session.close()
        self._connected = False


def register(plugin_loader) -> None:
    """Register every preset as a model-specific driver."""
    for preset in CAMERA_PRESETS:
        plugin_loader.register_model_driver(preset, GenericCameraDriver)
```

- [x] **Step 2: Add generic_camera manufacturer map entry**

Append to `hub/core/manufacturer_maps.py` inside `MANUFACTURER_MAPS`:

```python
    "generic_camera": {
        "protocol": "rtsp",
        "auth_type": "user_password",
        "device_types": ["camera"],
        "payload_map": {
            "camera": {
                "power": "power",
            }
        },
        "discovery": {
            "method": "manual",
        },
    },
```

- [x] **Step 3: Run the new driver tests (will be created in Task 6)**

For now, verify the file imports cleanly:

```bash
cd hub && python -c "from plugins.generic_camera import GenericCameraDriver, CAMERA_PRESETS; print(len(CAMERA_PRESETS), 'presets')"
```

Expected output: `6 presets`.

---

## Task 4: Hydrate registry state after driver instantiation

**Files:**
- Modify: `hub/services/device_manager.py`

- [x] **Step 1: Update `_add_driver` to publish initial state**

After the authentication block in `hub/services/device_manager.py`, add:

```python
        # Publish initial driver state to the registry so stream URLs, etc.
        # are visible to API consumers immediately after add/load.
        try:
            initial_state = await driver.get_state()
            if initial_state:
                await self.registry.update(cfg.device_id, initial_state)
        except Exception as exc:
            logger.warning(
                "Failed to publish initial state for %s: %s", cfg.device_id, exc
            )
```

The end of `_add_driver` should look like:

```python
        try:
            await driver.authenticate(credentials)
        except Exception as exc:
            logger.warning(
                "Authentication skipped for %s (%s): %s",
                cfg.device_id,
                cfg.manufacturer,
                exc,
            )

        try:
            initial_state = await driver.get_state()
            if initial_state:
                await self.registry.update(cfg.device_id, initial_state)
        except Exception as exc:
            logger.warning(
                "Failed to publish initial state for %s: %s", cfg.device_id, exc
            )

        logger.info("Instantiated driver for %s (%s)", cfg.device_id, cfg.manufacturer)
```

- [x] **Step 2: Run device manager tests**

```bash
cd hub && pytest tests/test_device_manager.py tests/test_local_driver_end_to_end.py -v
```

Expected: all pass.

---

## Task 5: Wire real snapshots and MJPEG proxy

**Files:**
- Modify: `hub/api/camera_stream.py`

- [x] **Step 1: Add go2rtc helpers**

At the top of `hub/api/camera_stream.py`, add imports:

```python
import os

import aiohttp
```

Add helper functions after the imports / logger setup:

```python
GO2RTC_URL = os.environ.get("GO2RTC_URL", "http://localhost:1984")


async def _proxy_go2rtc_mjpeg(
    camera_id: str, stream_url: str
) -> AsyncGenerator[bytes, None]:
    """Push a stream to go2rtc and yield its MJPEG response chunks."""
    name = f"myiot_{camera_id}"
    session = aiohttp.ClientSession()
    try:
        add_url = f"{GO2RTC_URL}/api/streams"
        async with session.post(
            add_url,
            params={"src": stream_url, "name": name},
            timeout=aiohttp.ClientTimeout(total=5),
        ) as add_resp:
            if add_resp.status not in (200, 201, 204):
                body = await add_resp.text()
                logger.warning(
                    "go2rtc add stream returned %s: %s", add_resp.status, body
                )
                return

        mjpeg_url = f"{GO2RTC_URL}/api/stream.mjpeg"
        async with session.get(
            mjpeg_url,
            params={"src": name},
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            if resp.status != 200:
                logger.warning(
                    "go2rtc MJPEG returned %s for %s", resp.status, camera_id
                )
                return
            async for chunk in resp.content.iter_chunked(8192):
                yield chunk
    finally:
        await session.close()
```

- [x] **Step 2: Replace the snapshot endpoint with driver fallback**

Replace the body of `camera_snapshot` in `hub/api/camera_stream.py` with:

```python
    manager = request.app.state.device_manager
    driver = None
    try:
        async with manager._lock:
            driver = manager._drivers.get(camera_id)
    except Exception:
        driver = None

    if driver and device.state.get("power", True) and status == "LIVE":
        try:
            data = await driver.capture_snapshot()
            if data:
                return StreamingResponse(
                    io.BytesIO(data),
                    media_type="image/jpeg",
                    headers={"Cache-Control": "no-cache"},
                )
        except Exception as exc:
            logger.warning("capture_snapshot failed for %s: %s", camera_id, exc)

    # Fallback to synthetic frame
    camera_name = device.state.get("name", camera_id)
    stream_url = device.state.get("stream_url")
    timestamp = time.time()
    if status == "LIVE":
        frame = _generate_live_frame(640, 360, camera_name, 0, 0, 1.0, timestamp)
    else:
        frame = _generate_status_frame(640, 360, camera_name, status, stream_url or "", timestamp)

    return StreamingResponse(
        io.BytesIO(frame),
        media_type="image/jpeg",
        headers={"Cache-Control": "no-cache"},
    )
```

- [x] **Step 3: Replace the MJPEG generator with go2rtc proxy**

Replace `async def _mjpeg_stream_generator(...)` in `hub/api/camera_stream.py` with:

```python
async def _mjpeg_stream_generator(
    camera_id: str,
    camera_name: str,
    status: str,
    stream_url: Optional[str],
    fps: int = 8,
) -> AsyncGenerator[bytes, None]:
    """Generate an MJPEG stream.

    If the camera is online, has a stream URL, and go2rtc is reachable,
    proxy the transcoded MJPEG feed from go2rtc. Otherwise, fall back to
    synthetic status frames.
    """
    width, height = 640, 360
    frame_delay = 1.0 / fps

    if stream_url and status == "LIVE":
        try:
            async for chunk in _proxy_go2rtc_mjpeg(camera_id, stream_url):
                yield chunk
            return
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("go2rtc proxy failed for %s: %s", camera_id, exc)

    # Synthetic fallback
    try:
        while True:
            timestamp = time.time()
            if status == "LIVE":
                frame = _generate_live_frame(width, height, camera_name, 0, 0, 1.0, timestamp)
            else:
                details = stream_url if stream_url else "No stream configured"
                frame = _generate_status_frame(width, height, camera_name, status, details, timestamp)
            yield (
                b'--frame\r\nContent-Type: image/jpeg\r\nContent-Length: '
                + str(len(frame)).encode()
                + b'\r\n\r\n'
                + frame
                + b'\r\n'
            )
            await asyncio.sleep(frame_delay)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.error("MJPEG stream error for %s: %s", camera_id, exc)
        while True:
            timestamp = time.time()
            frame = _generate_status_frame(width, height, camera_name, "ERROR", str(exc), timestamp)
            yield (
                b'--frame\r\nContent-Type: image/jpeg\r\nContent-Length: '
                + str(len(frame)).encode()
                + b'\r\n\r\n'
                + frame
                + b'\r\n'
            )
            await asyncio.sleep(1)
```

- [x] **Step 4: Verify camera_stream imports cleanly**

```bash
cd hub && python -c "from api import camera_stream; print('ok')"
```

Expected: `ok`.

---

## Task 6: Add manual camera support and refresh stream URL

**Files:**
- Modify: `hub/api/routes.py`

- [x] **Step 1: Ensure manual add carries camera fields**

The existing `ManualDeviceRequest` already has `custom_map`, `ip_address`, `protocol`, `model`, etc. When `device_type == "camera"`, the generic driver receives `custom_map` in its config. No route change is required, but verify the stored `DeviceConfig` persists `custom_map` (it does in `add_manual_device`).

- [x] **Step 2: Add a refresh stream endpoint (optional but useful)**

Add to `hub/api/routes.py` after `get_stream_uri`:

```python
@router.post("/api/streams/{device_id}/refresh")
async def refresh_stream_uri(request: Request, device_id: str) -> StreamResponse:
    """Re-resolve the stream URL from the driver and update the registry."""
    registry = request.app.state.registry
    device = await registry.get(device_id)
    if not device or device.device_type != "camera":
        raise HTTPException(status_code=404, detail="Camera not found")

    manager = request.app.state.device_manager
    driver = None
    async with manager._lock:
        driver = manager._drivers.get(device_id)

    stream_url = None
    if driver is not None:
        try:
            stream_url = await driver.get_stream_url()
            new_state = await driver.get_state()
            if new_state:
                await registry.update(device_id, new_state)
        except Exception as exc:
            logger.warning("Failed to refresh stream for %s: %s", device_id, exc)
            raise HTTPException(status_code=502, detail=str(exc))

    return StreamResponse(stream_url=stream_url)
```

- [x] **Step 3: Verify routes compile**

```bash
cd hub && python -c "from api import routes; print('ok')"
```

Expected: `ok`.

---

## Task 7: Frontend snapshot thumbnail

**Files:**
- Modify: `app/src/pages/CameraMonitor.tsx`
- Modify: `app/src/api/client.ts` (if needed)

- [x] **Step 1: Add a refreshable snapshot panel in the controls tab**

In `app/src/pages/CameraMonitor.tsx`, inside the `sidebarTab === 'controls' && activeCamera` block, after the info box, add:

```tsx
            {/* Live snapshot */}
            <div className="rounded-lg p-2" style={{ backgroundColor: 'var(--bg-inset)' }}>
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-medium" style={{ color: 'var(--text-muted)' }}>Snapshot</span>
                <button
                  onClick={() => setNow(Date.now())}
                  className="text-[10px]"
                  style={{ color: 'var(--accent-primary)' }}
                >Refresh</button>
              </div>
              {activeCamera.online && activeCamera.power ? (
                <img
                  key={now}
                  src={`/api/cameras/${activeCamera.id}/snapshot?ts=${now}`}
                  alt={`${activeCamera.name} snapshot`}
                  className="mt-2 h-32 w-full rounded-lg object-cover"
                />
              ) : (
                <div className="mt-2 flex h-32 items-center justify-center rounded-lg" style={{ backgroundColor: 'var(--bg-elevated)' }}>
                  <span className="text-[10px]" style={{ color: 'var(--text-muted)' }}>Camera offline</span>
                </div>
              )}
            </div>
```

- [x] **Step 2: Verify TypeScript compiles**

Run:

```bash
cd app && npm run build
```

Expected: build succeeds (or `npm run dev` starts without type errors). For a quick check you can also run:

```bash
cd app && npx tsc --noEmit
```

---

## Task 8: Write tests

**Files:**
- Create: `hub/tests/test_generic_camera.py`
- Create: `hub/tests/test_camera_stream.py`

- [x] **Step 1: Test preset URL construction**

Create `hub/tests/test_generic_camera.py`:

```python
import pytest

from plugins.generic_camera import GenericCameraDriver, CAMERA_PRESETS


@pytest.mark.asyncio
async def test_reolink_url_templates():
    config = {
        "device_id": "cam-reolink-01",
        "manufacturer": "generic_camera",
        "model": "reolink",
        "device_type": "camera",
        "ip": "192.168.1.50",
        "username": "admin",
        "password": "secret",
    }
    driver = GenericCameraDriver(config)
    stream_url = await driver.get_stream_url()
    assert stream_url == "rtsp://admin:secret@192.168.1.50:554/h264Preview_01_main"

    state = await driver.get_state()
    assert state.state["snapshot_url"].startswith("http://192.168.1.50/cgi-bin/api.cgi")
    assert "user=admin" in state.state["snapshot_url"]
    assert "password=secret" in state.state["snapshot_url"]


@pytest.mark.asyncio
async def test_set_state_toggles_power():
    config = {
        "device_id": "cam-tapo-01",
        "manufacturer": "generic_camera",
        "model": "tapo",
        "device_type": "camera",
        "ip": "192.168.1.51",
        "username": "user",
        "password": "pass",
    }
    driver = GenericCameraDriver(config)
    await driver.set_state({"power": False})
    state = await driver.get_state()
    assert state.state["power"] is False

    await driver.set_state({"power": True})
    state = await driver.get_state()
    assert state.state["power"] is True


@pytest.mark.asyncio
async def test_custom_stream_url_takes_precedence():
    config = {
        "device_id": "cam-custom-01",
        "manufacturer": "generic_camera",
        "model": "generic_onvif",
        "device_type": "camera",
        "ip": "192.168.1.52",
        "stream_url": "rtsp://custom/url",
        "snapshot_url": "http://custom/snap",
    }
    driver = GenericCameraDriver(config)
    assert await driver.get_stream_url() == "rtsp://custom/url"
    state = await driver.get_state()
    assert state.state["snapshot_url"] == "http://custom/snap"
```

- [x] **Step 2: Test snapshot endpoint with a fake camera driver**

Create `hub/tests/test_camera_stream.py`:

```python
import time
import uuid
from typing import Any, Dict

import pytest
from httpx import ASGITransport, AsyncClient

from core.base_driver import BaseDriver, DeviceState
from main import app


class FakeCameraDriver(BaseDriver):
    """Minimal camera driver that returns a known snapshot."""

    def __init__(self, device_config: Dict[str, Any]):
        super().__init__(device_config)
        self._connected = True
        self._power = True

    async def authenticate(self, credentials: Dict[str, Any]) -> bool:
        return True

    async def get_state(self) -> DeviceState:
        return DeviceState(
            device_id=self.device_id,
            manufacturer=self.manufacturer,
            model=self.model,
            device_type="camera",
            online=self._connected,
            state={"power": self._power},
            last_updated=time.time(),
        )

    async def set_state(self, payload: Dict[str, Any]) -> bool:
        power = payload.get("power")
        if power is not None:
            self._power = bool(power)
        return True

    async def capture_snapshot(self) -> bytes:
        return b"FAKE_JPEG_BYTES"

    async def disconnect(self) -> None:
        self._connected = False


@pytest.mark.asyncio
async def test_camera_snapshot_uses_driver(db_session):
    device_id = f"fake-cam-{uuid.uuid4().hex[:8]}"

    def fake_get_driver_class(model: str):
        if model == "fake-cam":
            return FakeCameraDriver
        return None

    async with app.router.lifespan_context(app):
        app.state.plugin_loader.get_driver_class = fake_get_driver_class

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            add_response = await client.post(
                "/api/devices/manual",
                json={
                    "device_id": device_id,
                    "manufacturer": "fake",
                    "model": "fake-cam",
                    "device_type": "camera",
                    "name": "Fake Camera",
                },
            )
            assert add_response.status_code == 200

            snapshot_response = await client.get(f"/api/cameras/{device_id}/snapshot")
            assert snapshot_response.status_code == 200
            assert snapshot_response.headers["content-type"] == "image/jpeg"
            assert snapshot_response.content == b"FAKE_JPEG_BYTES"
```

- [x] **Step 3: Run the full test suite**

```bash
cd hub && pytest -v
```

Expected: all tests pass.

---

## Task 9: Verify the stack manually

**Files:** none

- [x] **Step 1: Start the backend without Docker**

```bash
cd hub && uvicorn main:app --reload
```

- [x] **Step 2: Add a test camera manually**

```bash
curl -X POST http://localhost:8000/api/devices/manual \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "test-cam-1",
    "manufacturer": "generic_camera",
    "model": "eoeeies",
    "device_type": "camera",
    "name": "Test EOOEIES",
    "ip_address": "192.168.1.60",
    "custom_map": {"username": "admin", "password": "admin"}
  }'
```

Expected: `{"success": true, "device_id": "test-cam-1"}`.

- [x] **Step 3: Check stream URL**

```bash
curl http://localhost:8000/api/streams/test-cam-1
```

Expected: a JSON object with a non-null `stream_url` matching the EOOEIES preset.

- [x] **Step 4: Check snapshot endpoint returns a JPEG**

```bash
curl -I http://localhost:8000/api/cameras/test-cam-1/snapshot
```

Expected: `Content-Type: image/jpeg`. If the camera is offline, it returns a synthetic JPEG frame.

- [x] **Step 5: Check MJPEG endpoint**

```bash
curl -N http://localhost:8000/api/cameras/test-cam-1/mjpeg | head -c 500
```

Expected: multipart JPEG stream. Without go2rtc running it will be the synthetic feed.

---

## Self-review checklist

1. **Spec coverage:**
   - go2rtc container added → Task 1 ✅
   - Generic camera driver with presets → Task 3 ✅
   - Real snapshot + MJPEG endpoints → Task 5 ✅
   - Dashboard still consumes MJPEG and gets snapshot widget → Task 7 ✅
   - ONVIF auto-discovery is explicitly deferred ✅

2. **Placeholder scan:** No TBD/TODO/fill-in-later steps. ✅

3. **Type consistency:** `GenericCameraDriver` implements `BaseDriver`. `capture_snapshot()` and `get_stream_url()` match optional base methods. ✅

---

## Execution handoff

**Plan saved to:** `docs/superpowers/plans/2026-06-15-m5-camera-streaming.md`

**Two execution options:**

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks.
2. **Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach do you want?
