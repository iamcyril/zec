# Makefile for Zecpath AI Platform
# Works on Unix/macOS; on Windows use scripts/setup.ps1 directly.

PYTHON   := .venv/Scripts/python
PIP      := .venv/Scripts/pip
PYTEST   := .venv/Scripts/pytest
RUFF     := .venv/Scripts/ruff
MYPY     := .venv/Scripts/mypy
PRECOMMIT := .venv/Scripts/pre-commit

.PHONY: setup test lint format smoke clean

## setup: create venv, install dev deps, copy .env, install pre-commit hooks
setup:
	python -m venv .venv
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements-dev.txt
	@if not exist .env copy .env.example .env
	$(PRECOMMIT) install

## test: run full pytest suite with coverage
test:
	$(PYTEST) tests/ --cov=. --cov-report=term-missing

## lint: run ruff linter + mypy type-checker
lint:
	$(RUFF) check .
	$(MYPY) .

## format: auto-fix ruff issues
format:
	$(RUFF) check --fix .
	$(RUFF) format .

## smoke: run end-to-end smoke test
smoke:
	$(PYTHON) scripts/smoke_test.py

## clean: remove venv, caches, coverage artefacts
clean:
	if exist .venv rmdir /s /q .venv
	if exist .pytest_cache rmdir /s /q .pytest_cache
	if exist .mypy_cache rmdir /s /q .mypy_cache
	if exist .ruff_cache rmdir /s /q .ruff_cache
	if exist htmlcov rmdir /s /q htmlcov
	del /s /q *.pyc 2>nul || true
