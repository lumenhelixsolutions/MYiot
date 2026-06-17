"""
Smart Home Universal Hub — FastAPI Application Entry Point.

Initializes all core subsystems (state registry, discovery, dispatcher,
authentication manager, plugin loader) via a lifespan context manager.
Mounts REST API routes and WebSocket handlers, configures CORS, and
serves static frontend files.
"""

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
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from core.state_registry import StateRegistry
from core.dispatcher import ActuationDispatcher
from core.plugin_loader import PluginLoader
from core.manufacturer_maps import MANUFACTURER_MAPS
from auth.manager import AuthenticationManager
from discovery.listener import NetworkDiscoveryListener
from models.database import init_db
from services.state_persistence import StatePersistenceAdapter, load_devices_into_registry
from services.device_manager import DeviceManager

from api import routes as api_routes
from api import websocket as api_websocket
from api import camera_stream as camera_api

# ─── Logging Setup ────────────────────────────────────────────────────────

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ─── Discovery Callbacks ──────────────────────────────────────────────────


async def _handle_device_found(device_info: Dict[str, Any], app: FastAPI) -> None:
    """
    Callback invoked when the discovery listener finds a new device.

    Creates or updates the device state in the registry and logs
    the discovery event.
    """
    registry: StateRegistry = app.state.registry

    device_id = device_info.get("device_id") or device_info.get("usn", "unknown")
    manufacturer = device_info.get("manufacturer", "unknown")
    device_type = device_info.get("device_type", "unknown")
    model = device_info.get("model", "unknown")

    from core.base_driver import DeviceState

    device_state = DeviceState(
        device_id=device_id,
        manufacturer=manufacturer,
        model=model,
        device_type=device_type,
        online=True,
        state=device_info.get("state", {}),
        last_updated=time.time(),
    )

    await registry.update(device_id, device_state)
    logger.info(
        "Device discovered: %s (%s / %s)", device_id, manufacturer, device_type
    )


async def _seed_devices(registry: StateRegistry) -> None:
    """Seed the registry with initial demo devices."""
    from core.base_driver import DeviceState

    seed_devices = [
        {"id": "cam-1", "name": "Front Door", "mfr": "Ring", "type": "camera", "room": "Entry", "online": True, "power": True, "ip": "192.168.1.101", "signal": 92, "stream": "rtsp://192.168.1.101:554/live"},
        {"id": "cam-2", "name": "Backyard", "mfr": "Wyze", "type": "camera", "room": "Garden", "online": True, "power": True, "ip": "192.168.1.102", "signal": 78, "stream": "rtsp://192.168.1.102:554/live"},
        {"id": "cam-3", "name": "Garage", "mfr": "EOOEIES", "type": "camera", "room": "Garage", "online": True, "power": True, "ip": "192.168.1.103", "signal": 85, "stream": "rtsp://192.168.1.103:554/live"},
        {"id": "cam-4", "name": "Living Room", "mfr": "Nest", "type": "camera", "room": "Living Room", "online": True, "power": True, "ip": "192.168.1.104", "signal": 95, "stream": "rtsp://192.168.1.104:554/live"},
        {"id": "cam-5", "name": "Driveway", "mfr": "Ring", "type": "camera", "room": "Driveway", "online": False, "power": False, "ip": "192.168.1.105", "signal": 0, "stream": "rtsp://192.168.1.105:554/live"},
        {"id": "hue-1", "name": "Living Room Ceiling", "mfr": "Philips Hue", "type": "light", "room": "Living Room", "online": True, "power": True, "ip": "192.168.1.106", "signal": 92, "brightness": 85, "color": "#6366F1"},
        {"id": "hue-2", "name": "Bedside Lamp", "mfr": "Philips Hue", "type": "light", "room": "Bedroom", "online": True, "power": False, "ip": "192.168.1.107", "signal": 78, "brightness": 40, "color": "#fbbf24"},
        {"id": "kasa-1", "name": "Coffee Maker", "mfr": "TP-Link Kasa", "type": "plug", "room": "Kitchen", "online": True, "power": True, "ip": "192.168.1.108", "signal": 88},
        {"id": "kasa-2", "name": "Office Desk", "mfr": "TP-Link Kasa", "type": "plug", "room": "Office", "online": True, "power": True, "ip": "192.168.1.109", "signal": 95},
        {"id": "nest-1", "name": "Hallway Thermostat", "mfr": "Nest", "type": "thermostat", "room": "Hallway", "online": True, "power": True, "ip": "192.168.1.110", "signal": 85, "target_temp": 72, "current_temp": 70, "humidity": 45, "mode": "auto"},
        {"id": "nest-2", "name": "Upstairs", "mfr": "Nest", "type": "thermostat", "room": "Upstairs", "online": True, "power": True, "ip": "192.168.1.111", "signal": 80, "target_temp": 68, "current_temp": 69, "humidity": 42, "mode": "cool"},
        {"id": "lifx-1", "name": "Kitchen Strip", "mfr": "LIFX", "type": "light", "room": "Kitchen", "online": True, "power": True, "ip": "192.168.1.112", "signal": 86, "brightness": 70, "color": "#10b981"},
        {"id": "ikea-1", "name": "Desk Lamp", "mfr": "IKEA Tradfri", "type": "light", "room": "Office", "online": True, "power": False, "ip": "192.168.1.113", "signal": 76, "brightness": 60, "color": "#f8fafc"},
        {"id": "ecobee-1", "name": "Master Bedroom", "mfr": "Ecobee", "type": "thermostat", "room": "Master Bedroom", "online": False, "power": False, "ip": "192.168.1.114", "signal": 0, "target_temp": 70, "current_temp": 68, "humidity": 50, "mode": "off"},
        {"id": "wemo-1", "name": "Living Room Outlet", "mfr": "Wemo", "type": "plug", "room": "Living Room", "online": True, "power": False, "ip": "192.168.1.115", "signal": 82},
        {"id": "govee-1", "name": "TV Backlight", "mfr": "Govee", "type": "light", "room": "Living Room", "online": True, "power": True, "ip": "192.168.1.116", "signal": 91, "brightness": 55, "color": "#a855f7"},
        {"id": "hue-3", "name": "Porch Light", "mfr": "Philips Hue", "type": "light", "room": "Outdoor", "online": True, "power": False, "ip": "192.168.1.117", "signal": 65, "brightness": 100, "color": "#f1f5f9"},
        {"id": "kasa-3", "name": "Bedroom Charger", "mfr": "TP-Link Kasa", "type": "plug", "room": "Bedroom", "online": True, "power": False, "ip": "192.168.1.118", "signal": 79},
        {"id": "sonoff-1", "name": "Garden Lights", "mfr": "Sonoff", "type": "plug", "room": "Outdoor", "online": True, "power": True, "ip": "192.168.1.119", "signal": 58},
    ]

    for d in seed_devices:
        state = DeviceState(
            device_id=d["id"],
            manufacturer=d["mfr"],
            model="Unknown",
            device_type=d["type"],
            online=d["online"],
            state={
                "name": d["name"],
                "room": d["room"],
                "power": d["power"],
                "ip": d["ip"],
                "ip_address": d["ip"],
                "signal_strength": d["signal"],
                "stream_url": d.get("stream"),
                "brightness": d.get("brightness"),
                "color": d.get("color"),
                "target_temp": d.get("target_temp"),
                "current_temp": d.get("current_temp"),
                "humidity": d.get("humidity"),
                "mode": d.get("mode"),
            },
            last_updated=time.time(),
        )
        await registry.update(d["id"], state)


