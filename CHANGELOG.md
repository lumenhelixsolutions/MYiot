# Changelog

All notable changes to MYiot will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Multi-camera command center with 5 layout modes (1x1, 2x2, 3x3, 1+2, 2+1)
- PTZ controls with zoom support
- Zone monitoring with motion detection and sensitivity controls
- Custom alert system with acknowledge, filter, and rule engine
- Recording controls with manual and triggered capture
- Fullscreen camera viewer
- Frigate NVR AI integration with real-time object detection overlays
- Animated device discovery with state-machine pairing
- WebSocket real-time sync with auto-reconnect
- Hybrid state architecture (API-first with local fallback)
- 17+ manufacturer support including Philips Hue, TP-Link Kasa, Nest, Ring, Wyze, IKEA, Ecobee, Samsung SmartThings
- Premium glassmorphism dark theme with spring animations
- NODI mascot branding and identity

## [0.1.0] - 2025-01-15

### Added
- Initial release of MYiot universal smart home hub
- React 19 + TypeScript + Vite frontend
- FastAPI Python backend with WebSocket support
- Device management with 19 pre-configured devices across 4 rooms
- Dashboard with live activity feed and room cards
- Settings with manufacturer configuration and credentials
- Activity log with date-grouped timeline
- Docker and docker-compose support
- CI/CD pipeline with GitHub Actions
