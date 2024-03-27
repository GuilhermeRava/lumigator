import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from testcontainers.postgres import PostgresContainer

from src.api.deps import get_db_session
from src.db import BaseRecord
from src.main import create_app
from src.settings import settings

# TODO: Add test fixtures for Ray cluster (and other services?)
# Possibly break tests into "unit" and "integration" for those requiring external deps or not


@pytest.fixture(scope="session")
def db_engine():
    """Initialize a Postgres test container as the DB engine for integration tests."""
    with PostgresContainer(
        "postgres:16-alpine",
        port=settings.POSTGRES_PORT,
        username=settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD,
        dbname=settings.POSTGRES_DB,
    ) as postgres:
        url = postgres.get_connection_url()
        engine = create_engine(url, echo=True)
        yield engine


@pytest.fixture(scope="session", autouse=True)
def initialize_db(db_engine):
    """Create DB database/tables for the test suite.

    # TODO: Run migrations here once switched over to Alembic.
    """
    BaseRecord.metadata.create_all(db_engine)


@pytest.fixture(scope="session")
def app(db_engine):
    """Create the FastAPI app bound to the test DB engine."""
    app = create_app(db_engine)
    return app


@pytest.fixture(scope="function")
def client(app):
    """Create a test client for calling the FastAPI app."""
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="function")
def db_session(db_engine):
    """Fixture to provide a clean DB session per test function.

    This method yields a session and rolls it back after test completion
    so tests do not actually alter the DB state (which is initialized once per test suite).

    Reference: https://dev.to/jbrocher/fastapi-testing-a-database-5ao5
    """
    with db_engine.begin() as connection:
        try:
            session = Session(bind=connection)
            yield session
        finally:
            session.rollback()


@pytest.fixture(scope="function", autouse=True)
def session_override(app, db_session) -> None:
    """Override the FastAPI dependency injection for test DB sessions.

    Reference: https://fastapi.tiangolo.com/he/advanced/testing-database/
    """

    def get_db_session_override():
        yield db_session

    app.dependency_overrides[get_db_session] = get_db_session_override
