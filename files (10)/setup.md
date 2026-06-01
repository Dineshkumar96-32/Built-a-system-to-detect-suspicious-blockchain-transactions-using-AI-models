# BlockShield — Development Setup & Fixing Pyrefly Errors

## The Error

```
Cannot find module `sqlalchemy.ext.asyncio`
Cannot find module `fastapi`
Cannot find module `pydantic`
```

These `missing-import` errors appear in VS Code because **Pyrefly is looking at
a Python interpreter that doesn't have the packages installed**. The fix is
two steps: create a virtual environment and tell Pyrefly where it is.

---

## Step 1 — Create the Virtual Environment

### Windows (PowerShell)

```powershell
# From the project root (d:\Built a system to detect...)
python -m venv .venv
.venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements-dev.txt
pip install -e .
```

### macOS / Linux

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements-dev.txt
pip install -e .
```

Or use the shortcut:

```bash
make dev-install
```

---

## Step 2 — Point Pyrefly at Your Venv

Open `pyrefly.toml` and uncomment the right line:

```toml
[tool.pyrefly]

# Windows:
python_interpreter = ".venv/Scripts/python.exe"

# macOS / Linux:
# python_interpreter = ".venv/bin/python"
```

---

## Step 3 — Point VS Code at Your Venv

Press `Ctrl+Shift+P` → **Python: Select Interpreter** →
choose `.venv\Scripts\python.exe` (Windows) or `.venv/bin/python` (macOS/Linux).

This makes both the Pyrefly extension **and** the Pylance extension use the
same interpreter where your packages are installed.

---

## Step 4 — Verify

```bash
# Run Pyrefly manually
pyrefly check

# Should show 0 errors for missing-import.
# Remaining warnings (implicit-any, untyped-import) are expected
# for optional heavy deps like torch, aiokafka — they are suppressed
# with  # type: ignore[import]  at each call-site.
```

---

## Why the Error Happens

Pyrefly resolves module imports by inspecting the Python interpreter's
`sys.path` and `site-packages`. Without `python_interpreter` set:

1. Pyrefly falls back to the system Python (or VS Code's selected interpreter)
2. That interpreter's `site-packages` has no `sqlalchemy`, `fastapi`, etc.
3. Every `from sqlalchemy import ...` triggers `missing-import` (severity 8 = error)

Installing packages in a venv **and** telling Pyrefly which venv to use
resolves all of them in one shot.

---

## Project Structure Quick Reference

```
blockshield/
├── app/                    # FastAPI application
│   ├── core/
│   │   ├── config.py       # Pydantic-settings (all env vars)
│   │   └── database.py     # Async SQLAlchemy engine + get_db()
│   ├── models.py           # ALL ORM models (User, Transaction, Alert…)
│   ├── routes/             # One file per API resource
│   ├── schemas/            # Pydantic request/response schemas
│   ├── main.py             # FastAPI app factory + lifespan
│   └── worker.py           # Background pipeline worker
│
├── auth/                   # JWT, RBAC, rate-limiting
│   └── auth.py
│
├── broker/                 # Message broker (Memory/Redis/Kafka)
│   ├── message_broker.py
│   └── multichain_provider.py
│
├── ml/                     # Machine learning pipeline
│   ├── feature_engineering.py   # FeatureEngineer + OFACList
│   ├── feedback_loop.py         # LiveIsolationForest + RetrainScheduler
│   └── gnn_model.py             # GraphSAGE GNN (optional torch dep)
│
├── observability/          # Prometheus metrics + structlog
│   └── observability.py
│
├── migrations/             # Alembic database migrations
│   ├── env.py              # imports Base from app.models
│   └── versions/
│
├── tests/
│   ├── conftest.py         # Shared fixtures (StaticPool SQLite engine)
│   ├── api/                # API endpoint integration tests
│   ├── db/                 # ORM CRUD tests
│   └── pipeline/           # Worker unit tests
│
├── infra/                  # Docker infrastructure configs
│   ├── prometheus/
│   └── grafana/
│
├── pyrefly.toml            # Type checker config (set python_interpreter here)
├── pyrightconfig.json      # Pyright fallback config
├── requirements.txt        # Production dependencies
├── requirements-dev.txt    # Dev dependencies (includes pyrefly, pytest…)
├── setup.py                # pip install -e . (fixes internal imports)
├── alembic.ini
├── docker-compose.yml
└── Makefile
```

---

## Common Commands

| Task | Command |
|------|---------|
| Install deps | `pip install -r requirements-dev.txt && pip install -e .` |
| Run app | `uvicorn app.main:app --reload` |
| Run worker | `python -m app.worker` |
| Run migrations | `alembic upgrade head` |
| Type check | `pyrefly check` |
| Lint | `ruff check app broker ml auth observability tests` |
| Run tests | `pytest tests/ -v` |
| Run tests + coverage | `pytest tests/ --cov=app --cov-report=term-missing` |