async def _handle_state_change(device_info: Dict[str, Any], app: FastAPI) -> None:
    """
    Callback invoked when the discovery listener detects a state change.

    Updates the device state in the registry.
    """
    registry: StateRegistry = app.state.registry

    device_id = device_info.get("device_id") or device_info.get("usn")
    if not device_id:
        return

    existing = await registry.get(device_id)
    if existing:
        from core.base_driver import DeviceState

        updated_state = DeviceState(
            device_id=device_id,
            manufacturer=existing.manufacturer,
            model=existing.model,
            device_type=existing.device_type,
            online=device_info.get("online", existing.online),
            state={**existing.state, **device_info.get("state", {})},
            last_updated=time.time(),
        )
        await registry.update(device_id, updated_state)
        logger.debug("State change processed for %s", device_id)


async def _seed_admin_user() -> None:
    """Create the default admin user if no users exist."""
    import secrets

    from sqlalchemy import select

    from auth.config import settings
    from auth.session import hash_password
    from models.database import User, get_async_session_factory

    factory = get_async_session_factory()
    async with factory() as session:
        result = await session.execute(select(User))
        if result.scalars().first() is not None:
            return

        password = settings.admin_password or secrets.token_urlsafe(16)
        user = User(
            username=settings.admin_username,
            password_hash=hash_password(password),
            role="admin",
            created_at=time.time(),
            updated_at=time.time(),
        )
        session.add(user)
        await session.commit()
        logger.warning(
            "Created default admin user '%s' with password: %s",
            settings.admin_username,
            password,
        )


