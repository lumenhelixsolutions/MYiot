# Contributing to MYiot

Welcome to the MYiot community! We're thrilled that you're considering contributing to the Universal Smart Home Hub. Whether you're fixing a bug, adding a new device driver, improving documentation, or suggesting a feature — every contribution makes MYiot better for everyone.

> **New to open source?** No worries! Check out our [good first issue](https://github.com/myiot/myiot/labels/good%20first%20issue) labels to find beginner-friendly tasks. We're here to help you succeed.

---

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Development Setup](#development-setup)
- [Branch Naming Conventions](#branch-naming-conventions)
- [Commit Message Format](#commit-message-format)
- [Pull Request Process](#pull-request-process)
- [Code Style Guidelines](#code-style-guidelines)
- [Testing Requirements](#testing-requirements)
- [How to Report Issues](#how-to-report-issues)
- [Community](#community)

---

## Code of Conduct

This project and everyone participating in it is governed by our [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code. Please report unacceptable behavior to [conduct@myiot.dev](mailto:conduct@myiot.dev).

---

## Development Setup

### Prerequisites

Before you begin, ensure you have the following installed on your system:

| Requirement | Version | Installation |
|-------------|---------|-------------|
| **Node.js** | >= 20.0 | [nodejs.org](https://nodejs.org/) |
| **Python** | >= 3.11 | [python.org](https://www.python.org/) |
| **Docker** | >= 24.0 | [docker.com](https://www.docker.com/) (optional but recommended) |
| **Git** | >= 2.40 | [git-scm.com](https://git-scm.com/) |

### Quick Setup

The easiest way to get started is with our automated setup script:

```bash
# 1. Fork and clone the repository
git clone https://github.com/YOUR_USERNAME/myiot.git
cd myiot

# 2. Run the setup script
bash scripts/setup.sh

# 3. Review and edit your environment variables
cp .env.example .env
nano .env  # or your preferred editor

# 4. Start development servers
make dev
```

### Manual Setup

If you prefer to set things up manually:

```bash
# Frontend
cd frontend
npm install
npm run dev        # http://localhost:5173

# Backend (in a new terminal)
cd backend
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000  # http://localhost:8000
```

### Verify Your Setup

Run the full test suite to ensure everything is working:

```bash
make test
```

---

## Branch Naming Conventions

All branches must follow this naming convention so our CI/CD pipeline can properly categorize changes:

| Prefix | Purpose | Example |
|--------|---------|---------|
| `feature/` | New features or enhancements | `feature/zigbee-group-support` |
| `bugfix/` | Bug fixes | `bugfix/camera-stream-reconnect` |
| `docs/` | Documentation changes only | `docs/api-authentication` |
| `refactor/` | Code refactoring without functional changes | `refactor/websocket-manager` |
| `test/` | Adding or updating tests | `test/camera-driver-unit` |
| `chore/` | Maintenance tasks (deps, CI, etc.) | `chore/update-dependencies` |
| `security/` | Security-related fixes | `security/jwt-validation` |

```bash
# Creating a new feature branch
git checkout -b feature/my-new-feature

# Creating a bugfix branch from a specific issue
git checkout -b bugfix/issue-123-fix-camera-timeout
```

---

## Commit Message Format

We follow the [Conventional Commits](https://www.conventionalcommits.org/) specification. This enables automatic changelog generation and semantic versioning.

### Format

```
<type>(<scope>): <subject>

<body> (optional)

<footer> (optional)
```

### Types

| Type | Description |
|------|-------------|
| `feat` | A new feature |
| `fix` | A bug fix |
| `docs` | Documentation only changes |
| `style` | Changes that don't affect code meaning (formatting, semicolons, etc.) |
| `refactor` | Code change that neither fixes a bug nor adds a feature |
| `perf` | Performance improvement |
| `test` | Adding or correcting tests |
| `chore` | Build process, dependencies, tooling changes |
| `ci` | CI/CD configuration changes |
| `security` | Security-related changes |

### Scopes

Common scopes for MYiot:

- `frontend` — React/TypeScript UI code
- `backend` — FastAPI/Python server code
- `api` — REST API or WebSocket changes
- `auth` — Authentication/authorization
- `camera` — Camera streaming/Frigate integration
- `zigbee` — Zigbee device support
- `zwave` — Z-Wave device support
- `mqtt` — MQTT broker/integration
- `ws` — WebSocket infrastructure
- `docker` — Docker/Compose configuration
- `docs` — Documentation

### Examples

```bash
# Feature commit
git commit -m "feat(camera): add multi-stream grid layout support

Implements a responsive grid layout for viewing up to 4 camera
streams simultaneously on the dashboard.

Closes #456"

# Bug fix commit
git commit -m "fix(zigbee): handle unexpected device leave events

Devices that leave the network during initialization caused
an unhandled exception in the state manager.

Fixes #789"

# Documentation commit
git commit -m "docs(api): add WebSocket event examples for camera motion"

# Chore commit
git commit -m "chore(deps): bump react from 19.0.0 to 19.1.0"
```

### Commit Best Practices

- Use the present tense ("Add feature" not "Added feature")
- Use the imperative mood ("Move cursor to..." not "Moves cursor to...")
- Keep the subject line under 72 characters
- Reference issues and PRs in the footer when applicable

---

## Pull Request Process

1. **Before You Start**
   - Check existing issues and PRs to avoid duplicates
   - For significant changes, open a [feature request](https://github.com/myiot/myiot/issues/new?template=feature_request.md) first to discuss the approach

2. **Create Your Branch**
   ```bash
   git checkout main
   git pull origin main
   git checkout -b feature/your-feature-name
   ```

3. **Make Your Changes**
   - Write clean, well-commented code
   - Follow our [code style guidelines](#code-style-guidelines)
   - Add or update tests as needed
   - Update documentation if your change affects user-facing behavior

4. **Commit Your Changes**
   - Follow our [commit message format](#commit-message-format)
   - Keep commits focused and atomic

5. **Before Submitting**
   ```bash
   # Rebase onto latest main
   git fetch origin
   git rebase origin/main

   # Run the full check suite
   make lint
   make test
   make build
   ```

6. **Submit Your Pull Request**
   - Fill out the [pull request template](.github/PULL_REQUEST_TEMPLATE.md)
   - Link any related issues with `Fixes #123` or `Closes #456`
   - Request review from maintainers
   - Ensure all CI checks pass

7. **Review Process**
   - Maintainers will review within 48-72 hours
   - Address review feedback promptly
   - Once approved, a maintainer will merge your PR

8. **After Merge**
   - Your contribution will be included in the next release
   - You'll be credited in the changelog and release notes

---

## Code Style Guidelines

### Frontend (React + TypeScript)

We use **ESLint**, **Prettier**, and **TypeScript** strict mode:

```bash
# Check linting
cd frontend && npm run lint

# Auto-fix issues
cd frontend && npm run lint:fix

# Check formatting
cd frontend && npx prettier --check "src/**/*"

# Auto-format
cd frontend && npm run format
```

**Key rules:**
- Use functional components with hooks (no class components)
- Prefer `const` and arrow functions
- Use explicit TypeScript types (no `any` without justification)
- Component files use PascalCase (`CameraCard.tsx`)
- Utility files use camelCase (`useWebSocket.ts`)
- CSS modules or Tailwind utility classes only
- Maximum line length: 100 characters

### Backend (Python + FastAPI)

We use **Ruff**, **Black**, and **mypy**:

```bash
# Check linting
cd backend && ruff check app tests

# Auto-fix issues
cd backend && ruff check --fix app tests

# Check formatting
cd backend && ruff format --check app tests

# Type checking
cd backend && mypy app
```

**Key rules:**
- Follow PEP 8 style guidelines
- Use type hints everywhere (enforced by mypy --strict)
- Maximum line length: 100 characters (Black default)
- Use `async`/`await` for I/O-bound operations
- Document all public functions with docstrings (Google style)
- Use Pydantic models for request/response validation

### Import Order

```python
# 1. Standard library
import asyncio
from typing import Optional

# 2. Third-party packages
from fastapi import FastAPI
from pydantic import BaseModel

# 3. MYiot modules
from app.core.config import settings
from app.models.device import Device
```

---

## Testing Requirements

All contributions must include appropriate tests. We aim for >80% code coverage.

### Frontend Tests (Jest + React Testing Library)

```bash
# Run all tests
cd frontend && npm run test:run

# Run with coverage
cd frontend && npm run test:run -- --coverage

# Watch mode (during development)
cd frontend && npm run test
```

**Guidelines:**
- Test component rendering and user interactions
- Use `screen` queries following Testing Library priorities
- Mock external dependencies (API calls, WebSocket)
- Test accessibility with `jest-axe`

### Backend Tests (pytest)

```bash
# Run all tests
cd backend && pytest -xvs

# Run with coverage
cd backend && pytest --cov=app --cov-report=term-missing

# Run specific test file
cd backend && pytest -xvs tests/test_camera_service.py

# Run with markers
cd backend && pytest -m "not slow"
```

**Guidelines:**
- Unit tests for services and utilities
- Integration tests for API endpoints
- Use `pytest-asyncio` for async test support
- Mock external services (MQTT, Frigate, hardware)
- Use `pytest fixtures` for shared test setup

### Test Markers

```python
import pytest

@pytest.mark.unit          # Fast unit tests
@pytest.mark.integration   # Integration tests (slower)
@pytest.mark.slow          # Long-running tests
@pytest.mark.hardware      # Tests requiring physical hardware
```

---

## How to Report Issues

### Before Reporting

- Search existing issues to avoid duplicates
- Check the [documentation](docs/) for solutions
- Try the latest version to see if the issue is already fixed

### Bug Reports

Use our [Bug Report template](https://github.com/myiot/myiot/issues/new?template=bug_report.md) and include:

1. **Clear description** — What happened vs. what you expected
2. **Reproduction steps** — Step-by-step instructions
3. **Environment details** — Versions, OS, deployment method
4. **Logs** — Relevant log output (redact sensitive info)
5. **Screenshots** — If applicable

### Feature Requests

Use our [Feature Request template](https://github.com/myiot/myiot/issues/new?template=feature_request.md) and include:

1. **Problem statement** — What problem are you trying to solve?
2. **Proposed solution** — What would you like to see?
3. **Alternatives** — What have you tried or considered?
4. **Use case** — Who would benefit and how?

### Security Issues

**Do NOT open a public issue for security vulnerabilities.**

See our [Security Policy](SECURITY.md) for responsible disclosure.

---

## Community

Join our growing community of smart home enthusiasts and developers:

| Platform | Link | Purpose |
|----------|------|---------|
| **Discord** | [discord.gg/myiot](https://discord.gg/myiot) | Real-time chat, support, community |
| **GitHub Discussions** | [github.com/myiot/myiot/discussions](https://github.com/myiot/myiot/discussions) | Long-form discussions, Q&A |
| **Documentation** | [docs.myiot.dev](https://docs.myiot.dev) | Full project documentation |
| **Twitter/X** | [@myiot_hub](https://twitter.com/myiot_hub) | Announcements, tips |
| **Mastodon** | [@myiot@fosstodon.org](https://fosstodon.org/@myiot) | Open-source community |

---

## Recognition

Contributors will be:

- Listed in our [Contributors](https://github.com/myiot/myiot/graphs/contributors) page
- Mentioned in release notes
- Added to our Hall of Fame (significant contributions)
- Eligible for contributor swag (stickers, t-shirts) after 3+ merged PRs

---

Thank you for making MYiot better! 🏠⚡

*If you have questions not covered here, reach out on [Discord](https://discord.gg/myiot) or open a [Discussion](https://github.com/myiot/myiot/discussions).*
