"""Auth-related configuration loaded from environment or generated files."""

import os
import secrets
from pathlib import Path
from typing import List


class AuthSettings:
    """Runtime auth settings."""

    def __init__(self) -> None:
        self.secret_key = self._load_or_create_secret()
        self.access_token_expire_minutes = int(
            os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
        )
        origins_str = os.environ.get(
            "FRONTEND_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173,https://localhost:5173",
        )
        self.frontend_origins = [
            o.strip() for o in origins_str.split(",") if o.strip()
        ]
        hosts_str = os.environ.get("ALLOWED_HOSTS", "*")
        self.allowed_hosts = [
            h.strip() for h in hosts_str.split(",") if h.strip()
        ] or ["*"]
        self.admin_username = os.environ.get("ADMIN_USERNAME", "admin")
        self.admin_password = os.environ.get("ADMIN_PASSWORD", "")
        self.ssl_certfile = os.environ.get("SSL_CERTFILE")
        self.ssl_keyfile = os.environ.get("SSL_KEYFILE")

    def _load_or_create_secret(self) -> str:
        """Load SECRET_KEY from env or from ./data/.secret_key."""
        env_key = os.environ.get("SECRET_KEY")
        if env_key:
            return env_key
        key_path = Path("./data/.secret_key")
        if key_path.exists():
            return key_path.read_text().strip()
        key_path.parent.mkdir(parents=True, exist_ok=True)
        key = secrets.token_urlsafe(32)
        key_path.write_text(key)
        os.chmod(key_path, 0o600)
        return key


settings = AuthSettings()
