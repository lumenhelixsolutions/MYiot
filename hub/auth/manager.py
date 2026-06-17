"""
Authentication manager for Smart Home Universal Hub.

Handles secure storage and retrieval of manufacturer credentials using
Fernet symmetric encryption from the cryptography library. Supports
different authentication flows including local network handshakes,
OAuth2 tokens, API keys, and username/password pairs.
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional

from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)


class AuthenticationManager:
    """
    Token and credential storage module.

    Handles local network authentication handshakes and securely stores
credentials using Fernet symmetric encryption. All credentials are
    encrypted at rest and decrypted on demand.
    """

    def __init__(self, storage_path: str = "./data/credentials.json"):
        """
        Initialize the authentication manager.

        Args:
            storage_path: Path to the encrypted credentials file.
                The parent directory and encryption key file will be
                created automatically if they don't exist.
        """
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._key = self._get_or_create_key()
        self._cipher = Fernet(self._key)
        self._credentials: Dict[str, Any] = {}
        self._load()

    def _get_or_create_key(self) -> bytes:
        """
        Get the existing encryption key or generate a new one.

        The key is stored in a hidden file next to the credentials file.
        If the key file exists, its contents are read and returned.
        Otherwise, a new key is generated and saved.

        Returns:
            32-byte Fernet encryption key.
        """
        key_path = self.storage_path.parent / ".key"
        if key_path.exists():
            key_data = key_path.read_bytes()
            logger.debug("Loaded existing encryption key from %s", key_path)
            return key_data
        key = Fernet.generate_key()
        key_path.write_bytes(key)
        # Restrict key file permissions (owner read/write only)
        os.chmod(key_path, 0o600)
        logger.info("Generated new encryption key at %s", key_path)
        return key

    def _load(self) -> None:
        """
        Load encrypted credentials from disk and decrypt them.

        If the credentials file doesn't exist or decryption fails,
        an empty credentials dictionary is used.
        """
        if not self.storage_path.exists():
            logger.debug("No credentials file found at %s", self.storage_path)
            self._credentials = {}
            return

        try:
            encrypted = self.storage_path.read_bytes()
            if not encrypted:
                self._credentials = {}
                return
            decrypted = self._cipher.decrypt(encrypted)
            self._credentials = json.loads(decrypted.decode("utf-8"))
            logger.debug(
                "Loaded credentials for %d manufacturers", len(self._credentials)
            )
        except Exception as exc:
            logger.warning(
                "Failed to decrypt credentials from %s: %s. Starting fresh.",
                self.storage_path,
                exc,
            )
            self._credentials = {}

    def _save(self) -> None:
        """
        Encrypt and save credentials to disk.

        The credentials dictionary is serialized to JSON, encrypted
        with Fernet, and written to the storage path.
        """
        try:
            json_data = json.dumps(self._credentials, indent=2).encode("utf-8")
            encrypted = self._cipher.encrypt(json_data)
            self.storage_path.write_bytes(encrypted)
            # Restrict credentials file permissions
            os.chmod(self.storage_path, 0o600)
            logger.debug(
                "Saved credentials for %d manufacturers", len(self._credentials)
            )
        except Exception as exc:
            logger.error("Failed to save credentials: %s", exc)
            raise RuntimeError(f"Failed to save credentials: {exc}") from exc

    def store(self, manufacturer: str, credentials: Dict[str, Any]) -> None:
        """
        Store credentials for a manufacturer.

        Args:
            manufacturer: Manufacturer key (e.g., "philips_hue", "nest").
            credentials: Dictionary containing authentication data
                (tokens, API keys, passwords, etc.).
        """
        self._credentials[manufacturer] = credentials
        self._save()
        logger.info("Stored credentials for manufacturer '%s'", manufacturer)

    def get(self, manufacturer: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve credentials for a manufacturer.

        Args:
            manufacturer: Manufacturer key.

        Returns:
            The stored credentials dictionary, or None if not found.
        """
        return self._credentials.get(manufacturer)

    def delete(self, manufacturer: str) -> bool:
        """
        Delete credentials for a manufacturer.

        Args:
            manufacturer: Manufacturer key to delete.

        Returns:
            True if credentials existed and were deleted, False otherwise.
        """
        if manufacturer in self._credentials:
            del self._credentials[manufacturer]
            self._save()
            logger.info("Deleted credentials for manufacturer '%s'", manufacturer)
            return True
        return False

    def list_manufacturers(self) -> list[str]:
        """
        List all manufacturers with stored credentials.

        Returns:
            List of manufacturer keys.
        """
        return list(self._credentials.keys())

    async def authenticate_hue_bridge(self, ip: str) -> Optional[str]:
        """
        Special handler for Philips Hue bridge token creation.

        Initiates the push-link authentication flow on the Hue bridge.
        The user must press the physical button on the bridge within
        30 seconds for this to succeed.

        Args:
            ip: IP address of the Hue bridge on the local network.

        Returns:
            The generated bridge username/token if successful, None otherwise.

        Note:
            This is an async stub. Full implementation requires aiohttp
            to POST to http://{ip}/api with {"devicetype": "universal_hub#app"}.
        """
        import aiohttp

        url = f"http://{ip}/api"
        payload = {"devicetype": "universal_hub#backend"}

        logger.info(
            "Starting Hue bridge authentication with %s — "
            "press the link button on the bridge now",
            ip,
        )

        try:
            timeout = aiohttp.ClientTimeout(total=35)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                # Try for up to 30 seconds (Hue requires button press)
                for attempt in range(30):
                    async with session.post(url, json=payload) as resp:
                        data = await resp.json()
                        if isinstance(data, list) and len(data) > 0:
                            result = data[0]
                            if "success" in result:
                                username = result["success"]["username"]
                                logger.info(
                                    "Hue bridge authentication successful — username: %s",
                                    username,
                                )
                                self.store("philips_hue", {"username": username, "ip": ip})
                                return username
                            elif "error" in result:
                                error_type = result["error"].get("type")
                                if error_type == 101:
                                    # Link button not pressed — keep trying
                                    logger.debug(
                                        "Hue bridge link button not pressed (attempt %d)",
                                        attempt + 1,
                                    )
                                    await asyncio.sleep(1)
                                    continue
                                else:
                                    logger.error(
                                        "Hue bridge error: %s", result["error"]
                                    )
                                    return None
        except ImportError:
            logger.error("aiohttp is required for Hue bridge authentication")
            return None
        except Exception as exc:
            logger.error("Hue bridge authentication failed: %s", exc)
            return None

        logger.warning("Hue bridge authentication timed out — link button not pressed")
        return None


# Need asyncio for the Hue bridge auth method
import asyncio  # noqa: E402
