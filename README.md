# MYiot

<p align="center">
  <a href="https://lumenhelix.com">
    <img src="docs/assets/lumenhelix-logo.svg" alt="LumenHelix Solutions" width="180">
  </a>
</p>

<h3 align="center">Privacy-first universal smart home hub with a glassmorphism UI</h3>

<p align="center">
  <a href="https://lumenhelixsolutions.github.io/MYiot/">
    <img src="https://img.shields.io/badge/Launch_Page-MYiot-00D4FF?style=flat-square&logo=githubpages&logoColor=white" alt="Launch Page">
  </a>
  <a href="https://lumenhelix.com">
    <img src="https://img.shields.io/badge/Built_by-LumenHelix-7C3AED?style=flat-square" alt="Built by LumenHelix">
  </a>
  <img src="https://img.shields.io/badge/license-CC-BY-NC-4.0-8A95A8?style=flat-square" alt="License">
</p>

---

**MYiot** is part of the [LumenHelix Solutions](https://lumenhelix.com) portfolio — applied symbolic dynamics & reversible computation for deterministic, traceable AI systems.

MYiot is the LumenHelix privacy-first universal smart home hub. It unifies 17+ smart device brands behind a React 19 + Vite glassmorphism dashboard, backed by a FastAPI hub with WebSocket real-time sync, local SQLite/Redis storage, and Frigate-powered camera AI — all without cloud dependency.

## Why this exists

- **Stay private.** Local-first processing and end-to-end encryption keep your home data in your home.
- **Unify everything.** One dashboard for Zigbee, Z-Wave, WiFi, Bluetooth, MQTT, HomeKit, Thread, and 17+ brands.
- **Ship with confidence.** Dockerized stack, FastAPI backend, and reversible commit history make iteration predictable.

## Quick start

Install and run MYiot in under two minutes.

### macOS / Linux

```bash
# Clone
git clone https://github.com/lumenhelixsolutions/MYiot.git
cd MYiot

# Install & run
cp hub/.env.example hub/.env
docker compose up -d
```

### Windows (PowerShell)

```powershell
# Clone
git clone https://github.com/lumenhelixsolutions/MYiot.git
Set-Location MYiot

# Install & run
Copy-Item hub\.env.example hub\.env
docker compose up -d
```

### Windows (Git Bash / WSL)

```bash
git clone https://github.com/lumenhelixsolutions/MYiot.git
cd MYiot
cp hub/.env.example hub/.env
docker compose up -d
```

> **Device note:** MYiot is tested on Windows 11, macOS Sonoma, Ubuntu 22.04/24.04, and modern mobile browsers.

## Full documentation

Visit the launch page for architecture, API reference, and deployment guides:  
**https://lumenhelixsolutions.github.io/MYiot/**

## Features

| Feature | What it gives you |
|---------|-------------------|
| Universal device hub | Connect 17+ brands — Hue, Nest, Ring, Wyze, IKEA, Ecobee, SmartThings, LIFX, Nanoleaf, Aqara, Sonos, and more — under one dashboard. |
| Camera command center | Multi-layout live views, PTZ controls, and AI-powered zones via Frigate NVR integration. |
| Privacy-first by design | Local processing, end-to-end encryption, and no cloud dependency — your data never leaves your home. |
| Real-time glassmorphism UI | React 19 + Vite + Tailwind CSS glassmorphism dashboard with sub-second WebSocket state sync. |

## Architecture at a glance

```
MYiot/
├── app/        React 19 + Vite glassmorphism dashboard
├── hub/        FastAPI backend — WebSocket, discovery, automation
├── scripts/    PowerShell / shell starters
└── docker-compose.yml  — one-command local stack
```

## Development

```bash
# Terminal 1 — backend
cd hub && . .venv/bin/activate && uvicorn main:app --reload --host 0.0.0.0 --port 8000
# Terminal 2 — frontend
cd app && npm run dev
```

## Roadmap

- [ ] Frigate NVR camera AI zones and alerting
- [ ] Zigbee2MQTT and Z-Wave JS device bridges
- [ ] Mobile PWA with offline-first dashboard cache

## Support & consulting

Need deterministic AI systems with full traceability? LumenHelix builds reversible computation kernels, governance layers, and end-to-end AI integrations.

- **Website:** https://lumenhelix.com
- **Services:** AI diagnostics, B.Y.O. support packages, governance audits
- **Research:** TEN² kernel, R.U.B.I.C. boundary discipline, C.O.R.E. constraint lens

## License

Licensed under the Creative Commons Attribution-NonCommercial 4.0 International License.

---

<p align="center">
  <sub>Engineered by <a href="https://lumenhelix.com">LumenHelix Solutions</a> — Applied Symbolic Dynamics & Reversible Computation.</sub>
</p>
