# MyIoT Phase 1 — Foundation, Persistence & Local Drivers

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Turn the existing FastAPI/React skeleton into a runnable, testable, persist-backed hub that can discover and control local IP lights and plugs.

**Architecture:** Keep the existing plugin driver system and REST/WebSocket surface, add a `DeviceManager` that owns plugin lifecycles, a `StatePersistenceAdapter` that writes state snapshots to SQLite, and Docker Compose for one-command local development.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy 2.0 (async/aiosqlite), pytest, Docker Compose, React + Vite.

---

## Existing files you will modify

| File | Why |
|------|-----|
| `hub/main.py` | Lifespan wiring, optional demo seed, load persisted devices, attach persistence adapter and device manager. |
| `hub/models/database.py` | Add `last_state` column to `DeviceConfig`; add helper to update it. |
| `hub/api/routes.py` | Route `/api/devices/{id}/command` through `DeviceManager` instead of raw dispatcher. |
| `hub/requirements.txt` | Add `python-dotenv`, `pytest`, `pytest-asyncio`, `httpx`, `aiolifx`. |
| `hub/plugins/lifx.py` | Replace cloud REST with local LAN `aiolifx` (optional but recommended for local-first). |

## New files you will create

| File | Responsibility |
|------|----------------|
| `docker-compose.yml` | Runs FastAPI + Vite dev environment. |
| `hub/Dockerfile` | Container for the FastAPI backend. |
| `hub/.env.example` | Documented environment variables. |
| `hub/pyproject.toml` | pytest, ruff, mypy configuration. |
| `hub/services/state_persistence.py` | Subscribes to `StateRegistry` and throttles writes to SQLite. |
| `hub/services/device_manager.py` | Loads DB configs, instantiates plugins, dispatches commands, polls state. |
| `tests/conftest.py` | Shared pytest fixtures (app, registry, db session). |
| `tests/test_health.py` | Health endpoint sanity test. |
| `tests/test_state_persistence.py` | State snapshot persistence tests. |
| `tests/test_device_manager.py` | Command dispatch through simulator plugin. |

---

## Task 1: One-command dev environment (M1)

**Files:**
- Create: `hub/.env.example`, `hub/Dockerfile`, `docker-compose.yml`, `hub/pyproject.toml`
- Modify: `hub/requirements.txt`, `hub/main.py`

- [x] **Step 1: Add environment config**

Create `hub/.env.example`:

```text
# MyIoT backend configuration
LOG_LEVEL=INFO
HOST=0.0.0.0
PORT=8000
DEBUG=true
DATABASE_URL=sqlite+aiosqlite:///./data/hub.db
SECRET_KEY=change-me-in-production
SEED_DEMO_DEVICES=false
```

Create `hub/.env` (copied from example) and add `.env` to `.gitignore` if not present.

- [x] **Step 2: Add dev/test dependencies**

Modify `hub/requirements.txt` to append:

```text
python-dotenv>=1.0.0
pytest>=8.0.0
pytest-asyncio>=0.23.0
httpx>=0.27.0
aiolifx>=1.0.0
```

- [x] **Step 3: Add tool configuration**

Create `hub/pyproject.toml`:

```toml
[project]
name = "myiot-hub"
version = "0.1.0"
requires-python = ">=3.11"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
pythonpath = [".", ".."]

[tool.ruff]
line-length = 100
select = ["E", "F", "W", "I"]

[tool.mypy]
python_version = "3.11"
warn_return_any = true
warn_unused_configs = true
```

- [x] **Step 4: Containerize the backend**

Create `hub/Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

ENV PYTHONPATH=/app
ENV HOST=0.0.0.0
ENV PORT=8000

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

- [x] **Step 5: Add Docker Compose stack**

Create `docker-compose.yml` at project root:

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
    environment:
      - DEBUG=true
      - SEED_DEMO_DEVICES=false
    command: uvicorn main:app --host 0.0.0.0 --port 8000 --reload

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

volumes:
  hub-data:
```

Create `app/Dockerfile.dev`:

```dockerfile
FROM node:20-slim
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm install
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host"]
```

- [x] **Step 6: Load `.env` and make demo seed optional**

