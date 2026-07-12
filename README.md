# MYiot

<p align="center">
  <img src="docs/assets/logo.svg" alt="MYiot logo" width="160">
</p>

<h3 align="center">Secure. Smart. Connected.</h3>

<p align="center">One universal hub for every smart device in your home.</p>

<p align="center">
  <a href="https://lumenhelixsolutions.github.io/MYiot/">Launch Page</a>
  <span> · </span>
  <a href="https://github.com/lumenhelixsolutions/MYiot">GitHub</a>
  <span> · </span>
  <a href="https://lumenhelix.com">LumenHelix</a>
</p>

---

MYiot unifies lights, cameras, locks, thermostats, and sensors from any manufacturer behind a single local-first API and dashboard.

## Why MYiot

- **Own your home.** Local-first processing means your data never leaves the house.
- **Connect everything.** One dashboard for 17+ brands and protocols.
- **Stay secure.** Encrypted credentials and audit logging by default.

## Quick start

### macOS / Linux

```bash
git clone https://github.com/lumenhelixsolutions/MYiot.git
cd MYiot
cp hub/.env.example hub/.env
docker compose up -d
```

### Windows (PowerShell)

```powershell
git clone https://github.com/lumenhelixsolutions/MYiot.git
Set-Location MYiot
copy hub\.env.example hub\.env
docker compose up -d
```

### Windows (Git Bash / WSL)

```bash
git clone https://github.com/lumenhelixsolutions/MYiot.git
cd MYiot
cp hub/.env.example hub/.env
docker compose up -d
```

> Tested on Windows 11, macOS Sonoma, Ubuntu 22.04/24.04, and modern mobile browsers.

## Features

| Feature | What it gives you |
|---------|-------------------|
| Universal control | One abstraction for Hue, Nest, Ring, Wyze, SmartThings, and 12+ more brands. |
| Real-time streaming | WebRTC and MJPEG camera feeds with sub-second state sync across every device. |
| Privacy by design | Local processing, encrypted credentials, and no mandatory cloud dependency. |
| Plugin driver system | Add new manufacturers without touching core code — drivers load dynamically. |

## Architecture

```
React Dashboard  ->  FastAPI Hub  ->  Universal Device Engine  ->  Plugin Drivers  ->  Devices
                              ^                                        |
                              └────────── WebSocket state sync ────────┘
```

## Development

```bash
# Terminal 1: backend
cd hub && python -m uvicorn main:app --reload
# Terminal 2: dashboard
cd app && npm run dev
```

## Roadmap

- [ ] Matter / Thread support
- [ ] Mobile app beta
- [ ] Voice assistant integration

## License

Released under CC BY-NC 4.0. Commercial use requires written permission.

---

<p align="center">
  <sub>MYiot is a <a href="https://lumenhelix.com">LumenHelix</a> project — Applied Symbolic Dynamics & Reversible Computation.</sub>
</p>
