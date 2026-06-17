# MyIoT M6 — Real-Time Frontend Dashboard

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Make the React dashboard live by consuming the backend WebSocket stream, fetching real device state, sending commands through the REST API, and wiring control widgets to the real hub. Also implement a dark/light theme toggle.

**Architecture:** Backend already publishes `state_change` messages and accepts WebSocket commands, but the command path still uses the legacy dispatcher. We’ll route WebSocket commands through `DeviceManager`, add a frontend mapper from backend `DeviceState` to frontend `Device`, and wire `useBackendSync` to fetch the device list and dispatch incoming state changes into `AppContext`. Control widgets will call `api.sendCommand` and let the WebSocket update confirm state. A theme provider will persist the user’s choice in `localStorage`.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy, pytest, React 18, Vite, Tailwind CSS, WebSocket.

---

## Existing files you will modify

| File | Why |
|------|-----|
| `hub/api/websocket.py` | Route WebSocket commands through `DeviceManager` instead of legacy `ActuationDispatcher`. |
| `app/src/api/mappers.ts` *(new)* | Map backend `DeviceState` to frontend `Device`. |
| `app/src/store/AppContext.tsx` | Add `SYNC_DEVICES` / `UPDATE_DEVICE_FROM_BACKEND` actions; send commands to backend. |
| `app/src/store/useBackendSync.ts` | Fetch device list on connect; subscribe to WS messages; dispatch mapped updates. |
| `app/src/index.css` | Add light-theme CSS variables and a `.light` class scope. |
| `app/src/App.tsx` | Read persisted theme on mount and apply `light`/`dark` class. |
| `app/src/pages/Settings.tsx` | Make the theme selector actually apply the theme and persist it. |
| `app/src/pages/Dashboard.tsx` | Ensure stats and activity reflect live state (already mostly wired after AppContext changes). |
| `app/src/pages/Devices.tsx` | Ensure grid reflects live state and commands reach backend. |
| `app/src/pages/DeviceDetail.tsx` | Ensure sliders/color/mode controls call backend commands. |

## New files you will create

| File | Responsibility |
|------|----------------|
| `app/src/api/mappers.ts` | Convert backend `DeviceState` into the frontend `Device` type. |
| `hub/tests/test_websocket.py` | Backend test proving WebSocket commands go through `DeviceManager`. |
| `app/src/components/ThemeProvider.tsx` *(optional)* | Apply/persist theme class; can be inlined in `App.tsx`. |

---

## Task 1: Route WebSocket commands through DeviceManager

**Files:**
- Modify: `hub/api/websocket.py`
- Test: `hub/tests/test_websocket.py`

- [x] **Step 1: Replace dispatcher command handling with DeviceManager**

Modify `hub/api/websocket.py`:

1. Remove the `dispatcher` variable and the import of `ActuationDispatcher` if it is only used here.
2. In `websocket_endpoint`, change:

```python
    registry = websocket.app.state.registry
    dispatcher = websocket.app.state.dispatcher
```

to:

```python
    registry = websocket.app.state.registry
    device_manager = websocket.app.state.device_manager
```

3. Update the call to `_handle_client_message(message, client, registry, dispatcher)` to pass `device_manager`.

4. Replace `_handle_command_message` with:

```python
async def _handle_command_message(
    message: Dict[str, Any],
    client: WebSocketClient,
    registry: Any,
    device_manager: Any,
) -> None:
    """Handle a command message from the client via the DeviceManager."""
    device_id = message.get("device_id")
    payload = message.get("payload", {})

    if not device_id:
        await client.send({"type": "error", "message": "Missing device_id in command"})
        return

    device = await registry.get(device_id)
    if not device:
        await client.send({
            "type": "error",
            "message": f"Device not found: {device_id}",
        })
        return

    try:
        success = await device_manager.set_state(device_id, payload)
        await client.send({
            "type": "command_result",
            "device_id": device_id,
            "success": success,
        })
    except Exception as exc:
        logger.warning("WebSocket command failed for %s: %s", device_id, exc)
        await client.send({
            "type": "command_result",
            "device_id": device_id,
            "success": False,
            "error": str(exc),
        })
```

5. Update `_handle_client_message` signature and call:

```python
async def _handle_client_message(
    message: Dict[str, Any],
    client: WebSocketClient,
    registry: Any,
    device_manager: Any,
) -> None:
    action = message.get("action")

    if action == "command":
        await _handle_command_message(message, client, registry, device_manager)
    elif action == "subscribe":
        await _handle_subscribe_message(message, client, registry)
    elif action == "ping":
        await client.send({"type": "pong", "timestamp": asyncio.get_event_loop().time()})
    else:
        await client.send({"type": "error", "message": f"Unknown action: {action}"})
```