Modify the top of `hub/main.py`:

```python
import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException, Request
...
```

Then wrap the seed call in lifespan:

```python
    # Seed initial devices only when explicitly requested
    if os.environ.get("SEED_DEMO_DEVICES", "false").lower() == "true":
        try:
            await _seed_devices(app.state.registry)
            logger.info("Initial devices seeded")
        except Exception as exc:
            logger.warning("Device seeding failed: %s", exc)
    else:
        logger.info("Demo device seeding disabled")
```

- [x] **Step 7: Run the stack**

Run:

```bash
cd hub && pip install -r requirements.txt
cd .. && docker compose up --build
```

Expected: `http://localhost:8000/health` returns JSON with `status: healthy`.

- [x] **Step 8: Commit**

```bash
git add docker-compose.yml hub/Dockerfile app/Dockerfile.dev hub/.env.example hub/pyproject.toml hub/requirements.txt hub/main.py .gitignore
git commit -m "chore: docker compose, env config, optional demo seed"
```

---

## Task 2: Persist device state snapshots (M2)

**Files:**
- Create: `hub/services/state_persistence.py`
- Modify: `hub/models/database.py`, `hub/main.py`
- Test: `tests/test_state_persistence.py`

- [x] **Step 1: Add `last_state` to the device config table**

Modify `hub/models/database.py` to add `import time` at the top with the other imports.

Then inside `DeviceConfig`:

```python
from sqlalchemy import (
    create_engine,
    Column,
    String,
    Integer,
    Float,
    Boolean,
    JSON,
    select,
    desc,
)
```

Add columns to `DeviceConfig` after `enabled`:

```python
    enabled = Column(Boolean, default=True)
    last_state = Column(JSON, nullable=True)
    last_seen_at = Column(Float, nullable=True)
```

Add helper function at module level:

```python
async def update_device_state(
    session: AsyncSession, device_id: str, state: dict
) -> None:
    """Update the persisted last_state and last_seen_at for a device."""
    result = await session.execute(
        select(DeviceConfig).where(DeviceConfig.device_id == device_id)
    )
    db_device = result.scalar_one_or_none()
    if db_device:
        db_device.last_state = state
        db_device.last_seen_at = time.time()
        await session.commit()
```

- [x] **Step 2: Create the persistence adapter**

Create `hub/services/state_persistence.py`:

```python
"""State persistence adapter.

Subscribes to StateRegistry updates and writes throttled snapshots to SQLite.
"""

import asyncio
import logging
from typing import Any, Dict

from sqlalchemy import select

from core.base_driver import DeviceState
from models.database import get_async_session_factory, update_device_state

logger = logging.getLogger(__name__)


class StatePersistenceAdapter:
    """Writes device state snapshots to the database on a debounced schedule."""

    def __init__(self, debounce_seconds: float = 2.0):
        self.debounce_seconds = debounce_seconds
        self._pending: Dict[str, DeviceState] = {}
        self._task: asyncio.Task | None = None
        self._registry = None

    def attach(self, registry) -> None:
        """Subscribe to registry updates."""
        self._registry = registry
        registry.subscribe(self._on_state_change)
        logger.info("StatePersistenceAdapter attached")

    async def detach(self) -> None:
        """Cancel pending writes and unsubscribe."""
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._registry:
            # Note: StateRegistry.unsubscribe expects the same callback object.
            self._registry.unsubscribe(self._on_state_change)

    async def _on_state_change(self, device_id: str, state: DeviceState) -> None:
        self._pending[device_id] = state
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._flush_after_debounce())

    async def _flush_after_debounce(self) -> None:
        await asyncio.sleep(self.debounce_seconds)
        await self._flush()

    async def _flush(self) -> None:
        if not self._pending:
            return

        batch = dict(self._pending)
        self._pending.clear()

        factory = get_async_session_factory()
        async with factory() as session:
            for device_id, state in batch.items():
                try:
                    await update_device_state(
                        session,
                        device_id,
                        {
                            "online": state.online,
                            "state": state.state,
                            "last_updated": state.last_updated,
                        },
                    )
                except Exception as exc:
                    logger.warning("Failed to persist state for %s: %s", device_id, exc)


async def load_devices_into_registry(registry) -> None:
    """Hydrate the registry from persisted device configs."""
    from core.base_driver import DeviceState as DS
    from models.database import DeviceConfig, get_async_session_factory

    factory = get_async_session_factory()
    async with factory() as session:
        result = await session.execute(select(DeviceConfig).where(DeviceConfig.enabled == True))
        configs = result.scalars().all()

    for cfg in configs:
        last_state = cfg.last_state or {}
        state = DS(
            device_id=cfg.device_id,
            manufacturer=cfg.manufacturer,
            model=cfg.model or "unknown",
            device_type=cfg.device_type,
            online=last_state.get("online", False),
            state=last_state.get("state", {}),
            last_updated=last_state.get("last_updated", 0.0),
        )
        await registry.update(cfg.device_id, state)
        logger.info("Restored device %s from database", cfg.device_id)
```

