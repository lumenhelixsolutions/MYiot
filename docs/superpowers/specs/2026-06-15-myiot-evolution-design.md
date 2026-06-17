# MyIoT Evolution Design — Pragmatic Self-Hosted Universal Hub

**Status:** Draft — pending final review  
**Date:** 2026-06-15  
**Target user:** Self-hosted home hub operator  
**Deployment target:** Old laptop / mini PC / NAS (x86_64, adequate CPU/RAM)  
**First-build device categories:** Smart lights & plugs, cameras & doorbells  
**Connectivity philosophy:** Local-first, with external bridges for hard radios; cloud integrations optional and isolated.

---

## 1. Executive summary

MyIoT is a self-hosted smart-home hub that unifies lights, plugs, cameras, and (later) sensors under a single React dashboard. It is designed to run locally on hardware the user already owns, keep data on the LAN by default, and avoid the maintenance burden of hand-rolling every radio protocol and cloud API.

The evolution strategy is **pragmatic universal hub + external bridges**:

- **Own the experience:** state registry, REST/WebSocket API, automation engine, user auth, and UI.
- **Borrow the hard parts:** Zigbee/Thread via **Zigbee2MQTT**, camera normalization via **go2rtc**.
- **Curate direct drivers:** only stable local-IP devices (Hue Bridge, Kasa, Wemo, Sonoff LAN, LIFX).
- **Defer cloud lock-in:** Nest/Ring/Govee/Wyze and cloud-only cameras are treated as optional plugins in a later milestone, not core dependencies.

This design directly addresses the main risk in the existing codebase: an overly ambitious list of 19 bespoke manufacturer integrations, many of them cloud/OAuth-based, that would consume the entire roadmap before the product felt usable.

---

## 2. Guiding principles

1. **Local-first by default.** Commands and automations must work without internet.
2. **Incremental deliverability.** Each milestone produces a working, testable system.
3. **Don’t rebuild bridges that already exist.** Use Zigbee2MQTT and go2rtc as external services, not as competitors.
4. **One device model to rule them all.** Every physical device maps to a normalized `DeviceState` regardless of protocol.
5. **Security is not a later feature.** Auth, encryption, and network segmentation are built before the system is exposed to a household.
6. **Hardware honesty.** Off-market cameras are supported generically via ONVIF/RTSP/MJPEG; cloud-only devices require an explicit optional bridge.

---

## 3. Revised architecture

```text
┌─────────────────────────────────────────────┐
│            React + Vite SPA                 │
│  Dashboard │ Device Grid │ Cameras │ Rooms   │
│  Automations │ Settings │ Activity Log      │
└──────────────┬──────────────────────────────┘
               │ REST + WebSocket
┌──────────────▼──────────────────────────────┐
│           MyIoT Core (FastAPI)              │
│  ┌─────────────┐  ┌─────────────────────┐   │
│  │ State       │  │ Automation Engine   │   │
│  │ Registry    │  │ (rules/scenes/scheduler) │
│  └──────┬──────┘  └─────────────────────┘   │
│  ┌─────────────┐  ┌─────────────────────┐   │
│  │ Auth &      │  │ Event Log / History │   │
│  │ Credential  │  │                     │   │
│  │ Manager     │  │                     │   │
│  └─────────────┘  └─────────────────────┘   │
└──────┬───────────────────────┬──────────────┘
       │                       │
  direct drivers          bridge adapters
  (IP-based)              (external services)
  - Philips Hue Bridge    - Zigbee2MQTT (MQTT)
  - TP-Link Kasa          - go2rtc (cameras)
  - Wemo
  - Sonoff LAN
  - LIFX
  - Generic ONVIF/RTSP
  - EOOEIES / off-market
    template driver
```

### 3.1 Core responsibilities

| Component | Responsibility |
|-----------|----------------|
| **FastAPI app layer** | REST endpoints, WebSocket broadcaster, lifecycle management, CORS/HTTPS. |
| **State Registry** | Single source of truth for current device state. Persists snapshots to SQLite. |
| **Plugin/Adapter layer** | Translates manufacturer/protocol specifics into normalized `DeviceState` and commands. |
| **Auth & Credential Manager** | User sessions, encrypted manufacturer credentials, API tokens. |
| **Automation Engine** | Rule evaluation, scene execution, scheduled jobs. |
| **Event Log** | Append-only record of discovery, state changes, commands, errors. |

### 3.2 External services (containers)

| Service | Role | Why it is used |
|---------|------|----------------|
| **Zigbee2MQTT** | Zigbee/Thread radio coordinator | Mature, exposes everything via MQTT, huge device compatibility. |
| **Eclipse Mosquitto** | MQTT broker | Standard broker for Zigbee2MQTT and any other MQTT devices. |
| **go2rtc** | Camera stream gateway | Ingests RTSP/ONVIF and serves WebRTC/MJPEG to browsers with minimal latency. |

