# MYiot API Documentation

> **MYiot** — Universal Smart Home Hub REST API & WebSocket Events
>
> **Base URL:** `http://localhost:8000` (development) / `https://myiot.local` (production)
> **API Version:** `v1`
> **Brand Colors:** `#081021` | `#6366F1` | `#06B6D4` | `#F59E0B`

---

## Table of Contents

- [Authentication](#authentication)
- [REST API Endpoints](#rest-api-endpoints)
  - [Auth](#auth-endpoints)
  - [Devices](#device-endpoints)
  - [Cameras](#camera-endpoints)
  - [Rooms](#room-endpoints)
  - [Automations](#automation-endpoints)
  - [System](#system-endpoints)
- [WebSocket Events](#websocket-events)
- [Frigate Integration](#frigate-integration)
- [Error Handling](#error-handling)
- [Rate Limiting](#rate-limiting)

---

## Authentication

MYiot uses **JWT (JSON Web Tokens)** for authentication. All protected endpoints require a valid `Bearer` token in the `Authorization` header.

### Login

```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "username": "admin",
  "password": "your-secure-password"
}
```

**Response (200 OK):**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": {
    "id": "usr_01HQMZ...",
    "username": "admin",
    "display_name": "Administrator",
    "role": "admin",
    "permissions": ["*"]
  }
}
```

### Refresh Token

```http
POST /api/v1/auth/refresh
Content-Type: application/json

{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response (200 OK):**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

### Using the Token

```http
GET /api/v1/devices
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### Token Details

| Property | Value |
|----------|-------|
| Algorithm | HS256 |
| Access token expiry | 60 minutes |
| Refresh token expiry | 7 days |
| Refresh token storage | Redis (revocable) |

---

## REST API Endpoints

### Auth Endpoints

#### `POST /api/v1/auth/register`

Register a new user account (admin only in production).

**Request:**

```json
{
  "username": "newuser",
  "password": "secure-password-123",
  "display_name": "New User",
  "role": "user"
}
```

**Response (201 Created):**

```json
{
  "id": "usr_01HQMZ...",
  "username": "newuser",
  "display_name": "New User",
  "role": "user",
  "created_at": "2025-01-15T10:30:00Z"
}
```

#### `GET /api/v1/auth/me`

Get current authenticated user.

**Response (200 OK):**

```json
{
  "id": "usr_01HQMZ...",
  "username": "admin",
  "display_name": "Administrator",
  "role": "admin",
  "permissions": ["*"],
  "created_at": "2025-01-01T00:00:00Z",
  "last_login": "2025-01-15T10:30:00Z"
}
```

#### `POST /api/v1/auth/logout`

Revoke current access and refresh tokens.

**Response (200 OK):**

```json
{
  "message": "Successfully logged out"
}
```

---

### Device Endpoints

#### `GET /api/v1/devices`

List all devices with optional filtering.

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `room_id` | string | Filter by room |
| `protocol` | string | Filter by protocol (`zigbee`, `zwave`, `wifi`, `ble`) |
| `type` | string | Filter by device type |
| `status` | string | Filter by status (`online`, `offline`, `unavailable`) |
| `search` | string | Text search across name, manufacturer, model |
| `page` | integer | Page number (default: 1) |
| `limit` | integer | Items per page (default: 50, max: 200) |

**Response (200 OK):**

```json
{
  "items": [
    {
      "id": "dev_01HQMZ...",
      "name": "Living Room Light",
      "manufacturer": "Philips",
      "model": "LWA001",
      "protocol": "zigbee",
      "type": "light",
      "room_id": "room_01HQMZ...",
      "room_name": "Living Room",
      "status": "online",
      "battery": null,
      "capabilities": ["on_off", "dimmer"],
      "state": {
        "on": true,
        "brightness": 180,
        "color_temp": 350
      },
      "last_seen": "2025-01-15T12:34:56Z",
      "created_at": "2025-01-01T00:00:00Z"
    }
  ],
  "total": 42,
  "page": 1,
  "limit": 50,
  "pages": 1
}
```

#### `GET /api/v1/devices/{device_id}`

Get a single device with full details.

**Response (200 OK):**

```json
{
  "id": "dev_01HQMZ...",
  "name": "Living Room Light",
  "manufacturer": "Philips",
  "model": "LWA001",
  "protocol": "zigbee",
  "type": "light",
  "room_id": "room_01HQMZ...",
  "room_name": "Living Room",
  "status": "online",
  "battery": null,
  "capabilities": ["on_off", "dimmer", "color_temp"],
  "state": {
    "on": true,
    "brightness": 180,
    "color_temp": 350
  },
  "config": {
    "power_on_behavior": "previous",
    "transition": 0.5
  },
  "history": {
    "last_on": "2025-01-15T12:00:00Z",
    "last_off": "2025-01-15T08:00:00Z",
    "total_on_time_hours": 1234
  },
  "last_seen": "2025-01-15T12:34:56Z",
  "created_at": "2025-01-01T00:00:00Z"
}
```

#### `PATCH /api/v1/devices/{device_id}`

Update device properties (name, room, config).

**Request:**

```json
{
  "name": "Living Room Main Light",
  "room_id": "room_01HQMZ...",
  "config": {
    "transition": 1.0
  }
}
```

**Response (200 OK):** Updated device object.

#### `POST /api/v1/devices/{device_id}/command`

Send a command to a device.

**Request:**

```json
{
  "command": "set_state",
  "params": {
    "on": true,
    "brightness": 255,
    "transition": 0.5
  }
}
```

**Available commands by capability:**

| Capability | Commands |
|-----------|----------|
| `on_off` | `turn_on`, `turn_off`, `toggle` |
| `dimmer` | `set_brightness`, `step_up`, `step_down` |
| `color` | `set_color`, `set_color_temp`, `set_hue`, `set_saturation` |
| `cover` | `open`, `close`, `stop`, `set_position` |
| `climate` | `set_temperature`, `set_mode`, `set_fan_speed` |
| `lock` | `lock`, `unlock` |

**Response (200 OK):**

```json
{
  "success": true,
  "device_id": "dev_01HQMZ...",
  "command": "set_state",
  "new_state": {
    "on": true,
    "brightness": 255
  },
  "executed_at": "2025-01-15T12:35:01Z"
}
```

#### `DELETE /api/v1/devices/{device_id}`

Remove a device from MYiot. This does **not** factory-reset the device.

**Response (204 No Content):**

#### `POST /api/v1/devices/discover`

Start a device discovery scan for a specific protocol.

**Request:**

```json
{
  "protocol": "zigbee",
  "duration_seconds": 60
}
```

**Response (202 Accepted):**

```json
{
  "scan_id": "scan_01HQMZ...",
  "protocol": "zigbee",
  "status": "scanning",
  "started_at": "2025-01-15T12:35:00Z",
  "ends_at": "2025-01-15T12:36:00Z"
}
```

#### `GET /api/v1/devices/discover/{scan_id}`

Get discovery scan results.

**Response (200 OK):**

```json
{
  "scan_id": "scan_01HQMZ...",
  "protocol": "zigbee",
  "status": "completed",
  "found_devices": [
    {
      "ieee_address": "0x00158d0001234567",
      "manufacturer": "Aqara",
      "model": "WSDCGQ11LM",
      "type": "temperature_sensor",
      "capabilities": ["temperature", "humidity", "pressure"]
    }
  ],
  "started_at": "2025-01-15T12:35:00Z",
  "completed_at": "2025-01-15T12:36:00Z"
}
```

#### `POST /api/v1/devices/discover/{scan_id}/pair`

Pair a discovered device.

**Request:**

```json
{
  "ieee_address": "0x00158d0001234567",
  "name": "Bedroom Temperature Sensor",
  "room_id": "room_01HQMZ..."
}
```

**Response (201 Created):** The newly paired device object.

---

### Camera Endpoints

#### `GET /api/v1/cameras`

List all configured cameras.

**Response (200 OK):**

```json
{
  "items": [
    {
      "id": "cam_01HQMZ...",
      "name": "Front Door",
      "manufacturer": "Reolink",
      "model": "RLC-810A",
      "room_id": "room_01HQMZ...",
      "room_name": "Exterior",
      "status": "online",
      "stream_url": "rtsp://192.168.1.100:554/stream1",
      "frigate_camera": "front_door",
      "capabilities": ["stream", "record", "motion_detect", "night_vision"],
      "resolution": "3840x2160",
      "fps": 15,
      "recording_enabled": true,
      "motion_detection": true,
      "last_event": {
        "type": "motion",
        "timestamp": "2025-01-15T12:30:00Z",
        "thumbnail_url": "/api/v1/cameras/cam_01HQMZ.../events/latest/thumbnail"
      },
      "created_at": "2025-01-01T00:00:00Z"
    }
  ]
}
```

#### `GET /api/v1/cameras/{camera_id}/stream`

Get stream configuration for a camera.

**Response (200 OK):**

```json
{
  "camera_id": "cam_01HQMZ...",
  "stream_urls": {
    "hls": "/api/v1/cameras/cam_01HQMZ.../stream/hls",
    "webrtc": "/api/v1/cameras/cam_01HQMZ.../stream/webrtc",
    "snapshot": "/api/v1/cameras/cam_01HQMZ.../snapshot"
  },
  "format": "hls",
  "expires_at": "2025-01-15T13:00:00Z"
}
```

#### `GET /api/v1/cameras/{camera_id}/events`

Get camera event history.

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `start` | ISO datetime | Start of time range |
| `end` | ISO datetime | End of time range |
| `type` | string | Filter by event type (`motion`, `person`, `vehicle`, `animal`) |
| `page` | integer | Page number |
| `limit` | integer | Items per page |

**Response (200 OK):**

```json
{
  "items": [
    {
      "id": "evt_01HQMZ...",
      "camera_id": "cam_01HQMZ...",
      "type": "person",
      "label": "person",
      "confidence": 0.94,
      "start_time": "2025-01-15T12:30:00Z",
      "end_time": "2025-01-15T12:30:15Z",
      "thumbnail_url": "/api/v1/cameras/events/evt_01HQMZ.../thumbnail",
      "clip_url": "/api/v1/cameras/events/evt_01HQMZ.../clip",
      "bbox": [0.25, 0.30, 0.45, 0.80],
      "zones": ["porch"]
    }
  ],
  "total": 156
}
```

#### `GET /api/v1/cameras/{camera_id}/snapshot`

Get a real-time snapshot from a camera.

**Response (200 OK):** `image/jpeg` binary data.

#### `POST /api/v1/cameras/{camera_id}/ptz`

Control PTZ (Pan-Tilt-Zoom) for supported cameras.

**Request:**

```json
{
  "action": "move",
  "direction": "up",
  "speed": 50,
  "duration": 500
}
```

**Actions:** `move`, `zoom_in`, `zoom_out`, `preset`, `stop`

**Directions:** `up`, `down`, `left`, `right`, `up_left`, `up_right`, `down_left`, `down_right`

**Response (200 OK):**

```json
{
  "success": true,
  "action": "move",
  "new_position": {
    "pan": 45.0,
    "tilt": 30.0,
    "zoom": 1.0
  }
}
```

---

### Room Endpoints

#### `GET /api/v1/rooms`

List all rooms.

**Response (200 OK):**

```json
{
  "items": [
    {
      "id": "room_01HQMZ...",
      "name": "Living Room",
      "icon": "sofa",
      "color": "#6366F1",
      "floor": 1,
      "device_count": 12,
      "camera_count": 1,
      "automation_count": 3,
      "created_at": "2025-01-01T00:00:00Z"
    }
  ]
}
```

#### `POST /api/v1/rooms`

Create a new room.

**Request:**

```json
{
  "name": "Office",
  "icon": "monitor",
  "color": "#06B6D4",
  "floor": 2
}
```

**Response (201 Created):** The newly created room object.

#### `GET /api/v1/rooms/{room_id}/devices`

Get all devices in a room.

**Response (200 OK):** Array of device objects.

---

### Automation Endpoints

#### `GET /api/v1/automations`

List all automation rules.

**Response (200 OK):**

```json
{
  "items": [
    {
      "id": "auto_01HQMZ...",
      "name": "Motion Light - Hallway",
      "description": "Turn on hallway light when motion detected",
      "enabled": true,
      "trigger": {
        "type": "device_state",
        "device_id": "dev_motion_01",
        "condition": {
          "property": "occupancy",
          "operator": "eq",
          "value": true
        }
      },
      "conditions": [
        {
          "type": "time_range",
          "after": "sunset",
          "before": "sunrise"
        }
      ],
      "actions": [
        {
          "type": "device_command",
          "device_id": "dev_light_01",
          "command": "turn_on",
          "params": {
            "brightness": 200,
            "transition": 2.0
          }
        }
      ],
      "last_triggered": "2025-01-15T12:15:00Z",
      "trigger_count": 142,
      "created_at": "2025-01-01T00:00:00Z"
    }
  ]
}
```

#### `POST /api/v1/automations`

Create a new automation rule.

**Request:**

```json
{
  "name": "Bedtime Routine",
  "description": "Turn off all lights and arm security at 11 PM",
  "enabled": true,
  "trigger": {
    "type": "schedule",
    "cron": "0 23 * * *"
  },
  "conditions": [],
  "actions": [
    {
      "type": "device_command",
      "device_id": "dev_light_all",
      "command": "turn_off"
    },
    {
      "type": "notification",
      "message": "Bedtime routine activated"
    }
  ]
}
```

**Response (201 Created):** The newly created automation object.

#### `POST /api/v1/automations/{automation_id}/trigger`

Manually trigger an automation rule.

**Response (200 OK):**

```json
{
  "success": true,
  "automation_id": "auto_01HQMZ...",
  "triggered_at": "2025-01-15T12:35:00Z",
  "results": [
    {
      "action": "device_command",
      "success": true,
      "message": "Light turned on"
    }
  ]
}
```

---

### System Endpoints

#### `GET /api/v1/system/health`

Health check endpoint (public, no auth required).

**Response (200 OK):**

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2025-01-15T12:35:00Z",
  "uptime_seconds": 86400,
  "services": {
    "database": "connected",
    "redis": "connected",
    "mqtt": "connected",
    "frigate": "connected"
  }
}
```

#### `GET /api/v1/system/info`

System information and statistics.

**Response (200 OK):**

```json
{
  "version": "1.0.0",
  "platform": "linux",
  "python_version": "3.11.6",
  "hostname": "myiot-hub",
  "cpu_percent": 12.5,
  "memory": {
    "total_mb": 4096,
    "used_mb": 1843,
    "free_mb": 2253
  },
  "disk": {
    "total_gb": 64,
    "used_gb": 23.5,
    "free_gb": 40.5
  },
  "devices": {
    "total": 42,
    "online": 38,
    "offline": 4
  },
  "cameras": {
    "total": 4,
    "streaming": 4
  },
  "automations": {
    "total": 8,
    "enabled": 7
  }
}
```

#### `GET /api/v1/system/logs`

Get application logs.

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `level` | string | Filter by level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `limit` | integer | Number of lines (default: 100) |
| `since` | ISO datetime | Start timestamp |

**Response (200 OK):**

```json
{
  "lines": [
    {
      "timestamp": "2025-01-15T12:34:56Z",
      "level": "INFO",
      "module": "device_service",
      "message": "Device dev_01HQMZ... state updated: on=true"
    }
  ]
}
```

---

## WebSocket Events

Connect to the WebSocket endpoint for real-time updates:

```javascript
const ws = new WebSocket('ws://localhost:8000/ws');

ws.onopen = () => {
  // Authenticate
  ws.send(JSON.stringify({
    type: 'auth',
    token: 'your-jwt-access-token'
  }));

  // Subscribe to topics
  ws.send(JSON.stringify({
    type: 'subscribe',
    topics: ['devices', 'cameras.front_door', 'system.alerts']
  }));
};

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  console.log(message.type, message.payload);
};
```

### Client → Server Messages

| Message Type | Description | Payload |
|-------------|-------------|---------|
| `auth` | Authenticate connection | `{ token: string }` |
| `subscribe` | Subscribe to topics | `{ topics: string[] }` |
| `unsubscribe` | Unsubscribe from topics | `{ topics: string[] }` |
| `ping` | Keep-alive ping | `{}` |
| `device_command` | Send command via WS | `{ device_id, command, params }` |

### Server → Client Messages

#### `device_state_changed`

Fired when any device state changes.

```json
{
  "type": "device_state_changed",
  "timestamp": "2025-01-15T12:35:01Z",
  "payload": {
    "device_id": "dev_01HQMZ...",
    "device_name": "Living Room Light",
    "room_id": "room_01HQMZ...",
    "previous_state": {
      "on": false,
      "brightness": 0
    },
    "new_state": {
      "on": true,
      "brightness": 180
    },
    "changed_properties": ["on", "brightness"],
    "source": "user_action",
    "triggered_by": "usr_01HQMZ..."
  }
}
```

#### `device_connected` / `device_disconnected`

Fired when a device comes online or goes offline.

```json
{
  "type": "device_connected",
  "timestamp": "2025-01-15T12:35:00Z",
  "payload": {
    "device_id": "dev_01HQMZ...",
    "device_name": "Bedroom Sensor",
    "protocol": "zigbee",
    "last_seen": "2025-01-15T12:35:00Z"
  }
}
```

#### `camera_event`

Fired when a camera detects motion or an object.

```json
{
  "type": "camera_event",
  "timestamp": "2025-01-15T12:30:00Z",
  "payload": {
    "camera_id": "cam_01HQMZ...",
    "camera_name": "Front Door",
    "event_id": "evt_01HQMZ...",
    "event_type": "person",
    "label": "person",
    "confidence": 0.94,
    "thumbnail_url": "/api/v1/cameras/events/evt_01HQMZ.../thumbnail",
    "zones": ["porch"]
  }
}
```

#### `automation_triggered`

Fired when an automation rule executes.

```json
{
  "type": "automation_triggered",
  "timestamp": "2025-01-15T12:30:00Z",
  "payload": {
    "automation_id": "auto_01HQMZ...",
    "automation_name": "Motion Light - Hallway",
    "trigger_type": "device_state",
    "results": [
      {
        "action": "device_command",
        "success": true
      }
    ]
  }
}
```

#### `system_alert`

Fired for system-level alerts and notifications.

```json
{
  "type": "system_alert",
  "timestamp": "2025-01-15T12:00:00Z",
  "payload": {
    "level": "warning",
    "title": "Device Offline",
    "message": "Kitchen Sensor (dev_01HQMZ...) has been offline for 15 minutes",
    "device_id": "dev_01HQMZ...",
    "dismissible": true
  }
}
```

#### `pong`

Response to client `ping` messages.

```json
{
  "type": "pong",
  "timestamp": "2025-01-15T12:35:00Z"
}
```

---

## Frigate Integration

MYiot integrates with [Frigate NVR](https://frigate.video/) for camera management, AI object detection, and recording.

### Configuration

Set these environment variables:

| Variable | Description | Example |
|----------|-------------|---------|
| `FRIGATE_URL` | Frigate API base URL | `http://localhost:5000` |
| `FRIGATE_API_KEY` | Frigate API key (optional) | `your-api-key` |
| `FRIGATE_MQTT_TOPIC_PREFIX` | MQTT topic prefix | `frigate` |

### Frigate Proxy Endpoints

MYiot proxies select Frigate endpoints for unified access:

#### `GET /api/v1/frigate/config`

Get Frigate configuration.

**Response (200 OK):** Frigate configuration object.

#### `GET /api/v1/frigate/stats`

Get Frigate performance statistics.

**Response (200 OK):**

```json
{
  "detection_fps": 5.0,
  "detectors": {
    "coral": {
      "inference_speed": 12.5,
      "detection_enabled": true
    }
  },
  "cameras": {
    "front_door": {
      "camera_fps": 15.0,
      "capture_pid": 1234,
      "detection_fps": 5.0,
      "process_fps": 5.0,
      "skipped_fps": 0.0
    }
  }
}
```

#### `GET /api/v1/frigate/recordings`

Query Frigate recordings.

**Query Parameters:**

| Parameter | Description |
|-----------|-------------|
| `camera` | Camera name |
| `label` | Object label filter |
| `zone` | Zone filter |
| `after` | Start timestamp |
| `before` | End timestamp |
| `limit` | Max results |

#### `POST /api/v1/frigate/{camera}/snapshot`

Request a fresh snapshot from Frigate.

**Response (200 OK):** `image/jpeg` binary.

#### `GET /api/v1/frigate/{camera}/recordings/summary`

Get recording summary by hour.

**Response (200 OK):**

```json
{
  "front_door": [
    {
      "hour": "2025-01-15 12:00",
      "duration": 3600,
      "motion_count": 15,
      "object_count": 8
    }
  ]
}
```

### MQTT Events from Frigate

Frigate publishes events to MQTT which MYiot subscribes to:

| Topic Pattern | Description |
|--------------|-------------|
| `frigate/available` | Frigate online status |
| `frigate/events` | Detection events (JSON) |
| `frigate/{camera}/motion` | Motion state (on/off) |
| `frigate/{camera}/objects` | Detected objects |
| `frigate/{camera}/recording/state` | Recording state |

---

## Error Handling

All API errors follow a consistent format:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed",
    "details": [
      {
        "field": "brightness",
        "message": "Value must be between 0 and 255"
      }
    ],
    "request_id": "req_01HQMZ...",
    "timestamp": "2025-01-15T12:35:00Z"
  }
}
```

### Error Codes

| HTTP Status | Error Code | Description |
|-------------|-----------|-------------|
| 400 | `VALIDATION_ERROR` | Request body validation failed |
| 401 | `UNAUTHORIZED` | Missing or invalid authentication |
| 403 | `FORBIDDEN` | Insufficient permissions |
| 404 | `NOT_FOUND` | Resource not found |
| 409 | `CONFLICT` | Resource conflict (e.g., duplicate name) |
| 422 | `UNPROCESSABLE_ENTITY` | Business logic error |
| 429 | `RATE_LIMITED` | Too many requests |
| 500 | `INTERNAL_ERROR` | Server error |
| 503 | `SERVICE_UNAVAILABLE` | Dependency service unavailable |

---

## Rate Limiting

API rate limits are applied per client IP and per authenticated user:

| Scope | Limit | Window |
|-------|-------|--------|
| Anonymous IP | 30 requests | 1 minute |
| Authenticated user | 1,000 requests | 1 minute |
| Login attempts | 5 attempts | 5 minutes |
| WebSocket messages | 100 messages | 1 minute |

Rate limit headers are included in all responses:

```http
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1705319700
```

---

*For additional details, explore the interactive API documentation at `/docs` when running the MYiot backend.*