- [x] **Step 3: Wire adapter into lifespan**

Modify `hub/main.py`:

```python
from services.state_persistence import StatePersistenceAdapter, load_devices_into_registry
```

In lifespan, after registry init and before discovery:

```python
    # Load previously persisted devices
    try:
        await load_devices_into_registry(app.state.registry)
        logger.info("Persisted devices loaded into registry")
    except Exception as exc:
        logger.warning("Failed to load persisted devices: %s", exc)

    # Attach state persistence adapter
    app.state.persistence_adapter = StatePersistenceAdapter()
    app.state.persistence_adapter.attach(app.state.registry)
    logger.info("State persistence adapter attached")
```

In shutdown, before closing dispatcher:

```python
    try:
        await app.state.persistence_adapter.detach()
        logger.info("State persistence adapter detached")
    except Exception as exc:
        logger.warning("Error detaching persistence adapter: %s", exc)
```

- [x] **Step 4: Write persistence tests**

Create `tests/conftest.py`:

```python
import os
import pytest
import pytest_asyncio

# Use an in-memory database for tests
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("SEED_DEMO_DEVICES", "false")

from main import app
from models.database import init_db, get_async_session_factory


@pytest_asyncio.fixture
async def db_session():
    await init_db()
    factory = get_async_session_factory()
    async with factory() as session:
        yield session


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    return TestClient(app)
```

Create `tests/test_state_persistence.py`:

```python
import asyncio

import pytest
from sqlalchemy import select

from core.base_driver import DeviceState
from core.state_registry import StateRegistry
from models.database import DeviceConfig, get_async_session_factory
from services.state_persistence import StatePersistenceAdapter


@pytest.mark.asyncio
async def test_persistence_adapter_writes_state(db_session):
    registry = StateRegistry()
    adapter = StatePersistenceAdapter(debounce_seconds=0.1)
    adapter.attach(registry)

    state = DeviceState(
        device_id="test-plug-1",
        manufacturer="tp_link_kasa",
        model="KP125",
        device_type="plug",
        online=True,
        state={"power": True},
        last_updated=1234567890.0,
    )
    await registry.update("test-plug-1", state)
    await asyncio.sleep(0.2)

    factory = get_async_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(DeviceConfig).where(DeviceConfig.device_id == "test-plug-1")
        )
        cfg = result.scalar_one_or_none()
        assert cfg is not None
        assert cfg.last_state["state"]["power"] is True

    await adapter.detach()
```

- [x] **Step 5: Run persistence tests**

```bash
cd hub && pytest tests/test_state_persistence.py -v
```

Expected: PASS.

- [x] **Step 6: Commit**

```bash
git add hub/services/state_persistence.py hub/models/database.py hub/main.py tests/
git commit -m "feat: persist device state snapshots to sqlite"
```

---

## Task 3: Device manager and command routing (M3 core)

**Files:**
- Create: `hub/services/device_manager.py`
- Modify: `hub/main.py`, `hub/api/routes.py`
- Test: `tests/test_device_manager.py`

- [x] **Step 1: Create the device manager**

Create `hub/services/device_manager.py`:

```python
"""Device manager orchestrates plugin drivers and command dispatch."""

import logging
from typing import Any, Dict, Optional

from sqlalchemy import select

from core.base_driver import BaseDriver, DeviceState
from core.plugin_loader import PluginLoader
from models.database import DeviceConfig, get_async_session_factory

logger = logging.getLogger(__name__)


class DeviceManager:
    """Owns driver instances, maps device IDs to plugins, and dispatches commands."""

    def __init__(self, registry, plugin_loader: PluginLoader):
        self.registry = registry
        self.plugin_loader = plugin_loader
        self._drivers: Dict[str, BaseDriver] = {}

    async def load_devices(self) -> None:
        """Load enabled device configs from DB and instantiate drivers."""
        factory = get_async_session_factory()
        async with factory() as session:
            result = await session.execute(
                select(DeviceConfig).where(DeviceConfig.enabled == True)
            )
            configs = result.scalars().all()

        for cfg in configs:
            await self._add_driver(cfg)

    async def _add_driver(self, cfg: DeviceConfig) -> None:
        plugin_cls = self.plugin_loader.get_plugin(cfg.manufacturer)
        if plugin_cls is None:
            logger.warning("No plugin for manufacturer %s", cfg.manufacturer)
            return

        device_config = {
            "device_id": cfg.device_id,
            "manufacturer": cfg.manufacturer,
            "model": cfg.model or "unknown",
            "device_type": cfg.device_type,
            "ip": cfg.ip_address,
            "port": cfg.port,
            "protocol": cfg.protocol,
            **(cfg.custom_map or {}),
        }
        driver = plugin_cls(device_config)
        self._drivers[cfg.device_id] = driver
        logger.info("Instantiated driver for %s (%s)", cfg.device_id, cfg.manufacturer)

    async def authenticate(self, device_id: str, credentials: Dict[str, Any]) -> bool:
        driver = self._drivers.get(device_id)
        if not driver:
            return False
        return await driver.authenticate(credentials)

    async def get_state(self, device_id: str) -> Optional[DeviceState]:
        driver = self._drivers.get(device_id)
        if not driver:
            return None
        return await driver.get_state()

    async def set_state(self, device_id: str, payload: Dict[str, Any]) -> bool:
        driver = self._drivers.get(device_id)
        if not driver:
            logger.warning("No driver for device %s", device_id)
            return False
        success = await driver.set_state(payload)
        if success:
            # Optimistically refresh state
            new_state = await driver.get_state()
            if new_state:
                await self.registry.update(device_id, new_state)
        return success

    async def add_device(self, cfg: DeviceConfig) -> None:
        await self._add_driver(cfg)

    async def remove_device(self, device_id: str) -> None:
        driver = self._drivers.pop(device_id, None)
        if driver:
            await driver.disconnect()

    async def disconnect_all(self) -> None:
        for driver in self._drivers.values():
            await driver.disconnect()
        self._drivers.clear()
```

- [x] **Step 2: Wire device manager into lifespan**

Modify `hub/main.py`:

```python
from services.device_manager import DeviceManager
```

After plugin discovery in lifespan:

```python
    # Initialize device manager
    app.state.device_manager = DeviceManager(
        registry=app.state.registry,
        plugin_loader=app.state.plugin_loader,
    )
    await app.state.device_manager.load_devices()
    logger.info("Device manager initialized")
```

In shutdown:

```python
    try:
        await app.state.device_manager.disconnect_all()
        logger.info("Device manager disconnected")
    except Exception as exc:
        logger.warning("Error disconnecting device manager: %s", exc)
```

- [x] **Step 3: Route commands through the device manager**

Modify `hub/api/routes.py` `send_command`:

```python
@router.post("/api/devices/{device_id}/command")
async def send_command(
    request: Request,
    device_id: str,
    command: DeviceCommandRequest,
) -> Dict[str, Any]:
    registry = request.app.state.registry
    device = await registry.get(device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    manager = request.app.state.device_manager
    success = await manager.set_state(device_id, command.payload)

    # Log the command
    try:
        session_gen = get_db_session()
        session = await session_gen.__anext__()
        await log_event(
            session,
            event_type="command",
            device_id=device_id,
            manufacturer=device.manufacturer,
            details={"command": command.payload, "success": success},
        )
    except Exception as exc:
        logger.warning("Failed to log command event: %s", exc)

    if not success:
        raise HTTPException(status_code=502, detail="Command failed")

    return {"success": True, "device_id": device_id}
```

