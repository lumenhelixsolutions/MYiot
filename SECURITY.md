# Security Policy

> **MYiot** — Security is at the core of our architecture. We believe your smart home data belongs to you, and only you.
>
> ![#6366F1](https://via.placeholder.com/12/6366F1/6366F1.png) **Local-First** | ![#06B6D4](https://via.placeholder.com/12/06B6D4/06B6D4.png) **E2E Encrypted** | ![#F59E0B](https://via.placeholder.com/12/F59E0B/F59E0B.png) **Zero Cloud Dependency**

---

## Supported Versions

We actively maintain and provide security updates for the following versions:

| Version | Status | Release Date | Security Support Until |
|---------|--------|-------------|----------------------|
| 1.0.x | ✅ Active | 2025-01-15 | 2026-01-15 |
| 0.9.x | ⚠️ Maintenance | 2024-10-01 | 2025-04-01 |
| < 0.9 | ❌ End of Life | — | Not supported |

> We follow [Semantic Versioning](https://semver.org/). Security patches are released as patch versions (e.g., `1.0.1`).

---

## Security Features

MYiot is designed with a **security-first, privacy-by-design** philosophy:

### 🔒 Local-First Architecture

- All data processing happens on your local hardware
- No cloud services required for core functionality
- Works entirely on your local network without internet access
- Optional remote access via your own infrastructure (VPN, reverse proxy)

### 🔐 End-to-End Encryption

- **Transport Layer**: TLS 1.3 for all HTTP and WebSocket connections
- **MQTT**: TLS encryption between MYiot and the MQTT broker
- **Camera Streams**: SRTP/RTSPS for encrypted video streams
- **Database**: AES-256 encryption for sensitive configuration at rest

### 🛡️ Authentication & Authorization

- JWT-based authentication with configurable expiry
- Role-based access control (RBAC) — Admin, User, Guest roles
- API token support for third-party integrations
- Brute-force protection with rate limiting
- Session management with revocation support

### 🏠 Network Security

- Runs on your local network — not exposed to the public internet by default
- Traefik reverse proxy with automatic HTTPS via Let's Encrypt
- CORS protection configured for your domain only
- Network segmentation support (separate IoT VLAN)

### 📹 Camera Privacy

- All video processing happens locally via Frigate NVR
- No footage uploaded to cloud services
- Configurable retention and automatic deletion
- Motion detection runs on-device (Coral TPU support)

---

## Reporting a Vulnerability

We take security vulnerabilities seriously. If you discover a security issue, please report it **privately** so we can address it before public disclosure.

### How to Report

📧 **Email**: [security@myiot.dev](mailto:security@myiot.dev)

🔐 **GPG Key**: [security@myiot.dev.pub](https://myiot.dev/security@myiot.dev.pub)

Please include the following details:

1. **Description** — Clear description of the vulnerability
2. **Impact** — What could an attacker achieve?
3. **Reproduction** — Step-by-step instructions to reproduce
4. **Affected versions** — Which MYiot versions are affected?
5. **Mitigation** — Any workarounds you've identified
6. **Your contact** — How to reach you for follow-up (optional)

### What to Expect

| Timeline | Action |
|----------|--------|
| **Within 48 hours** | Acknowledgment of your report |
| **Within 7 days** | Initial assessment and severity classification |
| **Within 30 days** | Fix developed and tested (critical: 14 days) |
| **Upon release** | Public disclosure with credit (if desired) |

### Our Commitments

- We will **never take legal action** against researchers who report vulnerabilities in good faith
- We will **credit you** in the security advisory (unless you prefer anonymity)
- We will **keep you informed** throughout the remediation process
- We follow **responsible disclosure** — we coordinate with you before public disclosure

### Scope

The following are **in scope** for vulnerability reports:

- MYiot backend (FastAPI application)
- MYiot frontend (React application)
- MYiot WebSocket server
- MYiot device drivers and integrations
- Docker/Compose deployment configurations
- Official documentation

The following are **out of scope**:

- Third-party dependencies (report to upstream projects)
- Frigate NVR (report to [blakeblackshear/frigate](https://github.com/blakeblackshear/frigate))
- Zigbee2MQTT (report to [Koenkk/zigbee2mqtt](https://github.com/Koenkk/zigbee2mqtt))
- Infrastructure you operate (your reverse proxy, VPN, etc.)
- Issues requiring physical device access to your hardware

---

## Security Advisories

Published security advisories are available on our [GitHub Security Advisories](https://github.com/myiot/myiot/security/advisories) page and are also announced via:

- GitHub release notifications
- Discord #security-announcements channel
- Security mailing list (subscribe at [security@myiot.dev](mailto:security@myiot.dev))

---

## Security Hardening Guide

### Recommended Production Setup

```yaml
# docker-compose.prod.yml security checklist

# 1. Use strong secrets
SECRET_KEY=$(openssl rand -hex 32)
ENCRYPTION_KEY=$(openssl rand -hex 32)
MQTT_PASS=$(openssl rand -hex 16)

# 2. Enable HTTPS only
ENABLE_HTTPS=true

# 3. Restrict CORS to your domain
CORS_ORIGINS=https://myiot.yourdomain.com

# 4. Use PostgreSQL instead of SQLite
DATABASE_URL=postgresql+asyncpg://myiot:strong_password@postgres:5432/myiot

# 5. Enable MQTT authentication
MQTT_TLS_ENABLED=true

# 6. Keep containers updated
# Enable Watchtower in docker-compose.prod.yml
```

### Network Segmentation

We recommend placing IoT devices on a separate VLAN:

```
┌─────────────────────────────────────────────┐
│                  Router                     │
│  ┌─────────────┐      ┌──────────────────┐  │
│  │  Main LAN   │      │    IoT VLAN      │  │
│  │  192.168.1  │      │   192.168.100    │  │
│  │             │      │                  │  │
│  │  [MYiot]    │      │ [Cameras]        │  │
│  │  [Users]    │◄────►│ [Sensors]        │  │
│  │  [Phones]   │      │ [Smart Plugs]    │  │
│  └─────────────┘      └──────────────────┘  │
└─────────────────────────────────────────────┘
```

---

## Acknowledgments

We thank the following security researchers who have responsibly disclosed vulnerabilities:

| Researcher | Date | Advisory |
|-----------|------|----------|
| *Waiting for first report* | — | — |

*Want your name here? See [Reporting a Vulnerability](#reporting-a-vulnerability) above.*

---

## Contact

For security-related inquiries:

- 📧 Email: [security@myiot.dev](mailto:security@myiot.dev)
- 🔐 GPG Fingerprint: `A1B2 C3D4 E5F6 7890 1234  5678 90AB CDEF 1234 5678`
- 💬 Discord: DM @security-team (for urgent issues)

*Last updated: 2025-01-15*
