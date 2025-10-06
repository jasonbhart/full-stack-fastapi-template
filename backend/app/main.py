import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, AsyncIterator

import sentry_sdk
from fastapi import FastAPI
from fastapi.routing import APIRoute
from starlette.middleware.cors import CORSMiddleware

from app.api.main import api_router
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.rate_limit import close_rate_limiter, init_rate_limiter
from app.core.telemetry import (
    _initialize_prometheus_metrics,
    flush_telemetry,
    shutdown_telemetry,
)
from app.middleware import CorrelationIDMiddleware

# Conditional import for Prometheus instrumentator
if TYPE_CHECKING:
    from prometheus_client import CollectorRegistry
    from prometheus_fastapi_instrumentator import Instrumentator as InstrumentatorType

try:
    from prometheus_client import REGISTRY, make_asgi_app
    from prometheus_fastapi_instrumentator import Instrumentator

    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    if not TYPE_CHECKING:
        REGISTRY = None  # type: ignore[assignment]
        make_asgi_app = None  # type: ignore[assignment]
        Instrumentator = None  # type: ignore[assignment]

# Filter to suppress specific passlib bcrypt version warning
# passlib.handlers.bcrypt tries to read bcrypt.__about__.__version__ which was removed in bcrypt 4.1.0+
# This doesn't affect functionality, just creates noise in logs
class PasslibBcryptVersionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # Suppress only the specific "(trapped) error reading bcrypt version" warning
        return "(trapped) error reading bcrypt version" not in record.getMessage()


logging.getLogger("passlib.handlers.bcrypt").addFilter(PasslibBcryptVersionFilter())


def custom_generate_unique_id(route: APIRoute) -> str:
    return f"{route.tags[0]}-{route.name}"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Lifespan context manager for startup and shutdown events.

    Handles:
    - Structured logging setup
    - Rate limiter initialization
    - Prometheus metrics initialization
    - Prometheus instrumentator setup
    - Telemetry cleanup on shutdown
    """
    # Startup
    # Configure structured logging first so subsequent logs use the configured format
    setup_logging()
    logging.info("Application startup: initializing telemetry...")

    # Initialize rate limiter with Redis
    try:
        await init_rate_limiter()
    except Exception as e:
        logging.warning(f"Rate limiter initialization failed: {e}. Continuing without rate limiting.")

    # Initialize custom Prometheus metrics for agent operations
    _initialize_prometheus_metrics()

    # Initialize Prometheus FastAPI instrumentator if available
    if PROMETHEUS_AVAILABLE and Instrumentator is not None:
        try:
            instrumentator = Instrumentator(
                should_group_status_codes=False,
                should_ignore_untemplated=True,
                should_respect_env_var=True,
                should_instrument_requests_inprogress=True,
                excluded_handlers=["/metrics"],
                env_var_name="ENABLE_METRICS",
                inprogress_name="http_requests_inprogress",
                inprogress_labels=True,
            )

            # Instrument the app with default metrics
            instrumentator.instrument(app)
            logging.info("Prometheus FastAPI instrumentator initialized")
        except Exception as e:
            logging.error(f"Failed to initialize Prometheus instrumentator: {e}")
    else:
        logging.warning(
            "Prometheus instrumentator not available. "
            "Install with: pip install prometheus-fastapi-instrumentator"
        )

    yield

    # Shutdown
    logging.info("Application shutdown: cleaning up telemetry...")
    flush_telemetry()
    shutdown_telemetry()

    # Close rate limiter
    await close_rate_limiter()

    logging.info("Telemetry cleanup complete")


if settings.SENTRY_DSN and settings.ENVIRONMENT != "local":
    sentry_sdk.init(dsn=str(settings.SENTRY_DSN), enable_tracing=True)

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    generate_unique_id_function=custom_generate_unique_id,
    lifespan=lifespan,
)

# Add correlation ID middleware first (so it wraps all other middleware)
app.add_middleware(CorrelationIDMiddleware)

# Set all CORS enabled origins
if settings.all_cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.all_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(api_router, prefix=settings.API_V1_STR)

# Mount Prometheus metrics endpoint
# This endpoint exposes metrics in Prometheus format for scraping
if PROMETHEUS_AVAILABLE and make_asgi_app is not None:
    try:
        metrics_app = make_asgi_app(registry=REGISTRY)
        app.mount("/metrics", metrics_app)
        logging.info("Prometheus /metrics endpoint mounted successfully")
    except Exception as e:
        logging.error(f"Failed to mount /metrics endpoint: {e}")
else:
    logging.warning(
        "Prometheus /metrics endpoint not available. "
        "Install prometheus-client to enable metrics."
    )
