#!/usr/bin/env bash
# =============================================================================
# MYiot Development Environment Setup Script
# =============================================================================
# This script bootstraps a complete MYiot development environment.
# Run: bash scripts/setup.sh
# =============================================================================

set -euo pipefail

# Colors for output (using MYiot brand palette)
RESET='\033[0m'
INDIGO='\033[38;2;99;102;241m'
CYAN='\033[38;2;6;182;212m'
AMBER='\033[38;2;245;158;11m'
RED='\033[38;2;239;68;68m'
GREEN='\033[38;2;34;197;94m'
BOLD='\033[1m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------
log_info() { echo -e "${INDIGO}ℹ${RESET}  $1"; }
log_success() { echo -e "${GREEN}✔${RESET}  $1"; }
log_warn() { echo -e "${AMBER}⚠${RESET}  $1"; }
log_error() { echo -e "${RED}✖${RESET}  $1"; }
log_step() { echo -e "\n${BOLD}${CYAN}▶ $1${RESET}"; }

has_command() { command -v "$1" &>/dev/null; }

check_version() {
    local current="$1"
    local required="$2"
    # Simple semver comparison: require current >= required
    if [ "$(printf '%s\n' "$required" "$current" | sort -V | head -n1)" = "$required" ]; then
        return 0
    fi
    return 1
}

# ---------------------------------------------------------------------------
# Welcome banner
# ---------------------------------------------------------------------------
cat <<'EOF'
┌──────────────────────────────────────────────────────────────────────┐
│                                                                      │
│   ███╗   ███╗██╗   ██╗██╗ ██████╗ ████████╗                         │
│   ████╗ ████║╚██╗ ██╔╝██║██╔═══██╗╚══██╔══╝                         │
│   ██╔████╔██║ ╚████╔╝ ██║██║   ██║   ██║   Universal               │
│   ██║╚██╔╝██║  ╚██╔╝  ██║██║   ██║   ██║   Smart                   │
│   ██║ ╚═╝ ██║   ██║   ██║╚██████╔╝   ██║   Home                    │
│   ╚═╝     ╚═╝   ╚═╝   ╚═╝ ╚═════╝    ╚═╝   Hub                     │
│                                                                      │
│   Development Environment Setup                                      │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
EOF

log_info "Setting up MYiot development environment..."
log_info "Project root: ${PROJECT_ROOT}"

# ---------------------------------------------------------------------------
# Step 1: Check system prerequisites
# ---------------------------------------------------------------------------
log_step "Step 1/6 — Checking system prerequisites"

MISSING_DEPS=()

# Node.js >= 20
if has_command node; then
    NODE_VERSION=$(node --version | sed 's/v//')
    if check_version "$NODE_VERSION" "20.0.0"; then
        log_success "Node.js ${NODE_VERSION} detected"
    else
        log_error "Node.js ${NODE_VERSION} found, but >= 20.0.0 required"
        MISSING_DEPS+=("Node.js >= 20")
    fi
else
    log_error "Node.js not found"
    MISSING_DEPS+=("Node.js >= 20 (https://nodejs.org/)")
fi

# Python >= 3.11
if has_command python3; then
    PYTHON_VERSION=$(python3 --version | awk '{print $2}')
    if check_version "$PYTHON_VERSION" "3.11.0"; then
        log_success "Python ${PYTHON_VERSION} detected"
    else
        log_error "Python ${PYTHON_VERSION} found, but >= 3.11.0 required"
        MISSING_DEPS+=("Python >= 3.11")
    fi
else
    log_error "Python 3 not found"
    MISSING_DEPS+=("Python >= 3.11 (https://python.org/)")
fi

# Docker & Docker Compose
if has_command docker; then
    DOCKER_VERSION=$(docker --version | awk '{print $3}' | sed 's/,//')
    log_success "Docker ${DOCKER_VERSION} detected"
else
    log_warn "Docker not found (optional, but recommended)"
fi

if has_command docker-compose || docker compose version &>/dev/null; then
    log_success "Docker Compose detected"
else
    log_warn "Docker Compose not found (optional, but recommended)"
fi

# npm/pnpm
if has_command npm; then
    log_success "npm detected"
else
    MISSING_DEPS+=("npm (comes with Node.js)")
fi

# pip
if has_command pip3; then
    log_success "pip3 detected"
else
    MISSING_DEPS+=("pip3 (comes with Python 3)")
fi

