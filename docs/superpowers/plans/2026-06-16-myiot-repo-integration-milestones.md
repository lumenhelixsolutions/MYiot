# MYiot New Repo Integration — 5-Step Milestone Plan

## Context

A new reference repository has been placed at `/d/projects/myiot/myiot-repo/`. It contains a complete, production-ready GitHub package: viral README, docs suite, GitHub templates, CI/CD, Docker setup, Makefile, and supporting legal/community files.

The current working project (`/d/projects/myiot/`) contains the real source code (`app/`, `hub/`, `SPEC.md`, `plan-backend-integration.md`) plus the WebRTC work committed earlier. The two directories have **different structures and assumptions** that must be reconciled before the new repo assets can be adopted.

## Key Findings

### What the new repo adds

| Area | Files | Notes |
|------|-------|-------|
| README | `README.md` | 797-line viral README with NODI mascot, Sora type, animated badges |
| Legal / Community | `LICENSE`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `CHANGELOG.md` | `LICENSE` is MIT, conflicting with user's CC BY-NC request |
| GitHub | `.github/FUNDING.yml`, issue/PR templates, `workflows/ci.yml`, `workflows/release.yml` | Assumes `frontend/` and `backend/` dirs |
| Docs | `docs/API.md`, `ARCHITECTURE.md`, `DEPLOYMENT.md`, `DRIVERS.md`, `brand-kit.png` | API docs describe v1 endpoints and Frigate integration not yet implemented |
| DevEx | `Makefile`, `scripts/setup.sh`, `.env.example` | Makefile assumes `frontend/` and `backend/` |
| Containers | `Dockerfile`, `docker-compose.yml`, `docker-compose.prod.yml` | Multi-stage build with Nginx; references `docker/nginx.conf` and `docker/entrypoint.sh` not present |

### Structural mismatches

| New repo assumes | Current project uses |
|------------------|----------------------|
| `frontend/` directory | `app/` directory |
| `backend/` directory | `hub/` directory |
| `app/main:app` entry point | `hub/main:app` entry point |
| `backend/pyproject.toml` | `hub/pyproject.toml` |
| Redis, MQTT, Frigate, Zigbee, PostgreSQL optional | SQLite + in-memory registry + go2rtc |
| MIT License | User requested CC BY-NC + commercial clause |

### Aspirational vs implemented features

The new README and docs describe features not yet in the codebase:

- 17+ brands (current: 15 manufacturers mapped, fewer fully implemented)
- Frigate NVR AI detection
- Zigbee / Z-Wave / Thread support
- Redis, MQTT broker, PostgreSQL option
- Mobile app / PWA
- Traefik reverse proxy

These must be either implemented, scoped out, or clearly labeled as roadmap items.

---

## Milestone 1: Foundation — Import Legal, Community, and Repo Metadata

**Goal:** Establish the non-code repository infrastructure on top of the current project.

**Tasks:**

