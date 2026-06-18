# MYiot Deployment Guide

> **MYiot** — Universal Smart Home Hub
> Complete deployment guide for Docker, Kubernetes, Raspberry Pi, and more.
>
> **Brand Colors:** `#081021` (Deep Space Slate) | `#6366F1` (Electric Indigo) | `#06B6D4` (Cyan Glow) | `#F59E0B` (Warm Amber)

---

## Table of Contents

- [Quick Start](#quick-start)
- [Docker Deployment](#docker-deployment)
- [Kubernetes Deployment](#kubernetes-deployment)
- [Raspberry Pi Deployment](#raspberry-pi-deployment)
- [Environment Configuration](#environment-configuration)
- [SSL/TLS Setup](#ssltls-setup)
- [Reverse Proxy Configuration](#reverse-proxy-configuration)
- [Backup and Restore](#backup-and-restore)
- [Monitoring and Logging](#monitoring-and-logging)
- [Troubleshooting](#troubleshooting)

---

## Quick Start

The fastest way to get MYiot running:

```bash
# 1. Download compose file
curl -o docker-compose.yml https://raw.githubusercontent.com/myiot/myiot/main/docker-compose.yml

# 2. Create environment file
cp .env.example .env
# Edit .env with your settings

# 3. Start MYiot
docker compose up -d

# 4. Access the dashboard
# http://localhost:8080
```

---

## Docker Deployment

### Prerequisites

- Docker Engine >= 24.0
- Docker Compose >= 2.20
- At least 2GB RAM available
- 10GB free disk space

### Standard Deployment

```bash
# Clone the repository
git clone https://github.com/myiot/myiot.git
cd myiot

# Create and configure environment
cp .env.example .env
nano .env  # Edit to your needs

# Build and start services
docker compose up -d --build

# View logs
docker compose logs -f

# Check status
docker compose ps
```

### Services Overview

| Service | Container Name | Port | Purpose |
|---------|---------------|------|---------|
| Frontend | `myiot-frontend` | 8080 | Nginx serving React SPA |
| Backend | `myiot-backend` | 8000 | FastAPI + Uvicorn |
| MQTT Broker | `myiot-mqtt` | 1883, 9001 | Mosquitto MQTT |
| Redis | `myiot-redis` | 6379 | Cache & pub/sub |

### Production Deployment

For production with Traefik, SSL, and monitoring:

```bash
# Start with production overrides
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Or use the Makefile
make deploy-prod
```

The production setup includes:

| Addition | Description |
|----------|-------------|
| **Traefik** | Reverse proxy with automatic HTTPS |
| **Let's Encrypt** | Free SSL certificates |
| **Rate Limiting** | 100 req/min per IP |
| **Compression** | Gzip/Brotli response compression |
| **Security Headers** | HSTS, CSP, X-Frame-Options |
| **Watchtower** | Automatic container updates |

### Updating

```bash
# Pull latest images
docker compose pull

# Restart with new images
docker compose up -d

# Or rebuild from source
docker compose up -d --build
```

### Docker Environment Variables

Required variables for Docker deployment:

| Variable | Default | Description |
|----------|---------|-------------|
| `COMPOSE_PROJECT_NAME` | `myiot` | Docker Compose project name |
| `FRONTEND_PORT` | `8080` | Host port for frontend |
| `BACKEND_PORT` | `8000` | Host port for backend |
| `MQTT_PORT` | `1883` | Host port for MQTT |
| `SECRET_KEY` | *(required)* | JWT signing key |
| `DATABASE_URL` | `sqlite+aiosqlite...` | Database connection |
| `REDIS_URL` | `redis://myiot-redis:6379/0` | Redis connection |

---

## Kubernetes Deployment

### Prerequisites

- Kubernetes >= 1.28
- kubectl configured
- Helm 3 (optional but recommended)

### Using kubectl

Apply the manifests from the `k8s/` directory:

```bash
# Create namespace
kubectl create namespace myiot

# Create secrets
kubectl create secret generic myiot-secrets \
  --namespace myiot \
  --from-literal=secret-key="$(openssl rand -hex 32)" \
  --from-literal=mqtt-password="$(openssl rand -hex 16)" \
  --from-literal=encryption-key="$(openssl rand -hex 32)"

# Deploy
kubectl apply -k k8s/overlays/production/

# Check status
kubectl get pods -n myiot
kubectl get svc -n myiot
```

### Using Helm

```bash
# Add MYiot Helm repository
helm repo add myiot https://charts.myiot.dev
helm repo update

# Install with default values
helm install myiot myiot/myiot \
  --namespace myiot \
  --create-namespace

# Install with custom values
helm install myiot myiot/myiot \
  --namespace myiot \
  --values values-production.yaml

# Upgrade
helm upgrade myiot myiot/myiot \
  --namespace myiot \
  --values values-production.yaml
```

### Example `values-production.yaml`

```yaml
# values-production.yaml
replicaCount:
  frontend: 2
  backend: 2

image:
  repository: ghcr.io/myiot/myiot
  tag: "1.0.0"
  pullPolicy: IfNotPresent

ingress:
  enabled: true
  className: traefik
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
    traefik.ingress.kubernetes.io/router.middlewares: "default-https-redirect@kubernetescrd"
  hosts:
    - host: myiot.yourdomain.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: myiot-tls
      hosts:
        - myiot.yourdomain.com

resources:
  frontend:
    requests:
      memory: "64Mi"
      cpu: "100m"
    limits:
      memory: "256Mi"
      cpu: "500m"
  backend:
    requests:
      memory: "128Mi"
      cpu: "250m"
    limits:
      memory: "512Mi"
      cpu: "1000m"

persistence:
  enabled: true
  storageClass: "longhorn"
  size: 10Gi

redis:
  enabled: true
  architecture: standalone
  auth:
    enabled: true
    existingSecret: myiot-secrets
    existingSecretPasswordKey: redis-password

mqtt:
  enabled: true
  persistence:
    enabled: true
    size: 5Gi
```

### Kubernetes Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Kubernetes Cluster                      │
│                                                              │
│  ┌──────────────┐    ┌──────────────────────────────────┐  │
│  │   Ingress    │───►│          Traefik                 │  │
│  │ myiot.local  │    │  (SSL termination, routing)      │  │
│  └──────────────┘    └──────────────┬───────────────────┘  │
│                                     │                        │
│                    ┌────────────────┼────────────────┐       │
│                    ▼                ▼                ▼       │
│              ┌──────────┐    ┌──────────┐    ┌──────────┐  │
│              │Frontend  │    │Backend   │    │Backend   │  │
│              │Pod 1     │    │Pod 1     │    │Pod 2     │  │
│              └──────────┘    └────┬─────┘    └──────────┘  │
│                                   │                         │
│                         ┌─────────┼─────────┐               │
│                         ▼         ▼         ▼               │
│                    ┌────────┐ ┌────────┐ ┌────────┐        │
│                    │Redis   │ │PostgreSQL│ │MQTT    │        │
│                    │Service │ │Service   │ │Service │        │
│                    └────────┘ └────────┘ └────────┘        │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Persistent Volumes:                                 │   │
│  │    - myiot-data (10Gi)  — SQLite, recordings       │   │
│  │    - postgres-data (10Gi) — PostgreSQL data        │   │
│  │    - mqtt-data (5Gi)    — MQTT persistence         │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## Raspberry Pi Deployment

MYiot runs excellently on Raspberry Pi 4 and 5. Raspberry Pi 3 is supported but may have limited performance with multiple cameras.

### Hardware Requirements

| Model | RAM | Storage | Cameras | Performance |
|-------|-----|---------|---------|-------------|
| Raspberry Pi 5 | 4GB+ | SSD recommended | 4+ | Excellent |
| Raspberry Pi 4 | 4GB+ | SSD recommended | 2-4 | Good |
| Raspberry Pi 3B+ | 1GB | MicroSD | 1-2 | Limited |

### Raspberry Pi OS Setup

```bash
# 1. Install Raspberry Pi OS (64-bit) Lite
# https://www.raspberrypi.com/software/

# 2. Update system
sudo apt update && sudo apt upgrade -y

# 3. Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker

# 4. Enable USB device access (for Zigbee/Z-Wave dongles)
sudo usermod -aG dialout $USER

# 5. Optimize for IoT workload
# /boot/firmware/config.txt additions:
echo "dtoverlay=disable-bt" | sudo tee -a /boot/firmware/config.txt  # Optional: disable Bluetooth

# 6. Reduce GPU memory (headless)
echo "gpu_mem=16" | sudo tee -a /boot/firmware/config.txt

# 7. Reboot
sudo reboot
```

### Raspberry Pi Docker Compose

Use a compose file optimized for ARM:

```yaml
# docker-compose.rpi.yml
version: "3.9"

services:
  myiot-frontend:
    image: ghcr.io/myiot/myiot:latest
    platform: linux/arm64  # or linux/arm/v7 for Pi 3
    ports:
      - "8080:80"
    environment:
      - VITE_API_URL=http://raspberrypi.local:8000

  myiot-backend:
    image: ghcr.io/myiot/myiot:latest
    platform: linux/arm64
    ports:
      - "8000:8000"
    environment:
      - SECRET_KEY=${SECRET_KEY}
      - DATABASE_URL=sqlite+aiosqlite:///./data/myiot.db
      - MQTT_HOST=myiot-mqtt
      - MQTT_PORT=1883
    volumes:
      - ./data:/app/data
    devices:
      - /dev/ttyUSB0:/dev/ttyUSB0  # Zigbee dongle

  myiot-mqtt:
    image: eclipse-mosquitto:2
    ports:
      - "1883:1883"
    volumes:
      - ./mosquitto.conf:/mosquitto/config/mosquitto.conf:ro
      - mqtt-data:/mosquitto/data

  myiot-redis:
    image: redis:7-alpine
    platform: linux/arm64
    volumes:
      - redis-data:/data

  # Frigate with USB Coral TPU
  myiot-frigate:
    image: ghcr.io/blakeblackshear/frigate:stable
    privileged: true
    ports:
      - "5000:5000"
    volumes:
      - ./frigate.yml:/config/config.yml:ro
      - frigate-data:/media/frigate
    devices:
      - /dev/bus/usb:/dev/bus/usb  # USB Coral TPU
      # - /dev/dri:/dev/dri        # Intel GPU (if using Intel NUC)

volumes:
  mqtt-data:
  redis-data:
  frigate-data:
```

### Start on Raspberry Pi

```bash
# Start all services
docker compose -f docker-compose.yml -f docker-compose.rpi.yml up -d

# View logs
docker compose logs -f myiot-backend

# Check resource usage
docker stats
```

### Performance Tips for Raspberry Pi

1. **Use SSD instead of MicroSD** — Significantly better I/O performance
2. **Limit camera streams** — Set `CAMERA_MAX_STREAMS=2` on Pi 4, `1` on Pi 3
3. **Lower stream resolution** — Use sub-streams (640x480) for live view
4. **Enable Frigate hardware acceleration** — Use Coral TPU or Pi GPU
5. **Disable unused protocols** — Only enable Zigbee or Z-Wave, not both if not needed

---

## Environment Configuration

### Configuration Priority

Configuration is loaded in the following priority (highest first):

1. Environment variables
2. `.env` file
3. `docker-compose.yml` environment section
4. Default values in code

### Required Variables

```bash
# === SECURITY ===
# Generate strong secrets:
#   openssl rand -hex 32
SECRET_KEY=your-256-bit-secret-key-here
ENCRYPTION_KEY=your-256-bit-encryption-key-here

# === DATABASE ===
# For single-node: SQLite (default)
DATABASE_URL=sqlite+aiosqlite:///./data/myiot.db

# For multi-node or production: PostgreSQL
# DATABASE_URL=postgresql+asyncpg://myiot:password@postgres:5432/myiot

# === MQTT ===
MQTT_HOST=myiot-mqtt
MQTT_PORT=1883
MQTT_USER=myiot
MQTT_PASS=your-mqtt-password

# === FRIGATE (optional) ===
FRIGATE_URL=http://myiot-frigate:5000
FRIGATE_API_KEY=your-frigate-api-key
```

### Environment-Specific Profiles

| Environment | Database | Debug | SSL | Frigate |
|-------------|----------|-------|-----|---------|
| Development | SQLite | Enabled | No | Optional |
| Staging | PostgreSQL | Disabled | Yes (self-signed) | Yes |
| Production | PostgreSQL | Disabled | Yes (Let's Encrypt) | Yes |
| Raspberry Pi | SQLite | Disabled | Yes (Let's Encrypt) | Optional |

---

## SSL/TLS Setup

### Automatic SSL (Recommended) — Let's Encrypt

The production compose file includes Traefik with automatic Let's Encrypt:

```yaml
# docker-compose.prod.yml
traefik:
  command:
    - --certificatesresolvers.letsencrypt.acme.tlschallenge=true
    - --certificatesresolvers.letsencrypt.acme.email=admin@yourdomain.com
    - --certificatesresolvers.letsencrypt.acme.storage=/etc/traefik/certs/acme.json
```

Requirements:
- Public domain pointing to your server
- Ports 80 and 443 open to the internet

### Using Existing Certificates

```yaml
traefik:
  volumes:
    - ./certs/cert.pem:/etc/traefik/certs/cert.pem:ro
    - ./certs/key.pem:/etc/traefik/certs/key.pem:ro
```

### Self-Signed Certificates (Local/LAN only)

```bash
# Generate self-signed certificate
mkdir -p certs
openssl req -x509 -newkey rsa:4096 \
  -keyout certs/key.pem \
  -out certs/cert.pem \
  -days 365 -nodes \
  -subj "/CN=myiot.local"

# Mount into Traefik
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Cloudflare Origin Certificates

```bash
# Download Cloudflare origin certificate and key
# Place in ./certs/cloudflare-cert.pem and ./certs/cloudflare-key.pem

# docker-compose.prod.yml
traefik:
  command:
    - --certificatesresolvers.cloudflare.acme.dnschallenge=true
    - --certificatesresolvers.cloudflare.acme.dnschallenge.provider=cloudflare
  environment:
    - CF_API_EMAIL=${CF_API_EMAIL}
    - CF_API_KEY=${CF_API_KEY}
```

---

## Reverse Proxy Configuration

### Traefik (Included)

Traefik is included in the production compose file. No additional configuration needed.

### Nginx

If you prefer Nginx as the reverse proxy:

```nginx
# /etc/nginx/sites-available/myiot
server {
    listen 80;
    server_name myiot.yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name myiot.yourdomain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # Frontend (React SPA)
    location / {
        proxy_pass http://localhost:8080;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Backend API
    location /api/ {
        proxy_pass http://localhost:8000/api/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket
    location /ws/ {
        proxy_pass http://localhost:8000/ws/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400;
    }
}
```

### Apache

```apache
# /etc/apache2/sites-available/myiot.conf
<VirtualHost *:80>
    ServerName myiot.yourdomain.com
    Redirect permanent / https://myiot.yourdomain.com/
</VirtualHost>

<VirtualHost *:443>
    ServerName myiot.yourdomain.com

    SSLEngine on
    SSLCertificateFile /path/to/cert.pem
    SSLCertificateKeyFile /path/to/key.pem

    # Frontend
    ProxyPass / http://localhost:8080/
    ProxyPassReverse / http://localhost:8080/

    # Backend API
    ProxyPass /api/ http://localhost:8000/api/
    ProxyPassReverse /api/ http://localhost:8000/api/

    # WebSocket
    RewriteEngine on
    RewriteCond %{HTTP:Upgrade} websocket [NC]
    RewriteRule ^/ws/(.*) "ws://localhost:8000/ws/$1" [P,L]
    ProxyPass /ws/ http://localhost:8000/ws/
    ProxyPassReverse /ws/ http://localhost:8000/ws/

    ProxyPreserveHost On
    ProxyRequests Off
</VirtualHost>
```

### Cloudflare Tunnel (No port forwarding)

For users who cannot open ports:

```bash
# Install cloudflared
wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -O /usr/local/bin/cloudflared
chmod +x /usr/local/bin/cloudflared

# Authenticate and create tunnel
cloudflared tunnel login
cloudflared tunnel create myiot

# Configure tunnel
cat > ~/.cloudflared/config.yml <<EOF
tunnel: <TUNNEL_ID>
credentials-file: /root/.cloudflared/<TUNNEL_ID>.json

ingress:
  - hostname: myiot.yourdomain.com
    service: http://localhost:8080
  - service: http_status:404
EOF

# Run tunnel
cloudflared tunnel route dns myiot myiot.yourdomain.com
cloudflared tunnel run myiot
```

---

## Backup and Restore

### Automated Backups

```bash
#!/bin/bash
# backup-myiot.sh — Run via cron daily

BACKUP_DIR="/backups/myiot"
DATE=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=30

mkdir -p "$BACKUP_DIR"

# Backup SQLite database
docker compose cp myiot-backend:/app/data/myiot.db "$BACKUP_DIR/myiot_$DATE.db"

# Backup configuration
tar czf "$BACKUP_DIR/config_$DATE.tar.gz" .env docker-compose.yml docker/

# Backup Redis
redis-cli SAVE
docker compose cp myiot-redis:/data/dump.rdb "$BACKUP_DIR/redis_$DATE.rdb"

# Sync to remote (optional)
# rclone sync "$BACKUP_DIR" remote:myiot-backups

# Clean old backups
find "$BACKUP_DIR" -name "*.db" -mtime +$RETENTION_DAYS -delete
find "$BACKUP_DIR" -name "*.tar.gz" -mtime +$RETENTION_DAYS -delete

echo "Backup completed: $BACKUP_DIR"
```

Add to crontab:

```bash
# Daily at 3 AM
0 3 * * * /path/to/backup-myiot.sh >> /var/log/myiot-backup.log 2>&1
```

### Manual Backup

```bash
# Create backup directory
mkdir -p ./backups/$(date +%Y%m%d)

# Stop services
docker compose stop myiot-backend

# Copy database
docker compose cp myiot-backend:/app/data/myiot.db ./backups/$(date +%Y%m%d)/

# Copy config
cp .env ./backups/$(date +%Y%m%d)/
cp docker-compose.yml ./backups/$(date +%Y%m%d)/

# Restart
docker compose start myiot-backend
```

### Restore from Backup

```bash
# Stop services
docker compose down

# Restore database
cp ./backups/20250115/myiot.db ./data/myiot.db

# Restore config
cp ./backups/20250115/.env ./.env

# Start services
docker compose up -d
```

### PostgreSQL Backup/Restore

```bash
# Backup
docker compose exec myiot-postgres pg_dump -U myiot myiot > backup.sql

# Restore
docker compose exec -T myiot-postgres psql -U myiot myiot < backup.sql
```

---

## Monitoring and Logging

### Built-in Health Check

```bash
# System health
curl http://localhost:8000/api/v1/system/health

# Detailed info (authenticated)
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/system/info
```

### Docker Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f myiot-backend

# Last 100 lines
docker compose logs --tail=100 myiot-backend
```

### Prometheus Metrics

Enable Prometheus metrics by setting `PROMETHEUS_ENABLED=true`:

```yaml
# docker-compose.yml (additional service)
  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus-data:/prometheus
    ports:
      - "9090:9090"

  grafana:
    image: grafana/grafana:latest
    volumes:
      - grafana-data:/var/lib/grafana
      - ./grafana/dashboards:/etc/grafana/provisioning/dashboards:ro
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_ADMIN_PASSWORD}
```

### Key Metrics

| Metric | Description | Endpoint |
|--------|-------------|----------|
| `myiot_devices_total` | Total number of devices | Prometheus |
| `myiot_devices_online` | Online device count | Prometheus |
| `myiot_api_requests_total` | API request counter | Prometheus |
| `myiot_ws_connections` | Active WebSocket connections | Prometheus |
| `myiot_camera_events_total` | Camera event counter | Prometheus |

### Uptime Kuma (Optional Monitoring)

```yaml
  uptime-kuma:
    image: louislam/uptime-kuma:1
    volumes:
      - uptime-kuma-data:/app/data
    ports:
      - "3001:3001"
```

---

## Troubleshooting

### Common Issues

#### Services won't start

```bash
# Check for port conflicts
sudo lsof -i :8080
sudo lsof -i :8000
sudo lsof -i :1883

# Check logs
docker compose logs --tail=50 myiot-backend

# Verify environment
docker compose config
```

#### Database is locked (SQLite)

SQLite doesn't support multiple concurrent writers well. Solutions:

1. Switch to PostgreSQL for multi-instance setups
2. Ensure only one backend instance is running
3. Check for stale lock files: `rm data/*.db-journal data/*.db-wal data/*.db-shm`

#### WebSocket connection fails

```bash
# Check if backend is healthy
curl http://localhost:8000/api/v1/system/health

# Check firewall rules
sudo ufw status
sudo iptables -L -n | grep 8000

# Check browser console for CORS errors
# Ensure CORS_ORIGINS includes your frontend URL
```

#### MQTT not receiving messages

```bash
# Test MQTT connection
mosquitto_sub -h localhost -t "zigbee2mqtt/#" -v

# Check MQTT logs
docker compose logs myiot-mqtt

# Verify backend MQTT config
docker compose exec myiot-backend env | grep MQTT
```

#### Camera streams not loading

```bash
# Test RTSP stream
ffplay rtsp://camera-ip:554/stream1

# Check Frigate logs
docker compose logs myiot-frigate

# Verify camera configuration
curl http://localhost:8000/api/v1/cameras
```

### Getting Help

- **Documentation:** https://docs.myiot.dev
- **GitHub Issues:** https://github.com/myiot/myiot/issues
- **Discord:** https://discord.gg/myiot
- **Logs:** `docker compose logs -f`

---

*Last updated: 2025-01-15*