if [ ${#MISSING_DEPS[@]} -ne 0 ]; then
    echo ""
    log_error "Missing required dependencies:"
    for dep in "${MISSING_DEPS[@]}"; do
        echo "   • ${dep}"
    done
    echo ""
    log_info "Please install the missing dependencies and re-run this script."
    exit 1
fi

# ---------------------------------------------------------------------------
# Step 2: Install frontend dependencies
# ---------------------------------------------------------------------------
log_step "Step 2/6 — Installing frontend dependencies"

if [ -d "${PROJECT_ROOT}/frontend" ]; then
    cd "${PROJECT_ROOT}/frontend"
    log_info "Running npm install..."
    npm install
    log_success "Frontend dependencies installed"
else
    log_warn "Frontend directory not found, skipping..."
fi

# ---------------------------------------------------------------------------
# Step 3: Install backend dependencies
# ---------------------------------------------------------------------------
log_step "Step 3/6 — Installing backend dependencies"

if [ -d "${PROJECT_ROOT}/backend" ]; then
    cd "${PROJECT_ROOT}/backend"

    # Create virtual environment if it doesn't exist
    if [ ! -d ".venv" ]; then
        log_info "Creating Python virtual environment..."
        python3 -m venv .venv
    fi

    log_info "Activating virtual environment..."
    # shellcheck source=/dev/null
    source .venv/bin/activate

    log_info "Upgrading pip..."
    pip install --upgrade pip

    log_info "Installing Python dependencies..."
    if [ -f "requirements.txt" ]; then
        pip install -r requirements.txt
    elif [ -f "pyproject.toml" ]; then
        pip install -e ".[dev]"
    else
        log_warn "No requirements.txt or pyproject.toml found, skipping pip install"
    fi

    log_success "Backend dependencies installed"
else
    log_warn "Backend directory not found, skipping..."
fi

# ---------------------------------------------------------------------------
# Step 4: Create environment configuration
# ---------------------------------------------------------------------------
log_step "Step 4/6 — Setting up environment configuration"

cd "${PROJECT_ROOT}"

if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        log_success "Created .env from .env.example"
        log_warn "Review and update the values in .env before running MYiot"
    else
        log_warn ".env.example not found, skipping .env creation"
    fi
else
    log_warn ".env already exists, skipping creation"
fi

# ---------------------------------------------------------------------------
# Step 5: Setup pre-commit hooks
# ---------------------------------------------------------------------------
log_step "Step 5/6 — Setting up pre-commit hooks"

if [ -f ".pre-commit-config.yaml" ]; then
    if has_command pre-commit; then
        pre-commit install
        log_success "Pre-commit hooks installed"
    else
        log_warn "pre-commit not found, install with: pip install pre-commit"
    fi
else
    log_warn ".pre-commit-config.yaml not found, skipping pre-commit setup"
fi

# ---------------------------------------------------------------------------
# Step 6: Final validation
# ---------------------------------------------------------------------------
log_step "Step 6/6 — Validating setup"

cd "${PROJECT_ROOT}"

# Quick validation checks
VALIDATION_ERRORS=0

if [ -d "frontend" ] && [ ! -d "frontend/node_modules" ]; then
    log_error "Frontend node_modules not found"
    VALIDATION_ERRORS=$((VALIDATION_ERRORS + 1))
fi

if [ -d "backend" ] && [ ! -d "backend/.venv" ]; then
    log_error "Backend virtual environment not found"
    VALIDATION_ERRORS=$((VALIDATION_ERRORS + 1))
fi

if [ $VALIDATION_ERRORS -eq 0 ]; then
    log_success "All validation checks passed!"
else
    log_error "Some validation checks failed. Please review the errors above."
    exit 1
fi

# ---------------------------------------------------------------------------
# Success — Print next steps
# ---------------------------------------------------------------------------
echo ""
cat <<EOF
${GREEN}${BOLD}╔══════════════════════════════════════════════════════════════════════╗${RESET}
${GREEN}${BOLD}║  MYiot development environment is ready!                             ║${RESET}
${GREEN}${BOLD}╚══════════════════════════════════════════════════════════════════════╝${RESET}

  ${BOLD}${INDIGO}Next Steps:${RESET}

  1. Review your ${BOLD}.env${RESET} file and update any required values.

  2. Start the development servers:
     ${CYAN}make dev${RESET}
        — or —
     ${CYAN}cd frontend && npm run dev${RESET}  (Terminal 1)
     ${CYAN}cd backend  && source .venv/bin/activate && uvicorn main:app --reload${RESET}  (Terminal 2)

  3. Open the app: ${CYAN}http://localhost:5173${RESET}

  4. API docs:     ${CYAN}http://localhost:8000/docs${RESET}

  ${BOLD}${INDIGO}Useful Commands:${RESET}

  ${CYAN}make install${RESET}    Install all dependencies
  ${CYAN}make dev${RESET}        Start development servers
  ${CYAN}make test${RESET}       Run all test suites
  ${CYAN}make lint${RESET}       Run linters
  ${CYAN}make format${RESET}     Run code formatters
  ${CYAN}make build${RESET}      Build production assets
  ${CYAN}make docker-up${RESET}  Start with Docker Compose

  ${BOLD}${INDIGO}Community:${RESET}

  Discord:   ${CYAN}https://discord.gg/myiot${RESET}
  Docs:      ${CYAN}https://docs.myiot.dev${RESET}
  Issues:    ${CYAN}https://github.com/myiot/myiot/issues${RESET}

  ${AMBER}Happy hacking! 🚀${RESET}

EOF