1. Replace current `LICENSE` with the user's requested **CC BY-NC 4.0 + commercial-permission clause** (do not blindly copy the MIT file from `myiot-repo`).
2. Add `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, and `CHANGELOG.md` from `myiot-repo`, editing references from `frontend/backend` to `app/hub`.
3. Add `.github/FUNDING.yml`, issue templates, and PR template.
4. Merge `.gitignore` rules from `myiot-repo` into the current root `.gitignore`.
5. Add `.env.example` at project root, editing paths and variables to match `app/` and `hub/`.
6. Commit as `chore: add legal, community, and GitHub repo metadata`.

**Verification:**

- [ ] `LICENSE` reads CC BY-NC 4.0 with commercial clause.
- [ ] All `.github/` files render correctly in the repo UI.
- [ ] `.gitignore` ignores `.venv`, `node_modules`, caches, secrets, and build artifacts.

---

## Milestone 2: Documentation — Adopt and Align the Docs Suite

**Goal:** Import the new docs and align them with the actual codebase.

**Tasks:**

1. Create `docs/` directory and import:
   - `docs/API.md`
   - `docs/ARCHITECTURE.md`
   - `docs/DEPLOYMENT.md`
   - `docs/DRIVERS.md`
   - `docs/brand-kit.png`
2. Update all internal references from `frontend/` → `app/` and `backend/` → `hub/`.
3. Audit API docs against actual `hub/api/routes.py` endpoints. Mark aspirational endpoints (rooms, automations, Frigate) as **"Roadmap"** or remove them.
4. Update architecture diagrams to reflect the actual stack: FastAPI + React + SQLite + go2rtc.
5. Move or merge existing `SPEC.md` and `plan-backend-integration.md` content into `docs/` if appropriate, or keep them at root and cross-link.
6. Commit as `docs: add aligned API, architecture, deployment, and driver docs`.

**Verification:**

- [ ] All docs open without broken internal links.
- [ ] API endpoints documented match `hub/api/routes.py`.
- [ ] Architecture docs match current `hub/main.py` lifespan and `app/src` structure.

---

## Milestone 3: README — Merge Viral README with Current Reality

**Goal:** Replace/upgrade `README.md` to the award-winning version while keeping it accurate.

**Tasks:**

1. Import `myiot-repo/README.md` as the new `README.md`.
2. Replace all `frontend/` references with `app/` and `backend/` with `hub/`.
3. Update quickstart commands to match current project:
   ```bash
   cd hub && python -m uvicorn main:app --reload --port 8000
   cd app && npm run dev
   ```
4. Replace the one-liner `curl ... | bash` with a safe `git clone` path.
5. Reduce or clearly label aspirational feature claims:
   - Change "17+ Brands" to the number actually supported.
   - Move Frigate/Zigbee/Z-Wave/Thread to a **Roadmap** section.
   - Keep camera, discovery, real-time sync, privacy-first as implemented.
6. Add the NODI mascot and brand-kit assets to `docs/assets/` or root `assets/`.
7. Commit as `docs: rewrite README with NODI brand and accurate quickstart`.

**Verification:**

- [ ] README renders correctly on GitHub.
- [ ] All quickstart commands execute successfully against the current codebase.
- [ ] No unimplemented features are presented as shipped.

---

## Milestone 4: Developer Tooling — Makefile, Scripts, Docker

**Goal:** Import build/run automation and containerization, adapted to `app/` and `hub/`.

**Tasks:**

1. Import `Makefile` and edit:
   - `FRONTEND_DIR := app`
   - `BACKEND_DIR := hub`
   - Backend entry: `uvicorn main:app --reload` from `hub/`
   - Frontend build: `npm run build` from `app/`
2. Import `scripts/setup.sh` and edit paths/variables.
3. Import `Dockerfile` and adapt:
   - Copy `app/package*.json` and build from `app/`
   - Copy `hub/pyproject.toml` and `hub/requirements*.txt`
   - Backend entry point: `hub/main:app`
4. Import/adapt `docker-compose.yml` and `docker-compose.prod.yml`:
   - Remove or comment out services that are not yet implemented (Frigate, Zigbee, PostgreSQL).
   - Keep Redis and MQTT as optional services only if the code supports them.
   - Default to SQLite and in-memory registry matching current `hub/`.
5. Create missing `docker/nginx.conf` and `docker/entrypoint.sh` if the Dockerfile requires them, or simplify the Dockerfile to not need them.
6. Commit as `chore: add Makefile, setup script, and Docker support for app/hub layout`.

**Verification:**

- [ ] `make help` prints usage.
- [ ] `make dev-backend` starts the hub on port 8000.
- [ ] `docker build -t myiot .` completes without errors.
- [ ] `docker compose up` starts the core services.

---

## Milestone 5: CI/CD + Launch Readiness

**Goal:** Add automated testing/building and prepare for public launch.

**Tasks:**

1. Import `.github/workflows/ci.yml` and adapt:
   - `working-directory: ./app` for frontend jobs.
   - `working-directory: ./hub` for backend jobs.
   - Remove Redis service dependency unless implemented.
   - Disable or comment out steps for missing tooling (Playwright, codecov if no token).
2. Import `.github/workflows/release.yml` (if present) or create a simple release workflow.
3. Configure GitHub Pages to serve from `/docs` folder if a `docs/index.html` launch page is created later.
4. Run local verification:
   - Backend starts.
   - Frontend builds (or identify remaining `node_modules` blocker).
   - Docker image builds.
   - README links are valid.
5. Commit as `ci: add GitHub Actions workflows adapted to app/hub structure`.
6. Push all milestones to `origin/main`.

**Verification:**

- [ ] CI workflow file passes `actionlint` or basic YAML validation.
- [ ] `git push origin main` succeeds.
- [ ] GitHub repo shows the new README, docs, and workflows.

---

## Open Decisions Before Starting

1. **License:** Confirm CC BY-NC 4.0 + commercial clause, or keep MIT from `myiot-repo`.
2. **Mascot name:** Confirm "NODI" for README and docs.
3. **Aspirational features:** Keep as roadmap items or remove from README/docs.
4. **Optional services:** Include Redis/MQTT/Frigate/Zigbee/PostgreSQL in Docker compose or defer.
5. **GitHub Pages:** Create a `docs/index.html` launch page now or defer to a follow-up phase.

## Suggested Order of Execution

| Milestone | Estimated Effort | Depends On |
|-----------|------------------|------------|
| 1. Foundation | Low | None |
| 2. Documentation | Medium | Milestone 1 |
| 3. README | Medium | Milestone 2 |
| 4. Tooling/Docker | High | Milestone 1 |
| 5. CI/CD + Launch | Medium | Milestones 1–4 |

## Risks

- The `myiot-repo` README and docs contain claims that exceed current capabilities. Publishing them as-is could mislead users.
- The Dockerfile assumes a working frontend build; current `app/node_modules` is broken in this environment and may need to be rebuilt elsewhere.
- CI workflows reference tools (Ruff, mypy, Prettier, Playwright) that may not be configured in the current project.

## Recommendation

Proceed with **Milestones 1–3 first** (metadata, docs, README) because they are low-risk and immediately improve the repo's presentation. Defer **Milestone 4's optional services** (Redis, MQTT, Frigate, Zigbee) until the backend actually supports them. Treat **Milestone 5** as the final quality gate.
