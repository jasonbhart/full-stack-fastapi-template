import os
from collections.abc import Generator
from pathlib import Path

# Set test environment before any app imports
# This ensures .env.test is loaded with test-specific settings
os.environ["APP_ENV"] = "test"

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlmodel import Session, delete

from app.core.config import settings
from app.core.db import engine, init_db
from app.main import app
from app.models import AgentEvaluation, AgentRun, Item, User
from tests.utils.user import authentication_token_from_email
from tests.utils.utils import get_superuser_token_headers


@pytest.fixture(scope="session", autouse=True)
def db() -> Generator[Session, None, None]:
    # Run Alembic migrations to ensure test schema matches production
    # Use absolute path to alembic.ini so pytest works from any directory
    alembic_ini_path = Path(__file__).resolve().parent.parent / "alembic.ini"
    alembic_cfg = Config(str(alembic_ini_path))
    command.upgrade(alembic_cfg, "head")

    with Session(engine) as session:
        init_db(session)
        yield session
        # Clean up in reverse order of dependencies
        statement = delete(AgentEvaluation)
        session.execute(statement)
        statement = delete(AgentRun)
        session.execute(statement)
        statement = delete(Item)
        session.execute(statement)
        statement = delete(User)
        session.execute(statement)
        session.commit()


@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def superuser_token_headers(client: TestClient) -> dict[str, str]:
    return get_superuser_token_headers(client)


@pytest.fixture(scope="module")
def normal_user_token_headers(client: TestClient, db: Session) -> dict[str, str]:
    return authentication_token_from_email(
        client=client, email=settings.EMAIL_TEST_USER, db=db
    )