- [x] **Step 2: Write a backend WebSocket command test**

Create `hub/tests/test_websocket.py`:

```python
import pytest
from fastapi.testclient import TestClient

from core.plugin_loader import PluginLoader
from core.state_registry import StateRegistry
from main import app
from models.database import DeviceConfig, get_async_session_factory
from services.device_manager import DeviceManager


@pytest.mark.asyncio
async def test_websocket_command_via_device_manager(db_session):
    registry = StateRegistry()
    loader = PluginLoader()
    loader.discover()
    manager = DeviceManager(registry, loader)

    # Seed a simulator device
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

    await manager.load_devices()

    # Patch the running app instances for the WebSocket handler
    app.state.registry = registry
    app.state.device_manager = manager

    with TestClient(app) as client:
        with client.websocket_connect("/ws") as ws:
            ws.send_json({
                "action": "command",
                "device_id": "sim-plug-01",
                "payload": {"power": False},
            })
            result = ws.receive_json()
            assert result["type"] == "command_result"
            assert result["device_id"] == "sim-plug-01"
            assert result["success"] is True

            # State change broadcast should follow
            msg = ws.receive_json(timeout=2.0)
            assert msg["type"] == "state_change"
            assert msg["device_id"] == "sim-plug-01"
            assert msg["state"]["state"]["power"] is False
```

- [x] **Step 3: Run the test**

```bash
cd hub && pytest tests/test_websocket.py -v
```

Expected: PASS.

- [x] **Step 4: Run all backend tests**

```bash
cd hub && pytest -v
```

Expected: all existing tests still pass.

---

## Task 2: Add frontend state mapper

**Files:**
- Create: `app/src/api/mappers.ts`

- [x] **Step 1: Create the mapper**

Create `app/src/api/mappers.ts`:

```typescript
import type { Device, DeviceType, ThermoMode } from '@/types';

export interface BackendDeviceState {
  device_id: string;
  manufacturer: string;
  model: string;
  device_type: DeviceType;
  online: boolean;
  state: Record<string, unknown>;
  last_updated: number;
}

export function mapDeviceState(state: BackendDeviceState): Device {
  const s = state.state || {};
  return {
    id: state.device_id,
    name: (s.name as string) || state.device_id,
    manufacturer: state.manufacturer,
    model: state.model,
    type: state.device_type,
    room: (s.room as string) || 'Unknown',
    online: state.online,
    power: s.power === undefined ? true : Boolean(s.power),
    brightness: s.brightness as number | undefined,
    color: (s.color as string) || undefined,
    colorTemp: s.color_temp as number | undefined,
    targetTemp: s.target_temp as number | undefined,
    currentTemp: s.current_temp as number | undefined,
    humidity: s.humidity as number | undefined,
    mode: (s.mode as ThermoMode) || undefined,
    streamUrl: (s.stream_url as string) || undefined,
    ipAddress: (s.ip_address as string) || (s.ip as string) || '',
    protocol: String(s.protocol || 'REST').toUpperCase(),
    signalStrength: (s.signal_strength as number) || 0,
    lastSeen: state.last_updated * 1000 || Date.now(),
    firmware: (s.firmware as string) || 'unknown',
  };
}

export function mapDeviceStates(states: BackendDeviceState[]): Device[] {
  return states.map(mapDeviceState);
}
```

- [x] **Step 2: Verify imports**

```bash
cd app && npx tsc --noEmit
```

If `node_modules` is missing, skip and verify syntax visually.

---

## Task 3: Wire live state into AppContext

**Files:**
- Modify: `app/src/store/AppContext.tsx`
- Modify: `app/src/store/useBackendSync.ts`

- [x] **Step 1: Add backend-sync actions to AppContext**

In `app/src/store/AppContext.tsx`, extend the `Action` type:

```typescript
type Action =
  | { type: 'TOGGLE_DEVICE_POWER'; deviceId: string }
  | { type: 'UPDATE_DEVICE'; deviceId: string; updates: Partial<Device> }
  | { type: 'SYNC_DEVICES'; devices: Device[] }
  | { type: 'UPDATE_DEVICE_FROM_BACKEND'; deviceId: string; updates: Partial<Device> }
  | ... // keep the rest unchanged
```

