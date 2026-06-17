# Full Backend Integration Plan

## Phase 1: Backend Fix & Startup
- Fix any backend import issues
- Install Python dependencies
- Start FastAPI server on port 8000
- Verify API endpoints work

## Phase 2: Frontend API Client Layer
- Create `src/api/client.ts` — fetch wrapper with error handling
- Create `src/api/websocket.ts` — WebSocket connection manager with auto-reconnect
- Create `src/api/devices.ts`, `cameras.ts`, `alerts.ts`, `zones.ts` — typed API modules
- Replace in-memory state with API calls

## Phase 3: Camera Streaming
- Add MJPEG proxy endpoint to backend (RTSP → MJPEG for browsers)
- Add WebRTC endpoint for low-latency streams
- Frontend: `<img src="/api/cameras/{id}/mjpeg">` for live feeds
- Frontend: WebRTC peer connection for supported cameras

## Phase 4: Real-Time Sync
- WebSocket broadcasts state changes to all clients
- Frontend listens and updates UI in real-time
- Two-way: Frontend actions → API → Backend state → WebSocket → All clients

## Phase 5: Serve Frontend from Backend
- FastAPI serves static React build from `dist/`
- Single port (8000) serves both API and UI
- Backend runs continuously in the container
