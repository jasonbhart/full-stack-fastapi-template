import logging

import sentry_sdk
from fastapi import FastAPI
from fastapi.routing import APIRoute
from starlette.middleware.cors import CORSMiddleware

from app.api.main import api_router
from app.core.config import settings

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


if settings.SENTRY_DSN and settings.ENVIRONMENT != "local":
    sentry_sdk.init(dsn=str(settings.SENTRY_DSN), enable_tracing=True)

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    generate_unique_id_function=custom_generate_unique_id,
)

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
