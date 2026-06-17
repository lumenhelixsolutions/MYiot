# M7 — Auth & Security Design

## Goal
Add a single-admin login layer to the MyIoT hub, protect all sensitive REST, WebSocket, and camera endpoints, harden network settings, and keep the existing manufacturer credential vault secure.

## Context
- The backend is FastAPI + SQLAlchemy 2.0 async/aiosqlite.
- The frontend is React + Vite + Tailwind CSS; `node_modules` is currently incomplete and cannot be installed.
- `hub/auth/manager.py` already encrypts manufacturer credentials with Fernet; it does not implement user sessions.
- `hub/models/database.py` has no `User` table.
- `hub/main.py` CORS allows only the Vite dev origin; no HTTPS, trusted hosts, rate limits, or security headers are configured.
- Camera snapshot/MJPEG and WebSocket endpoints are currently unauthenticated.

## Decisions
- **Scope:** user login sessions + backend/network hardening.
- **Deployment:** local network only.
- **Users:** single pre-seeded admin account.
- **Session transport:** JWT inside an HTTP-only, Secure, SameSite=Lax cookie.
- **Protected endpoints:** all device, stream, log, WebSocket, and camera routes; public only `/health`, `/api/auth/login`, `/api/auth/logout`.
- **Password management:** change-password UI in Settings, requiring the current password.
- **Implementation approach:** JWT in HTTP-only cookies using `python-jose` and `passlib[bcrypt]`.

## Architecture

### Backend

#### New modules
- `hub/auth/session.py`
  - `hash_password(plain: str) -> str`
  - `verify_password(plain: str, hash: str) -> bool`
  - `create_access_token(username: str) -> str`
  - `decode_access_token(token: str) -> dict`
  - `require_auth(request: Request) -> AuthenticatedUser` FastAPI dependency
  - Cookie helper functions: `set_auth_cookie(response, token)` and `clear_auth_cookie(response)`
- `hub/auth/config.py`
  - Load `SECRET_KEY` from env or generate a one-time random key and warn.
  - Load `ACCESS_TOKEN_EXPIRE_MINUTES`, `FRONTEND_ORIGINS`, `SSL_CERTFILE`, `SSL_KEYFILE`.

#### Database
- Add `User` model in `hub/models/database.py`:
  - `username` (PK, str)
  - `password_hash` (str)
  - `role` (str, default `"admin"`)
  - `created_at` (float)
  - `updated_at` (float)
- Add migration in `_migrate_db` to create the `users` table and add columns if missing.
- Seed the admin user on startup if none exists, using `ADMIN_USERNAME`/`ADMIN_PASSWORD` env vars (default `admin` / random generated password logged once).

#### Endpoints
- `POST /api/auth/login` — validate credentials, set auth cookie, return `{ success: true }`.
- `POST /api/auth/logout` — clear auth cookie.
- `POST /api/auth/change-password` — requires current password, updates hash, logs event.
- `GET /api/auth/manufacturers` — list manufacturers with stored credentials.
- `DELETE /api/auth/{manufacturer}` — delete stored credentials.
- Apply `require_auth` dependency to existing protected routers.

#### WebSocket auth
- Frontend opens `wss://host/ws?token=<jwt>` because browser WebSocket API cannot send cookies.
- `hub/api/websocket.py` validates the `token` query parameter during the handshake.
- Reject missing/invalid tokens with code `1008`.

#### Network hardening
- CORS: read allowed origins from `FRONTEND_ORIGINS`; keep dev defaults. `allow_credentials=True`.
- Add `TrustedHostMiddleware` with allowed hosts from `ALLOWED_HOSTS`.
- Add in-memory rate limiter for `/api/auth/login` (5 attempts per minute per IP).
- Add security-headers middleware: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Strict-Transport-Security` when HTTPS is active.
- HTTPS: if `SSL_CERTFILE` and `SSL_KEYFILE` are set, pass them to uvicorn; otherwise generate a self-signed cert on first startup, save to `data/`, and log the SHA-256 fingerprint.
- Hide server version banner (`server_header=False` in uvicorn or middleware override).

#### Audit logging
- Log events: `login_success`, `login_failure`, `logout`, `password_change`, `auth_denied`.
- Include `ip_address` in login-related events.

### Frontend

- `app/src/context/AuthContext.tsx`
  - Track `user: { username, role } | null`.
  - `login(username, password)` → `POST /api/auth/login` with credentials.
  - `logout()` → `POST /api/auth/logout`.
  - `checkSession()` → call a new `GET /api/auth/me` on mount.
- `app/src/pages/Login.tsx`
  - Simple form; on success redirect to dashboard.
- Update `app/src/App.tsx`
  - Render `<Login />` when unauthenticated, otherwise the existing dashboard.
- Update API client (`api.ts`)
  - Ensure all requests use `credentials: "include"`.
- Update Settings page
  - Replace local manufacturer credential state with calls to `/api/auth/{manufacturer}` and `/api/auth/manufacturers`.
  - Add change-password form.

### Manufacturer Credential Vault
- Keep `AuthenticationManager` unchanged except for adding `list_manufacturers()` (already exists) and `delete()` (already exists) endpoints in the API.
- Verify key file (`data/.key`) permissions remain `0o600`.

## Error Handling
- Invalid login: return `401` with generic message, log failure with IP.
- Missing/invalid token on protected route: return `401`.
- Expired token: return `401`; frontend redirects to login.
- Rate-limited login: return `429`.
- WebSocket auth failure: close with `1008`.

## Testing
- Backend:
  - Password hash round-trip.
  - JWT encode/decode and expiry.
  - `POST /api/auth/login` success and failure.
  - `POST /api/auth/logout` clears cookie.
  - `POST /api/auth/change-password` rejects wrong current password.
  - Protected route returns `401` without cookie, `200` with valid cookie.
  - WebSocket rejects connection without token, accepts with valid token.
  - Rate limiter blocks repeated login attempts.
  - Manufacturer credential store/delete endpoints.
- Frontend:
  - Login form validation.
  - AuthContext state transitions.
  - Settings calls manufacturer credential endpoints.

## Dependencies
- Add to `hub/requirements.txt`:
  - `python-jose[cryptography]>=3.3.0`
  - `passlib[bcrypt]>=1.7.4`

## Out of Scope
- Multi-user roles beyond a single admin.
- OAuth / SSO.
- Public internet deployment / Let's Encrypt automation (docs only).
- Full frontend build verification (blocked by broken `npm install`).

## Open Questions
- None remaining; design approved.
