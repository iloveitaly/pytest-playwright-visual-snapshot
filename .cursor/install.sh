#!/usr/bin/env bash
# Cloud Agent setup for pytest-playwright-visual-snapshot.
# Idempotent: safe to run repeatedly. Prepares the pinned toolchain, Python
# dependencies, Playwright browsers, and the optional odiff matcher binary.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

BASHRC="$HOME/.bashrc"

append_once() {
    local line="$1"
    grep -qF "$line" "$BASHRC" 2>/dev/null || echo "$line" >> "$BASHRC"
}

# Install mise (tool version manager) if it is not already available.
if [ ! -x "$HOME/.local/bin/mise" ] && ! command -v mise >/dev/null 2>&1; then
    curl -fsSL https://mise.run | sh
fi
export PATH="$HOME/.local/bin:$PATH"

# Make future (agent and interactive) shells self-sufficient. Order matters:
# put ~/.local/bin on PATH, activate mise (adds tool shims, incl. direnv), then
# hook direnv for interactive convenience.
append_once 'export PATH="$HOME/.local/bin:$PATH"'
append_once 'eval "$(mise activate bash)"'
append_once 'command -v direnv >/dev/null 2>&1 && eval "$(direnv hook bash)"'
# Playwright browsers live inside the installed package (PLAYWRIGHT_BROWSERS_PATH=0)
# so pytester subprocesses, which override HOME, can still find them. This mirrors
# the repo's .envrc for shells that do not trigger direnv.
append_once 'export PLAYWRIGHT_BROWSERS_PATH=0'
export PLAYWRIGHT_BROWSERS_PATH=0

# System packages: zsh backs every Justfile recipe.
sudo apt-get update -qq
sudo apt-get install -y -qq zsh

# Install the pinned toolchain: python, uv, just, direnv, gitleaks.
mise trust
mise trust "$REPO_ROOT/mise.toml"
mise install

# The project reads configuration from .env.
[ -f .env ] || cp .env-example .env
# Allow direnv to load .envrc for interactive shells.
mise exec -- direnv allow "$REPO_ROOT" || true

# Python dependencies.
mise exec -- uv venv --allow-existing
mise exec -- uv sync
# Installs the beautiful-traceback .pth hook into the virtualenv.
mise exec -- uv run beautiful-traceback

# Playwright system libraries and browsers (chromium, firefox, webkit).
mise exec -- uv run playwright install-deps
mise exec -- uv run playwright install

# odiff enables the optional odiff matcher test suite. Skipped if npm is absent.
if ! command -v odiff >/dev/null 2>&1 && [ ! -x "$HOME/.local/bin/odiff" ]; then
    if command -v npm >/dev/null 2>&1; then
        npm install -g --prefix "$HOME/.local" odiff-bin
    else
        echo "npm not found; skipping optional odiff install"
    fi
fi

echo "cloud agent setup complete"