Add two reducer cases after `UPDATE_DEVICE`:

```typescript
    case 'SYNC_DEVICES':
      return {
        ...state,
        devices: action.devices,
      };
    case 'UPDATE_DEVICE_FROM_BACKEND': {
      const exists = state.devices.find(x => x.id === action.deviceId);
      if (!exists) {
        // A new device appeared; materialize a minimal Device from the update.
        const merged: Device = {
          id: action.deviceId,
          name: (action.updates.name as string) || action.deviceId,
          manufacturer: (action.updates.manufacturer as string) || 'unknown',
          model: (action.updates.model as string) || 'unknown',
          type: (action.updates.type as DeviceType) || 'plug',
          room: (action.updates.room as string) || 'Unknown',
          online: action.updates.online ?? true,
          power: action.updates.power ?? true,
          ipAddress: (action.updates.ipAddress as string) || '',
          protocol: (action.updates.protocol as string) || 'REST',
          signalStrength: (action.updates.signalStrength as number) || 0,
          lastSeen: action.updates.lastSeen || Date.now(),
          firmware: (action.updates.firmware as string) || 'unknown',
          ...action.updates,
        };
        return { ...state, devices: [...state.devices, merged] };
      }
      return {
        ...state,
        devices: state.devices.map(x =>
          x.id === action.deviceId ? { ...x, ...action.updates, lastSeen: Date.now() } : x
        ),
      };
    }
```

- [x] **Step 2: Make control actions call the backend**

Change `togglePower` and `updateDevice` callbacks in `AppProvider`:

```typescript
  const togglePower = useCallback(async (id: string) => {
    const d = state.devices.find(x => x.id === id);
    if (!d) return;
    const newPower = !d.power;
    dispatch({ type: 'TOGGLE_DEVICE_POWER', deviceId: id });
    try {
      await api.sendCommand(id, { power: newPower });
    } catch (err) {
      // Optionally revert or log; for now the WebSocket will reconcile.
    }
  }, [state.devices]);

  const updateDevice = useCallback(async (id: string, u: Partial<Device>) => {
    dispatch({ type: 'UPDATE_DEVICE', deviceId: id, updates: u });
    // Map Device fields back to backend payload field names where necessary.
    const payload: Record<string, unknown> = {};
    if (u.brightness !== undefined) payload.brightness = u.brightness;
    if (u.color !== undefined) payload.color = u.color;
    if (u.targetTemp !== undefined) payload.target_temp = u.targetTemp;
    if (u.mode !== undefined) payload.mode = u.mode;
    if (u.power !== undefined) payload.power = u.power;
    if (Object.keys(payload).length === 0) return;
    try {
      await api.sendCommand(id, payload);
    } catch (err) {
      // Reconciliation via WebSocket.
    }
  }, []);
```

Import `api` at the top of `AppContext.tsx`:

```typescript
import { api } from '@/api/client';
```

- [x] **Step 3: Pass dispatch into useBackendSync**

Modify `app/src/store/useBackendSync.ts`:

```typescript
import { useEffect, useRef, useState, useCallback } from 'react';
import { api } from '@/api/client';
import { wsClient } from '@/api/websocket';
import type { WsStatus } from '@/api/websocket';
import { mapDeviceState, mapDeviceStates } from '@/api/mappers';
import type { Device } from '@/types';
import type { Action } from './AppContext';

export function useBackendSync(dispatch: React.Dispatch<Action>) {
```

Inside the mount `useEffect`, after `wsClient.connect()`, add:

```typescript
        // Fetch full device list and keep it in sync
        const listRes = await api.listDevices();
        if (listRes.ok && listRes.data) {
          dispatch({ type: 'SYNC_DEVICES', devices: mapDeviceStates(listRes.data as any[]) });
        }

        // Subscribe to incoming state changes
        const unsubMessage = wsClient.onMessage((msg) => {
          if (msg.type === 'state_change' && msg.state) {
            const device = mapDeviceState(msg.state as any);
            dispatch({
              type: 'UPDATE_DEVICE_FROM_BACKEND',
              deviceId: device.id,
              updates: device,
            });
          }
        });
```

Return cleanup in the effect:

```typescript
    return () => {
      mounted = false;
      unsub();
      unsubMessage?.();
    };
```

Also update the `refresh` callback to dispatch after fetching:

