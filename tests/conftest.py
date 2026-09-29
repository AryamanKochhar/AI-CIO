"""Postgres-backed integration tests. Require the canonical PostgreSQL service."""
from __future__ import annotations

import json
import os
import subprocess
import time
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from domain.parser import FundHolding, ParseResult, Transaction

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = json.loads((ROOT / "tests" / "fixtures" / "psychometric_v1_golden.json").read_text())
TEST_DB_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql://postgres:postgres@127.0.0.1:5432/ai_cio_test",
)
ADMIN_URL = os.getenv(
    "POSTGRES_ADMIN_URL",
    "postgresql://postgres:postgres@127.0.0.1:5432/postgres",
)
os.environ.setdefault("DATABASE_URL", TEST_DB_URL)


def _can_connect(url: str) -> bool:
    try:
        engine = create_engine(url)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
        return True
    except Exception:
        return False


def _docker_available() -> bool:
    try:
        result = subprocess.run(
            ["./scripts/with-timeout.sh", "10", "docker", "info"],
            cwd=ROOT,
            capture_output=True,
            timeout=15,
        )
        return result.returncode == 0
    except Exception:
        return False


def _ensure_postgres() -> bool:
    if _can_connect(ADMIN_URL):
        return True
    compose = ROOT / "docker-compose.yml"
    if not compose.exists() or not _docker_available():
        return False
    try:
        subprocess.run(
            ["./scripts/with-timeout.sh", "60", "docker", "compose", "up", "-d", "postgres"],
            cwd=ROOT,
            check=False,
            capture_output=True,
        )
    except Exception:
        return False
    for _ in range(40):
        if _can_connect(ADMIN_URL):
            return True
        time.sleep(1)
    return False


def _ensure_test_database() -> None:
    engine = create_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
    db_name = TEST_DB_URL.rsplit("/", 1)[-1]
    with engine.connect() as conn:
        exists = conn.execute(text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": db_name}).scalar()
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{db_name}"'))
    engine.dispose()


@pytest.fixture(scope="session")
def pg_engine():
    from ai_cio.db.base import Base
    from ai_cio.db import models as _models  # noqa: F401
    from ai_cio.db.session import configure_engine

    if not _ensure_postgres():
        pytest.fail(
            "PostgreSQL is required for integration tests. "
            "Start it with `make db-up` or `make dev-up`, then retry."
        )

    _ensure_test_database()
    engine = configure_engine(TEST_DB_URL, pool_size=5, max_overflow=5)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db(pg_engine):
    from sqlalchemy import text

    from ai_cio.db.base import Base
    from ai_cio.db.session import SessionLocal
    from ai_cio.services.instruments import seed_instrument

    table_names = ", ".join(f'"{table.name}"' for table in reversed(Base.metadata.sorted_tables))
    with pg_engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {table_names} RESTART IDENTITY CASCADE"))
    session = SessionLocal()
    seed_instrument(session)
    session.commit()
    try:
        yield session
        session.commit()
    finally:
        session.close()


@pytest.fixture
def client(pg_engine, db):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from ai_cio.api.routes import router
    from ai_cio.db.session import get_db, SessionLocal

    app = FastAPI()
    app.include_router(router)

    def override_get_db():
        session = SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def _synthetic_result(label: str) -> ParseResult:
    holding = FundHolding(
        amc="Example AMC",
        folio="F1",
        scheme_name=f"Fund {label}",
        isin="INF000000001",
        opening_units=Decimal("1"),
        closing_units=Decimal("2"),
        nav=Decimal("10"),
        valuation=Decimal("20"),
        valuation_date="01-Jan-2026",
        source_page=1,
    )
    txn = Transaction(
        amc="Example AMC",
        folio="F1",
        scheme_name=f"Fund {label}",
        isin="INF000000001",
        date="01-Jan-2026",
        transaction_type="SIP_PURCHASE",
        description="Purchase - Systematic-Normal",
        amount=Decimal("20"),
        units=Decimal("2"),
        nav=Decimal("10"),
        unit_balance=Decimal("2"),
        source_page=1,
    )
    return ParseResult([holding], [txn], {1: "redacted test page"}, [])
