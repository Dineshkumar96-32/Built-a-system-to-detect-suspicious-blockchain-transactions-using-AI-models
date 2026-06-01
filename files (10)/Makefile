# ──────────────────────────────────────────────────────────────
# Makefile — BlockShield developer shortcuts
# ──────────────────────────────────────────────────────────────

.PHONY: install dev-install typecheck lint test run worker clean

# ── Setup ─────────────────────────────────────────────────────

install:
	python -m venv .venv
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -r requirements.txt
	.venv/bin/pip install -e .

dev-install:
	python -m venv .venv
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -r requirements-dev.txt
	.venv/bin/pip install -e .
	@echo ""
	@echo "✅ Dev environment ready."
	@echo "   Activate with:  source .venv/bin/activate   (macOS/Linux)"
	@echo "                   .venv\\Scripts\\activate      (Windows)"

# ── Type checking ─────────────────────────────────────────────

typecheck:
	@echo "Running Pyrefly..."
	.venv/bin/pyrefly check
	@echo ""
	@echo "Running Pyright (secondary)..."
	.venv/bin/pyright || true

# ── Lint ──────────────────────────────────────────────────────

lint:
	.venv/bin/ruff check app broker ml auth observability tests

lint-fix:
	.venv/bin/ruff check --fix app broker ml auth observability tests

# ── Tests ─────────────────────────────────────────────────────

test:
	.venv/bin/pytest tests/ -v --timeout=30

test-cov:
	.venv/bin/pytest tests/ -v --cov=app --cov=broker --cov=ml --cov=auth \
	  --cov-report=term-missing --cov-report=xml --timeout=30

# ── Run ───────────────────────────────────────────────────────

run:
	.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

worker:
	.venv/bin/python -m app.worker

migrate:
	.venv/bin/alembic upgrade head

# ── Docker ────────────────────────────────────────────────────

up:
	docker compose up -d

down:
	docker compose down

# ── Clean ─────────────────────────────────────────────────────

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .coverage coverage.xml htmlcov/ dist/ build/