```typescript
  const refresh = useCallback(async () => {
    setState(s => ({ ...s, syncing: true }));
    const res = await api.health();
    if (res.ok) {
      setState(s => ({
        ...s,
        connected: true,
        deviceCount: res.data?.devices_registered || 0,
        syncing: false,
        error: null,
      }));
      wsClient.connect();
      const listRes = await api.listDevices();
      if (listRes.ok && listRes.data) {
        dispatch({ type: 'SYNC_DEVICES', devices: mapDeviceStates(listRes.data as any[]) });
      }
    } else {
      setState(s => ({
        ...s,
        connected: false,
        syncing: false,
        error: res.error || 'Backend unavailable',
      }));
    }
  }, [dispatch]);
```

- [x] **Step 4: Update AppProvider call**

In `AppContext.tsx`, change:

```typescript
  const backendSync = useBackendSync();
```

to:

```typescript
  const backendSync = useBackendSync(dispatch);
```

- [x] **Step 5: Verify frontend type-check**

```bash
cd app && npx tsc --noEmit
```

Expected: no new type errors. (If `node_modules` is missing, note it.)

---

## Task 4: Implement dark/light theme toggle

**Files:**
- Modify: `app/src/index.css`
- Modify: `app/src/App.tsx`
- Modify: `app/src/pages/Settings.tsx`

- [x] **Step 1: Add light-theme CSS variables**

In `app/src/index.css`, wrap the existing `:root` block in a `html` selector and add a `.light` block:

```css
@layer base {
  :root {
    color-scheme: dark;
  }

  html {
    --bg-base: #07070d;
    --bg-surface: #0f0f17;
    --bg-elevated: #181822;
    --bg-inset: #0a0a12;
    --accent-primary: #6366f1;
    --accent-primary-light: #818cf8;
    --accent-secondary: #06b6d4;
    --accent-tertiary: #8b5cf6;
    --status-on: #10b981;
    --status-off: #374151;
    --status-warn: #f59e0b;
    --status-error: #ef4444;
    --text-primary: #f1f5f9;
    --text-secondary: #94a3b8;
    --text-muted: #475569;
    --border-subtle: rgba(255,255,255,0.04);
    --border-hover: rgba(255,255,255,0.08);
    --glass-bg: rgba(15,15,23,0.9);
    --glass-border: rgba(255,255,255,0.05);
  }

  html.light {
    color-scheme: light;
    --bg-base: #f8fafc;
    --bg-surface: #ffffff;
    --bg-elevated: #f1f5f9;
    --bg-inset: #e2e8f0;
    --accent-primary: #4f46e5;
    --accent-primary-light: #6366f1;
    --accent-secondary: #0891b2;
    --accent-tertiary: #7c3aed;
    --status-on: #059669;
    --status-off: #cbd5e1;
    --status-warn: #d97706;
    --status-error: #dc2626;
    --text-primary: #0f172a;
    --text-secondary: #475569;
    --text-muted: #94a3b8;
    --border-subtle: rgba(0,0,0,0.06);
    --border-hover: rgba(0,0,0,0.12);
    --glass-bg: rgba(255,255,255,0.9);
    --glass-border: rgba(0,0,0,0.05);
  }
  ...
}
```

Keep the rest of the file unchanged.

- [x] **Step 2: Apply persisted theme on app mount**

Modify `app/src/App.tsx` to read `localStorage` and apply the class:

```tsx
import { useEffect } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AppProvider } from '@/store/AppContext';
import Layout from '@/components/Layout';
import Dashboard from '@/pages/Dashboard';
import Devices from '@/pages/Devices';
import DeviceDetail from '@/pages/DeviceDetail';
import CameraMonitor from '@/pages/CameraMonitor';
import Discovery from '@/pages/Discovery';
import Activity from '@/pages/Activity';
import Settings from '@/pages/Settings';

function applyTheme(theme: 'dark' | 'light') {
  const root = document.documentElement;
  if (theme === 'light') root.classList.add('light');
  else root.classList.remove('light');
}

export default function App() {
  useEffect(() => {
    const saved = localStorage.getItem('myiot-theme') as 'dark' | 'light' | null;
    const theme = saved || 'dark';
    applyTheme(theme);
  }, []);

  return (
    <AppProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route index element={<Dashboard />} />
            <Route path="devices" element={<Devices />} />
            <Route path="devices/:id" element={<DeviceDetail />} />
            <Route path="cameras" element={<CameraMonitor />} />
            <Route path="discovery" element={<Discovery />} />
            <Route path="activity" element={<Activity />} />
            <Route path="settings" element={<Settings />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AppProvider>
  );
}
```