# ─── Lifespan Context Manager ─────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan context manager.

    Handles startup initialization and graceful shutdown of all
    core subsystems.
    """
    logger.info("=" * 60)
    logger.info("Smart Home Universal Hub starting up...")
    logger.info("=" * 60)

    # Initialize database
    try:
        await init_db()
        logger.info("Database initialized")
        await _seed_admin_user()
        logger.info("Admin user seeded")
    except Exception as exc:
        logger.warning("Database initialization skipped: %s", exc)

    # Initialize state registry
    app.state.registry = StateRegistry()
    logger.info("State registry initialized")

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

    # Initialize network discovery listener
    app.state.discovery = NetworkDiscoveryListener(
        on_device_found=lambda d: asyncio.create_task(_handle_device_found(d, app)),
        on_state_change=lambda d: asyncio.create_task(
            _handle_state_change(d, app)
        ),
    )

    # Initialize actuation dispatcher
    app.state.dispatcher = ActuationDispatcher()
    logger.info("Actuation dispatcher initialized")

    # Initialize authentication manager
    app.state.auth_manager = AuthenticationManager()
    logger.info("Authentication manager initialized")

    # Initialize and run plugin discovery
    app.state.plugin_loader = PluginLoader()
    plugins = app.state.plugin_loader.discover()
    logger.info("Plugin loader initialized — %d plugin(s) discovered", len(plugins))

    # Initialize device manager
    app.state.device_manager = DeviceManager(
        registry=app.state.registry,
        plugin_loader=app.state.plugin_loader,
        auth_manager=app.state.auth_manager,
    )
    await app.state.device_manager.load_devices()
    logger.info("Device manager initialized")

    # Seed initial devices only when explicitly requested
    if os.environ.get("SEED_DEMO_DEVICES", "false").lower() == "true":
        try:
            await _seed_devices(app.state.registry)
            logger.info("Initial devices seeded")
        except Exception as exc:
            logger.warning("Device seeding failed: %s", exc)
    else:
        logger.info("Demo device seeding disabled")

    # Start discovery listeners
    try:
        await app.state.discovery.start()
        logger.info("Network discovery listener started")
    except Exception as exc:
        logger.warning("Network discovery listener failed to start: %s", exc)

    logger.info("Smart Home Universal Hub ready!")

    yield

    # ─── Shutdown ─────────────────────────────────────────────────────────

    logger.info("Shutting down Smart Home Universal Hub...")

    try:
        await app.state.discovery.stop()
        logger.info("Network discovery listener stopped")
    except Exception as exc:
        logger.warning("Error stopping discovery listener: %s", exc)

    try:
        await app.state.persistence_adapter.detach()
        logger.info("State persistence adapter detached")
    except Exception as exc:
        logger.warning("Error detaching persistence adapter: %s", exc)

    try:
        await app.state.dispatcher.close()
        logger.info("Actuation dispatcher closed")
    except Exception as exc:
        logger.warning("Error closing dispatcher: %s", exc)

    try:
        await app.state.device_manager.disconnect_all()
        logger.info("Device manager disconnected")
    except Exception as exc:
        logger.warning("Error disconnecting device manager: %s", exc)

    logger.info("Shutdown complete.")


# ─── FastAPI Application ──────────────────────────────────────────────────

app = FastAPI(
    title="Smart Home Universal Hub",
    description="Universal backend for managing smart home devices from multiple manufacturers",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include REST API routes
app.include_router(api_routes.router)

# Include WebSocket routes
app.include_router(api_websocket.router)

# Include camera streaming routes
# ─── Health Check ─────────────────────────────────────────────────────────

@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "devices_registered": len(app.state.registry) if hasattr(app.state, "registry") else 0,
    }

app.include_router(camera_api.router)

# ─── Static Files ─────────────────────────────────────────────────────────

# Serve frontend static files from 'dist/' directory if it exists
DIST_DIR = Path(__file__).parent / "dist"

if DIST_DIR.exists():
    app.mount("/assets", StaticFiles(directory=DIST_DIR / "assets"), name="assets")

    @app.get("/", response_class=HTMLResponse)
    async def serve_index():
        """Serve the frontend index.html."""
        index_path = DIST_DIR / "index.html"
        if index_path.exists():
            return FileResponse(index_path)
        return HTMLResponse("<h1>Smart Home Universal Hub</h1><p>Frontend not built yet.</p>")

    @app.get("/{path:path}")
    async def serve_spa(path: str):
        """Serve SPA routes by returning index.html."""
        # Don't catch API, WebSocket, or health routes
        if path.startswith("api/") or path == "ws" or path == "health":
            raise HTTPException(status_code=404, detail="Not found")
        index_path = DIST_DIR / "index.html"
        if index_path.exists():
            return FileResponse(index_path)
        return HTMLResponse("<h1>Smart Home Universal Hub</h1><p>Frontend not built yet.</p>")
else:
    @app.get("/", response_class=HTMLResponse)
    async def root():
        """Root endpoint when no frontend is built."""
        return """
        <html>
            <head><title>Smart Home Universal Hub</title></head>
            <body>
                <h1>Smart Home Universal Hub</h1>
                <p>API is running. Frontend not built yet.</p>
                <p>Available endpoints:</p>
                <ul>
                    <li><a href="/api/devices">GET /api/devices</a></li>
                    <li><a href="/api/manufacturers">GET /api/manufacturers</a></li>
                    <li>WS /ws</li>
                </ul>
            </body>
        </html>
        """


# ─── Main Entry Point ─────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", 8000))

    logger.info("Starting uvicorn on %s:%d", host, port)
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=os.environ.get("DEBUG", "false").lower() == "true",
    )
