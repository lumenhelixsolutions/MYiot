"""
Camera streaming proxy for Smart Home Universal Hub.

Provides MJPEG and WebRTC proxy endpoints for camera feeds.
Since cameras use RTSP which browsers can't play directly,
this module transcodes RTSP → MJPEG for browser compatibility.

For cameras that are offline or unreachable, generates synthetic
frames with camera info and status so the UI always has content.
"""

import asyncio
import io
import logging
import os
import time
from typing import AsyncGenerator, Optional

import aiohttp
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

GO2RTC_URL = os.environ.get("GO2RTC_URL", "http://localhost:1984")


class WebRTCOfferRequest(BaseModel):
    """Client SDP offer for establishing a WebRTC playback session."""

    sdp: str
    type: str = "offer"


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
            timeout=aiohttp.ClientTimeout(total=None, sock_read=30),
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


async def _proxy_go2rtc_webrtc(
    camera_id: str, stream_url: str, offer_sdp: str
) -> str:
    """Push a stream to go2rtc and exchange SDP for WebRTC playback.

    go2rtc implements a WHEP-like endpoint at /api/webrtc. We send the
    client's SDP offer and return go2rtc's SDP answer.
    """
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
                raise RuntimeError(f"go2rtc add stream failed: {add_resp.status}")

        webrtc_url = f"{GO2RTC_URL}/api/webrtc"
        async with session.post(
            webrtc_url,
            params={"src": name},
            data=offer_sdp,
            headers={"Content-Type": "application/sdp"},
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            answer = await resp.text()
            if resp.status != 200:
                logger.warning(
                    "go2rtc WebRTC returned %s for %s: %s",
                    resp.status,
                    camera_id,
                    answer[:200],
                )
                raise RuntimeError(f"go2rtc WebRTC failed: {resp.status}")
            return answer
    finally:
        await session.close()

router = APIRouter()

# ─── Synthetic MJPEG Frame Generator ──────────────────────────────────────

# Cache for frame generators per camera
_frame_generators: dict[str, asyncio.Task] = {}


def _generate_status_frame(width: int, height: int, camera_name: str, status: str, details: str = "", timestamp: float = 0) -> bytes:
    """Generate a synthetic JPEG frame showing camera status."""
    img = Image.new('RGB', (width, height), color=(8, 8, 16))
    draw = ImageDraw.Draw(img)

    # Background gradient simulation
    for y in range(height):
        r = int(8 + (y / height) * 12)
        g = int(8 + (y / height) * 10)
        b = int(16 + (y / height) * 18)
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    # Status color
    if status == "LIVE":
        status_color = (239, 68, 68)  # Red
        icon_color = (16, 185, 129)   # Green dot
    elif status == "OFFLINE":
        status_color = (100, 100, 110)
        icon_color = (100, 100, 110)
    else:  # Privacy
        status_color = (245, 158, 11)  # Amber
        icon_color = (245, 158, 11)

    # Draw camera icon (rectangle with lens)
    cx, cy = width // 2, height // 2 - 20
    # Camera body
    draw.rectangle([cx - 40, cy - 25, cx + 40, cy + 20], fill=(30, 30, 45), outline=(60, 60, 80), width=2)
    # Lens
    draw.ellipse([cx - 18, cy - 18, cx + 18, cy + 18], fill=(20, 20, 35), outline=(80, 80, 100), width=2)
    draw.ellipse([cx - 8, cy - 8, cx + 8, cy + 8], fill=(50, 50, 70))
    # Indicator light
    draw.ellipse([cx + 25, cy - 20, cx + 33, cy - 12], fill=icon_color)

    # Status text
    try:
        font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
        font_medium = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 11)
    except:
        font_large = ImageFont.load_default()
        font_medium = ImageFont.load_default()
        font_small = ImageFont.load_default()

    # Camera name
    name_bbox = draw.textbbox((0, 0), camera_name, font=font_large)
    name_w = name_bbox[2] - name_bbox[0]
    draw.text(((width - name_w) // 2, cy + 35), camera_name, fill=(200, 200, 210), font=font_large)

    # Status badge
    status_bbox = draw.textbbox((0, 0), status, font=font_medium)
    status_w = status_bbox[2] - status_bbox[0]
    badge_x = (width - status_w) // 2 - 10
    badge_y = cy + 62
    draw.rounded_rectangle([badge_x, badge_y, badge_x + status_w + 20, badge_y + 24], radius=12, fill=(*status_color, 30))
    draw.text((badge_x + 10, badge_y + 3), status, fill=status_color, font=font_medium)

    # Details line
    if details:
        det_bbox = draw.textbbox((0, 0), details, font=font_small)
        det_w = det_bbox[2] - det_bbox[0]
        draw.text(((width - det_w) // 2, cy + 95), details, fill=(100, 100, 115), font=font_small)

    # Timestamp
    ts_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp or time.time()))
    draw.text((width - 150, height - 20), ts_str, fill=(80, 80, 95), font=font_small)

    # MYiot watermark
    draw.text((10, height - 20), "MYiot", fill=(99, 102, 241, 128), font=font_small)

    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=75)
    return buf.getvalue()


def _generate_live_frame(width: int, height: int, camera_name: str, pan: float, tilt: float, zoom: float, timestamp: float) -> bytes:
    """Generate a synthetic 'live' frame with animated content."""
    img = Image.new('RGB', (width, height), color=(10, 12, 20))
    draw = ImageDraw.Draw(img)

    # Animated background based on pan/tilt
    cx = int(width * (0.5 + pan / 200))
    cy = int(height * (0.5 + tilt / 200))

    # Radial gradient center
    for r in range(max(width, height), 0, -4):
        intensity = max(0, 1 - r / max(width, height))
        cr = int(15 + intensity * 25 * (1 + zoom / 10))
        cg = int(15 + intensity * 20 * (1 + zoom / 10))
        cb = int(25 + intensity * 30 * (1 + zoom / 10))
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(cr, cg, cb))

    # Moving particles (simulated motion)
    t = timestamp % 10
    for i in range(8):
        px = int((width * (0.2 + i * 0.08) + t * 8) % width)
        py = int(height * (0.3 + (i % 3) * 0.2) + (t * 3 if i % 2 else -t * 3) % height)
        size = 2 + (i % 3)
        brightness = 120 + (i * 15)
        draw.ellipse([px - size, py - size, px + size, py + size], fill=(brightness, brightness, brightness + 20))

    # Scanlines
    for y in range(0, height, 3):
        draw.line([(0, y), (width, y)], fill=(0, 0, 0, 30))

    # Grid overlay
    grid_spacing = 40
    for x in range(0, width, grid_spacing):
        draw.line([(x, 0), (x, height)], fill=(255, 255, 255, 8))
    for y in range(0, height, grid_spacing):
        draw.line([(0, y), (width, y)], fill=(255, 255, 255, 8))

    try:
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 10)
        font_tiny = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 9)
    except:
        font_small = ImageFont.load_default()
        font_tiny = ImageFont.load_default()

    # Crosshair center
    ch_color = (99, 102, 241, 60)
    draw.line([(cx, cy - 15), (cx, cy + 15)], fill=ch_color, width=1)
    draw.line([(cx - 15, cy), (cx + 15, cy)], fill=ch_color, width=1)

    # Info overlay
    ts_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))
    draw.text((10, 10), camera_name, fill=(255, 255, 255, 200), font=font_small)
    draw.text((10, 24), f"PAN:{pan:+.1f} TILT:{tilt:+.1f} ZOOM:{zoom:.1f}x", fill=(150, 150, 160), font=font_tiny)
    draw.text((width - 130, 10), ts_str, fill=(150, 150, 160), font=font_tiny)
    draw.text((width - 60, height - 15), "MYiot", fill=(99, 102, 241), font=font_tiny)

    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=75)
    return buf.getvalue()


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
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("go2rtc proxy failed for %s: %s", camera_id, exc)

    # Synthetic fallback
    try:
        while True:
            timestamp = time.time()
            if status == "LIVE":
                frame = _generate_live_frame(
                    width, height, camera_name, 0, 0, 1.0, timestamp
                )
            else:
                details = stream_url if stream_url else "No stream configured"
                frame = _generate_status_frame(
                    width, height, camera_name, status, details, timestamp
                )
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