- [x] **Step 3: Make Settings theme selector persist**

In `app/src/pages/Settings.tsx`, update `GeneralTab`:

```tsx
function GeneralTab() {
  const [theme, setTheme] = useState<'dark' | 'light'>(() => {
    return (localStorage.getItem('myiot-theme') as 'dark' | 'light') || 'dark';
  });
  ...
  const applyAndSave = (t: 'dark' | 'light') => {
    setTheme(t);
    localStorage.setItem('myiot-theme', t);
    if (t === 'light') document.documentElement.classList.add('light');
    else document.documentElement.classList.remove('light');
  };
  ...
  <Row label="Theme">
    <div className="flex gap-2">
      {(['dark', 'light'] as const).map(t => (
        <button
          key={t}
          onClick={() => applyAndSave(t)}
          className="rounded-lg px-3 py-1.5 text-xs font-medium capitalize transition-all"
          style={{ backgroundColor: theme === t ? 'var(--accent-primary)' : 'var(--bg-elevated)', color: theme === t ? '#fff' : 'var(--text-muted)' }}
        >{t}</button>
      ))}
    </div>
  </Row>
```

- [x] **Step 4: Verify theme switch**

Run the frontend dev server:

```bash
cd app && npm run dev
```

Open `http://localhost:5173/settings`, click **Light**, and confirm the page background changes to a light color.

---

## Task 5: Ensure control widgets send commands

**Files:**
- Modify: `app/src/pages/DeviceDetail.tsx`
- Modify: `app/src/pages/Devices.tsx`

- [x] **Step 1: Update DeviceDetail controls**

`DeviceDetail.tsx` already uses `updateDevice` and `togglePower` from context. Because those callbacks now call the backend, no code change is required here. Verify that the light scene buttons, brightness slider, color picker, thermostat mode/target, and camera privacy toggle still work.

- [x] **Step 2: Update Devices power toggle**

`Devices.tsx` uses `togglePower(device.id)`. No change required, but confirm the toggle switch still updates after the backend command.

---

## Task 6: Manual end-to-end verification

**Files:** none

- [x] **Step 1: Start the backend**

```bash
cd hub && uvicorn main:app --reload
```

- [x] **Step 2: Add a simulator device**

```bash
curl -X POST http://localhost:8000/api/devices/manual \
  -H "Content-Type: application/json" \
  -d '{"device_id": "dashboard-test-1", "manufacturer": "simulator", "model": "sim", "device_type": "plug", "name": "Dashboard Test Plug"}'
```

- [x] **Step 3: Start the frontend**

```bash
cd app && npm run dev
```

- [x] **Step 4: Verify live sync**

1. Open `http://localhost:5173/devices`.
2. Confirm the new simulator plug appears.
3. Toggle its power from the UI.
4. Confirm the switch reflects the new state within ~1 second.
5. Open a second browser tab to the same page.
6. Toggle power in one tab; the other tab should update automatically via WebSocket.

- [x] **Step 5: Verify theme toggle**

In `Settings > General`, switch between Dark and Light; the entire UI should switch palettes.

---

## Task 7: Tests and final verification

**Files:**
- Run: `hub/tests/`

- [x] **Step 1: Run backend tests**

```bash
cd hub && pytest -v
```

Expected: all tests pass (including the new WebSocket test).

- [x] **Step 2: Run frontend type-check**

```bash
cd app && npx tsc --noEmit
```

Expected: no new type errors.

- [x] **Step 3: Ruff check on changed Python files**

```bash
cd hub && ruff check api/websocket.py tests/test_websocket.py
```

Expected: no new lint errors.

---

## Self-review checklist

1. **Spec coverage:**
   - Reconnecting WebSocket consumed by UI → Tasks 1, 3 ✅
   - Device grid reflects real state → Tasks 2, 3 ✅
   - Control widgets send real commands → Task 3 ✅
   - Dark/light theme → Task 4 ✅
   - Two tabs see state changes instantly → Task 6 ✅

2. **Placeholder scan:** No TBD/TODO/fill-in-later steps. ✅

3. **Type consistency:** Mapper uses backend field names (`state.*`) and produces frontend `Device`. `useBackendSync` dispatches `SYNC_DEVICES` and `UPDATE_DEVICE_FROM_BACKEND`. ✅

---

## Execution handoff

**Plan saved to:** `docs/superpowers/plans/2026-06-15-m6-realtime-dashboard.md`

**Two execution options:**

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks.
2. **Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach do you want?