- [x] **Step 4: Test command routing with simulator**

Create `tests/test_device_manager.py`:

```python
import pytest
from models.database import DeviceConfig, get_async_session_factory
from services.device_manager import DeviceManager


@pytest.mark.asyncio
async def test_simulator_command(db_session):
    from core.plugin_loader import PluginLoader
    from core.state_registry import StateRegistry

    registry = StateRegistry()
    loader = PluginLoader()
    loader.discover()

    # Add a simulator device config
    factory = get_async_session_factory()
    async with factory() as session:
        cfg = DeviceConfig(
            device_id="sim-plug-01",
            manufacturer="simulator",
            device_type="plug",
            enabled=True,
        )
        session.add(cfg)
        await session.commit()

    manager = DeviceManager(registry, loader)
    await manager.load_devices()

    success = await manager.set_state("sim-plug-01", {"power": False})
    assert success is True

    state = await registry.get("sim-plug-01")
    assert state.state["power"] is False
```

- [x] **Step 5: Run device manager tests**

```bash
cd hub && pytest tests/test_device_manager.py -v
```

Expected: PASS.

- [x] **Step 6: Commit**

```bash
git add hub/services/device_manager.py hub/api/routes.py hub/main.py tests/test_device_manager.py
git commit -m "feat: device manager orchestrates plugin commands"
```

---

## Task 4: Validate local drivers (M3 acceptance)

**Files:**
- Modify: `hub/plugins/lifx.py` (optional local conversion)
- Test: `tests/test_local_drivers.py`

- [x] **Step 1: Create a manual add + command end-to-end test**

Create `tests/test_local_drivers.py`:

```python
import pytest
from fastapi.testclient import TestClient


@pytest.mark.asyncio
async def test_manual_add_then_command(client: TestClient, db_session):
    response = client.post(
        "/api/devices/manual",
        json={
            "device_id": "sim-light-01",
            "manufacturer": "simulator",
            "device_type": "light",
            "name": "Test Light",
        },
    )
    assert response.status_code == 200
    assert response.json()["success"] is True

    response = client.post(
        "/api/devices/sim-light-01/command",
        json={"payload": {"power": True, "brightness": 80}},
    )
    assert response.status_code == 200

    response = client.get("/api/devices/sim-light-01")
    assert response.status_code == 200
    data = response.json()
    assert data["state"]["power"] is True
```

- [x] **Step 2: Run the full test suite**

```bash
cd hub && pytest -v
```

Expected: all tests PASS.

- [x] **Step 3: Optionally convert LIFX to local**

If you want true local-first LIFX support, replace `hub/plugins/lifx.py` with an `aiolifx`-based implementation. Because this requires LAN UDP discovery and is more involved, it can be deferred to Phase 2 if the cloud LIFX plugin is acceptable for now. The rest of Phase 1 is complete without it.

- [x] **Step 4: Commit**

```bash
git add tests/test_local_drivers.py
git commit -m "test: end-to-end manual add and command acceptance"
```

---

## Self-review checklist

1. **Spec coverage:**
   - M1 runnable dev environment → Docker Compose, env config, optional seed. ✅
   - M2 persistent state/event log → state persistence adapter, `last_state` column. ✅
   - M3 local IP drivers → existing plugins wired through `DeviceManager`, command endpoint. ✅

2. **Placeholder scan:** No TBD/TODO/fill-in-later steps. ✅

3. **Type consistency:** `DeviceManager.set_state` uses `Dict[str, Any]` payload matching routes. `StatePersistenceAdapter` imports `DeviceState` from `core.base_driver`. ✅

4. **Gaps:** LIFX local conversion is explicitly optional; if skipped, document in commit message.

---

## Execution handoff

**Plan saved to:** `docs/superpowers/plans/2026-06-15-myiot-phase1-foundation-and-local-drivers.md`

**Two execution options:**

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks.
2. **Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach do you want?