# ─── API Routes ───────────────────────────────────────────────────────────


@router.get("/api/cameras/{camera_id}/mjpeg")
async def camera_mjpeg_stream(camera_id: str, request: Request):
    """
    Stream a camera feed as MJPEG.

    Returns a multipart/x-mixed-replace stream of JPEG frames.
    The frame content depends on the camera's current status:
    - LIVE: Animated synthetic feed with PTZ info
    - OFFLINE: Status frame with offline indicator
    - PRIVACY: Status frame with privacy mode indicator
    """
    registry = request.app.state.registry

    # Get camera from registry
    device = await registry.get(camera_id)
    if not device:
        raise HTTPException(status_code=404, detail="Camera not found")

    if device.device_type != "camera":
        raise HTTPException(status_code=400, detail="Device is not a camera")

    # Determine status
    online = device.state.get("online", True)
    power = device.state.get("power", True)

    if not online:
        status = "OFFLINE"
    elif not power:
        status = "PRIVACY"
    else:
        status = "LIVE"

    stream_url = device.state.get("stream_url")
    camera_name = device.state.get("name", camera_id)

    return StreamingResponse(
        _mjpeg_stream_generator(camera_id, camera_name, status, stream_url),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@router.post("/api/cameras/{camera_id}/webrtc")
async def camera_webrtc_offer(
    camera_id: str,
    request: Request,
    offer: WebRTCOfferRequest,
):
    """
    Exchange an SDP offer for a WebRTC playback session.

    This is a WHEP-like endpoint: the client sends an SDP offer, the
    backend proxies it to go2rtc, and returns the SDP answer. The
    browser can then set the remote description and start receiving
    the camera stream via WebRTC.

    If the camera is offline, has no stream URL, or go2rtc is
    unreachable, a 503 error is returned and the client should fall
    back to the MJPEG endpoint.
    """
    registry = request.app.state.registry

    device = await registry.get(camera_id)
    if not device:
        raise HTTPException(status_code=404, detail="Camera not found")

    if device.device_type != "camera":
        raise HTTPException(status_code=400, detail="Device is not a camera")

    online = device.state.get("online", True)
    power = device.state.get("power", True)
    if not online or not power:
        raise HTTPException(
            status_code=503,
            detail="Camera is offline or in privacy mode",
        )

    stream_url = device.state.get("stream_url")
    if not stream_url:
        raise HTTPException(
            status_code=503,
            detail="Camera has no stream URL configured",
        )

    try:
        answer_sdp = await _proxy_go2rtc_webrtc(
            camera_id, stream_url, offer.sdp
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("WebRTC offer failed for %s: %s", camera_id, exc)
        raise HTTPException(
            status_code=503,
            detail=f"WebRTC negotiation failed: {exc}",
        )

    return {"type": "answer", "sdp": answer_sdp}


@router.get("/api/cameras/{camera_id}/snapshot")
async def camera_snapshot(camera_id: str, request: Request):
    """
    Get a single JPEG snapshot from a camera.

    Returns the current frame as a static JPEG image.
    """
    registry = request.app.state.registry

    device = await registry.get(camera_id)
    if not device:
        raise HTTPException(status_code=404, detail="Camera not found")

    if device.device_type != "camera":
        raise HTTPException(status_code=400, detail="Device is not a camera")

    online = device.state.get("online", True)
    power = device.state.get("power", True)

    if not online:
        status = "OFFLINE"
    elif not power:
        status = "PRIVACY"
    else:
        status = "LIVE"

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


@router.get("/api/cameras")
async def list_cameras(request: Request):
    """List all camera devices."""
    registry = request.app.state.registry
    all_devices = await registry.get_all()
    cameras = [d for d in all_devices if d.device_type == "camera"]
    return [c.model_dump() for c in cameras]