---

## 4. Device & protocol strategy

### 4.1 Direct drivers (Milestone 3)

Built as Python plugins behind the existing `BaseDriver` interface. Each wraps a well-maintained library to avoid protocol archaeology.

| Manufacturer | Library / protocol | Notes |
|--------------|-------------------|-------|
| Philips Hue Bridge | `phue` or direct local REST | Local API requires bridge button press for token. |
| TP-Link Kasa | `python-kasa` | Modern local protocol; discovery built-in. |
| Wemo | `pywemo` | SSDP discovery. |
| Sonoff LAN mode | `python-kasa` (LAN) or custom REST | Avoids eWeLink cloud where possible. |
| LIFX | `aiolifx` or `python-lifx` | LAN UDP protocol. |

### 4.2 Bridge adapters

| Bridge | Adapter behavior |
|--------|------------------|
| **Zigbee2MQTT** | Subscribes to `zigbee2mqtt/+/availability`, `zigbee2mqtt/+/state`; publishes commands to `zigbee2mqtt/<friendly_name>/set`. |
| **go2rtc** | Core pushes RTSP/ONVIF URLs to go2rc; frontend requests WebRTC/MJPEG via MyIoT proxy endpoints. |

### 4.3 Generic camera driver (Milestone 5)

Handles the long tail of off-market cameras including EOOEIES.

Discovery/connection order:

1. **ONVIF auto-discovery** using `onvif-zeep` or `WSDiscovery` to fetch profiles, RTSP URL, and snapshot URL.
2. **Manual RTSP / HTTP-MJPEG template** for cameras with known URL patterns.
3. **Snapshot JPEG polling** for cameras that expose only a still-image endpoint.
4. **Cloud-only fallback** deferred to Milestone 9 (Tuya/EOOEIES cloud bridge if local access is impossible).

Preset templates to ship:

| Preset | Typical stream URL | Snapshot URL |
|--------|--------------------|--------------|
| Generic ONVIF | discovered | discovered |
| Reolink | `rtsp://admin:pass@IP:554/h264Preview_01_main` | `/cgi-bin/api.cgi?cmd=Snap&channel=0` |
| Tapo | `rtsp://user:pass@IP:554/stream1` | `/onvif/snapshot` |
| Hiseeu | `rtsp://user:pass@IP:554/user=admin_password=..._channel=1_stream=0.sdp` | `/snapshot.jpg` |
| EOOEIES | `rtsp://user:pass@IP:554/...` or HTTP-MJPEG | `/snapshot` (validate against firmware) |

---

## 5. Security model

| Layer | Requirement |
|-------|-------------|
| **Transport** | TLS 1.3 for all browser/API traffic. Self-signed cert by default; user can supply their own. |
| **User auth** | Local username/password + optional FIDO2/passkey. Short-lived JWT sessions. |
| **Credential storage** | Manufacturer credentials encrypted at rest with a key derived from the user password plus a server-side key file. |
| **API** | Rate limiting, strict input validation, CORS locked to the hub origin. |
| **Network** | Documented guide to place cameras and IoT radios on a dedicated VLAN with no internet egress unless required by a cloud plugin. |
| **Camera streams** | Never expose RTSP credentials to the frontend; go through the backend/go2rtc proxy. |

---

## 6. 10 logical milestones

