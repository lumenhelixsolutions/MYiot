"""Blink camera plugin — REST API with login + PIN verification."""

import logging
import time
from typing import Any, Dict, Optional

import aiohttp

from core.base_driver import BaseDriver, DeviceState
from core.payloads import CameraPayload

logger = logging.getLogger(__name__)

BASE_URL = "https://rest-prod.immedia-semi.com"
LOGIN_URL = "https://rest-prod.immedia-semi.com/api/v4/account/login"


def _translate_from_blink(camera: Dict[str, Any]) -> Dict[str, Any]:
    """Parse Blink camera response into standardized state."""
    state = {}
    state["power"] = camera.get("enabled", False)
    state["recording"] = camera.get("recording", False)
    state["battery"] = camera.get("battery", "")
    state["temperature"] = camera.get("temperature", None)
    state["wifi_signal"] = camera.get("wifi_signal", None)
    state["thumbnail"] = camera.get("thumbnail", "")
    return state


class BlinkPlugin(BaseDriver):
    """Blink camera plugin driver.

    Uses the Blink REST API with login and PIN verification.
    """

    def __init__(self, device_config: Dict[str, Any]):
        super().__init__(device_config)
        self._email = device_config.get("email", "")
        self._password = device_config.get("password", "")
        self._account_id = device_config.get("account_id", "")
        self._region = device_config.get("region", "prod")
        self._auth_token = ""
        self._network_id = device_config.get("network_id", "")

    async def authenticate(self, credentials: Dict[str, Any]) -> bool:
        """Login with email/password to obtain auth token."""
        self._email = credentials.get("email", self._email)
        self._password = credentials.get("password", self._password)
        try:
            if self._session is None or getattr(self._session, "closed", True):
                self._session = aiohttp.ClientSession()
            payload = {
                "email": self._email,
                "password": self._password,
                "unique_id": self.device_id,
                "device_identifier": "SmartHomeHub",
            }
            async with self._session.post(LOGIN_URL, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self._auth_token = data.get("authtoken", {}).get("authtoken", "")
                    self._account_id = str(data.get("account", {}).get("id", ""))
                    # Update region-specific base URL
                    region = data.get("region", {}).get("tier", "prod")
                    self._region = region
                    self._connected = bool(self._auth_token)
                    logger.info(
                        "BlinkPlugin: login OK, token=%s...",
                        self._auth_token[:8] if self._auth_token else "none",
                    )
                    return self._connected
                logger.warning("BlinkPlugin: login failed: %s", resp.status)
                return False
        except Exception as exc:
            logger.error("BlinkPlugin: authenticate error: %s", exc)
            return False

    async def get_state(self) -> DeviceState:
        """GET homescreen and parse camera state."""
        if self._session is None or getattr(self._session, "closed", True):
            self._session = aiohttp.ClientSession()
        headers = {
            "token-auth": self._auth_token,
            "user-id": self._account_id,
        }
        region_url = f"https://rest-{self._region}.immedia-semi.com"
        try:
            async with self._session.get(
                f"{region_url}/api/v3/accounts/{self._account_id}/homescreen",
                headers=headers,
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    cameras = data.get("cameras", [])
                    for cam in cameras:
                        if str(cam.get("id")) == self.device_id:
                            state = _translate_from_blink(cam)
                            return DeviceState(
                                device_id=self.device_id,
                                manufacturer="blink",
                                model=cam.get("type", "blink_camera"),
                                device_type="camera",
                                online=True,
                                state=state,
                                last_updated=time.time(),
                            )
                    logger.warning("BlinkPlugin: camera %s not found", self.device_id)
                    return self._offline_state()
                else:
                    logger.warning("BlinkPlugin: get_state status %s", resp.status)
                    return self._offline_state()
        except Exception as exc:
            logger.error("BlinkPlugin: get_state error: %s", exc)
            return self._offline_state()

    async def set_state(self, payload: Dict[str, Any]) -> bool:
        """POST camera command (arm/disarm, enable/disable)."""
        if self._session is None or getattr(self._session, "closed", True):
            self._session = aiohttp.ClientSession()
        power = payload.get("power")
        if power is None:
            logger.warning("BlinkPlugin: set_state requires power field")
            return False
        headers = {
            "token-auth": self._auth_token,
            "user-id": self._account_id,
        }
        region_url = f"https://rest-{self._region}.immedia-semi.com"
        enabled = 1 if power else 0
        try:
            async with self._session.post(
                f"{region_url}/api/v1/accounts/{self._account_id}"
                f"/networks/{self._network_id}/cameras/{self.device_id}/configure",
                headers=headers,
                json={"enabled": enabled},
            ) as resp:
                success = resp.status == 200
                logger.info(
                    "BlinkPlugin: set_state power=%s -> success=%s",
                    power,
                    success,
                )
                return success
        except Exception as exc:
            logger.error("BlinkPlugin: set_state error: %s", exc)
            return False

    async def capture_snapshot(self) -> Optional[bytes]:
        """Request thumbnail image from the camera."""
        if self._session is None or getattr(self._session, "closed", True):
            self._session = aiohttp.ClientSession()
        headers = {
            "token-auth": self._auth_token,
            "user-id": self._account_id,
        }
        region_url = f"https://rest-{self._region}.immedia-semi.com"
        try:
            # First get homescreen to find thumbnail URL
            async with self._session.get(
                f"{region_url}/api/v3/accounts/{self._account_id}/homescreen",
                headers=headers,
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    for cam in data.get("cameras", []):
                        if str(cam.get("id")) == self.device_id:
                            thumb_url = cam.get("thumbnail", "")
                            if thumb_url:
                                async with self._session.get(thumb_url) as img_resp:
                                    if img_resp.status == 200:
                                        return await img_resp.read()
                return None
        except Exception as exc:
            logger.error("BlinkPlugin: capture_snapshot error: %s", exc)
            return None

    async def disconnect(self) -> None:
        """Close aiohttp session."""
        if self._session and not getattr(self._session, "closed", True):
            await self._session.close()
            logger.info("BlinkPlugin: session closed")
        self._connected = False

    def _offline_state(self) -> DeviceState:
        return DeviceState(
            device_id=self.device_id,
            manufacturer="blink",
            model=self.model,
            device_type="camera",
            online=False,
            state={},
            last_updated=time.time(),
        )
