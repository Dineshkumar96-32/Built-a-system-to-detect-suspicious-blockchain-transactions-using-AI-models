"""
app/main.py
FastAPI application entry point.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.logger import setup_logging, get_logger
from app.core.database import create_tables
from app.blockchain.pipeline import start_pipeline, stop_pipeline, get_metrics, is_pipeline_running
from app.routes import (
    auth, transactions, wallet, alerts, analytics, feedback, rules, settings as api_settings, websocket
)

setup_logging()
logger = get_logger("blockshield.main")
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    logger.info("BlockShield starting up", env=settings.APP_ENV if hasattr(settings, 'APP_ENV') else 'development')
    await create_tables()
    pipeline_task = start_pipeline()
    logger.info("Real-time pipeline started")
    yield
    logger.info("Shutting down...")
    stop_pipeline()


app = FastAPI(
    title="BlockShield — Blockchain Fraud Detection API",
    description=(
        "Real-time AI-powered Ethereum fraud detection. "
        "Detects flash loan attacks, anomalous transfers, and wallet clusters "
        "with 92%+ precision."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list if hasattr(settings, 'cors_origins_list') else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Rate Limiting Middleware ──────────────────────────────────────────────────
import time
from fastapi import Request
from fastapi.responses import JSONResponse

_request_history: dict[str, list[float]] = {}
_last_limit_rpm = 60

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    global _last_limit_rpm
    import app.auth.auth
    limit_rpm = getattr(app.auth.auth, "RATE_LIMIT_RPM", 60)
    
    if limit_rpm != _last_limit_rpm:
        _request_history.clear()
        _last_limit_rpm = limit_rpm
        
    identifier = request.client.host if request.client else "unknown"
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        try:
            from app.auth.auth import decode_token
            token_data = decode_token(token)
            if token_data and token_data.sub:
                identifier = token_data.sub
        except Exception:
            pass

    now = time.time()
    history = _request_history.setdefault(identifier, [])
    history[:] = [t for t in history if now - t < 60]
    
    if len(history) >= limit_rpm:
        return JSONResponse(
            status_code=429,
            content={"detail": "Too Many Requests", "retry_after": 60}
        )
    
    history.append(now)
    response = await call_next(request)
    return response


# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth.router, prefix="/api/v1")
app.include_router(transactions.router, prefix="/api/v1")
app.include_router(wallet.router, prefix="/api/v1")
app.include_router(wallet.wallets_router, prefix="/api/v1")
app.include_router(alerts.router, prefix="/api/v1")
app.include_router(analytics.router, prefix="/api/v1")
app.include_router(feedback.router, prefix="/api/v1")
app.include_router(rules.router, prefix="/api/v1")
app.include_router(
    api_settings.router,
    prefix="/api/v1/settings",
    tags=["Settings"],
)
app.include_router(websocket.router, tags=["WebSocket"])


@app.get("/", include_in_schema=False)
async def root():
    return JSONResponse({
        "service": "BlockShield",
        "version": "1.0.0",
        "status": "online",
        "docs": "/docs",
    })


@app.get("/health", tags=["Health"])
async def health():
    m = get_metrics()
    running = is_pipeline_running()
    return {
        "status": "ok",
        "pipeline_running": running,
        "transactions_processed": m["total_processed"],
        "alerts_generated": m["total_alerts"],
    }


@app.get("/metrics", tags=["Metrics"])
async def metrics():
    try:
        from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
        from fastapi.responses import Response
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
    except ImportError:
        from fastapi.responses import Response
        m = get_metrics()
        running = is_pipeline_running()
        text_data = (
            "# HELP blockshield_pipeline_running Whether the pipeline is running\n"
            "# TYPE blockshield_pipeline_running gauge\n"
            f"blockshield_pipeline_running {1 if running else 0}\n"
            "# HELP blockshield_processed_transactions_total Total processed transactions\n"
            "# TYPE blockshield_processed_transactions_total counter\n"
            f"blockshield_processed_transactions_total {m['total_processed']}\n"
            "# HELP blockshield_alerts_total Total alerts\n"
            "# TYPE blockshield_alerts_total counter\n"
            f"blockshield_alerts_total {m['total_alerts']}\n"
            "# HELP python_info Python info\n"
            "# TYPE python_info gauge\n"
            "python_info{version=\"3.14\"} 1\n"
        )
        return Response(content=text_data, media_type="text/plain")


@app.get("/api/v1/metrics", tags=["Metrics"])
async def api_v1_metrics():
    return get_metrics()