| # | Milestone | Goal | Key deliverables | Success criteria |
|---|-----------|------|-------------------|------------------|
| **M1** | Foundation & runnable dev environment | The project builds and runs consistently. | Docker Compose stack (FastAPI + Vite), `.env` config, `pytest` harness, `ruff`/`mypy`, structured logging. | `docker compose up` serves API on `:8000` and UI on `:5173`; tests pass. |
| **M2** | Persistent state, config, and event log | Data survives restarts and is auditable. | Async SQLite/SQLAlchemy models: `Device`, `EventLog`, `User`; REST CRUD; event log endpoints. | Restarting the hub restores device list and state; events are queryable. |
| **M3** | Local IP drivers for lights & plugs | First user-facing device category works. | Plugins for Hue Bridge, Kasa, Wemo, Sonoff LAN, LIFX; SSDP/mDNS discovery; standardized payloads. | Lights/plugs auto-discover and respond to power/brightness/color commands. |
| **M4** | Zigbee/Thread bridge via Zigbee2MQTT | Add low-cost mesh devices without writing a Zigbee stack. | Mosquitto + Zigbee2MQTT containers; MQTT adapter; pairing flow in UI. | Zigbee lights/plugs/sensors appear and are controllable through the hub. |
| **M5** | Camera streaming + off-market/EOOEIES support | Cameras and doorbells viewable in the dashboard. | go2rtc container; ONVIF discovery; generic RTSP/MJPEG/snapshot driver; presets for EOOEIES, Hiseeu, Reolink, Tapo; WebRTC/MJPEG endpoints. | Live camera feed displays in the dashboard with sub-second latency for local-stream cameras. |
| **M6** | Real-time frontend dashboard | The product feels like a unified dashboard. | Typed API client, reconnecting WebSocket, device grid, room filters, camera panel, control widgets, dark/light theme. | Two browser tabs see state changes instantly; UI controls work without reload. |
| **M7** | User auth, security, and network hardening | The hub is safe to expose to a household. | Local auth + optional passkey, encrypted credential manager v2, HTTPS by default, rate limiting, CORS tightening, VLAN guide. | Login required for UI/API; credentials encrypted at rest; API served over HTTPS. |
| **M8** | Automations, scenes, and scheduler | Users get value beyond a remote-control app. | Rule engine (trigger/condition/action), scene presets, cron-like scheduler, rule editor UI. | User can create and run automations such as "if motion after sunset, turn on hallway light." |
| **M9** | Optional cloud bridges & energy monitoring | Support devices that have no local API. | OAuth plugin framework, token refresh, rate-limit handling, optional Tuya/EOOEIES cloud bridge, energy charts for smart plugs. | Cloud devices coexist with local devices; energy monitoring dashboards visible. |
| **M10** | Packaging, updates, and ecosystem | Non-technical users can install and maintain the hub. | Install/update script, backup/restore, PWA manifest, plugin manifest/schema, docs, sample driver template. | A user can install MyIoT on a mini PC, add a device, back up config, and apply an update. |

### 6.1 Milestone sequencing rationale

- **M1–M2** make the codebase production-shaped before feature work piles up.
- **M3–M5** deliver the two categories the user prioritized: lights/plugs and cameras.
- **M6** makes the product usable as a dashboard.
- **M7** is the trust gate; it must precede any real household deployment.
- **M8** is the reason users choose a hub over vendor apps.
- **M9–M10** broaden compatibility and reduce long-term maintenance burden.

---

## 7. Camera hardware compatibility guidance

### Recommended (known local streams)

| Use case | Recommended models | Protocol |
|----------|--------------------|----------|
| Budget doorbell | Reolink Video Doorbell WiFi/PoE, TP-Link Tapo D130, Amcrest AD110 | ONVIF + RTSP |
| Outdoor camera | Reolink Argus/Tapo C520WS/Hiseeu wireless kits | ONVIF + RTSP |
| NVR kit | Hiseeu, Annke, Hilook, Lorex PoE/wireless NVR kits | ONVIF + RTSP |

### Buyer beware

| Category | Risk |
|----------|------|
| Ring / Blink / Nest / Arlo | Cloud-only; no local stream without reverse-engineering. |
| Generic Temu/Amazon Tuya doorbells | Usually cloud-locked; may only expose port 6668. |
| EOOEIES-branded cameras | App is cloud-centric; local ONVIF/RTSP support varies by OEM batch. |

### Validating an EOOEIES or unknown camera

1. `nmap -p 80,443,554,8000-9000,10554 <camera-ip>`
2. Try ONVIF Device Manager or `onvif-zeep` discovery.
3. Test common RTSP paths (`/stream1`, `/onvif1`, `/live`).
4. If only cloud ports are open, route through the M9 cloud bridge.

---

## 8. Deployment target

- **Primary:** x86_64 mini PC, old laptop, or NAS with Docker.
- **Secondary:** Raspberry Pi 4/5 or equivalent ARM SBC (may require performance tuning for multiple camera streams).
- **Radios:** Zigbee/Thread via USB coordinator (e.g., Sonoff ZBDongle-E, SkyConnect) passed into the Zigbee2MQTT container.

---

## 9. Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Maintaining 19+ manufacturer integrations | Reduce direct drivers to a curated local set; defer cloud brands to optional plugins. |
| Off-market cameras have no local API | Generic ONVIF/RTSP/MJPEG driver + cloud-bridge fallback. |
| Zigbee/Thread complexity | Delegate to Zigbee2MQTT instead of writing a stack. |
| Camera streaming performance | Use go2rtc; recommend sub-streams and hardware with QuickSync/NVENC if transcoding is needed. |
| Security of cheap IoT cameras | Document VLAN isolation and egress blocking; never forward camera ports publicly. |

---

## 10. Open questions

1. **M9 cloud plugins:** Should these be included in the initial spec or moved to a post-M10 expansion pack to keep the core local-only?
2. **Matter/Thread native commissioning:** Is native Matter controller support a future milestone, or is Zigbee2MQTT + Thread border router sufficient?
3. **Voice assistants:** Any interest in Alexa/Google/HomeKit bridge integration later, or is PWA-only the target?

---

## 11. Approval

This spec is ready for final review. Once approved, the next step is to create a detailed implementation plan using the `writing-plans` skill.
