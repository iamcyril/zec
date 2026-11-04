#!/usr/bin/env bash
# scripts/setup.sh — Bootstrap Zecpath development environment (Unix/macOS)
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "==> Creating virtual environment at .venv/"
python3 -m venv .venv

echo "==> Upgrading pip"
.venv/bin/pip install --upgrade pip

echo "==> Installing dev dependencies"
.venv/bin/pip install -r requirements-dev.txt

echo "==> Copying .env.example -> .env (if not present)"
if [ ! -f .env ]; then
    cp .env.example .env
    echo "    .env created."
else
    echo "    .env already exists, skipping."
fi

echo "==> Installing pre-commit hooks"
.venv/bin/pre-commit install

echo ""
echo "✅  Setup complete. Activate with:  source .venv/bin/activate"
