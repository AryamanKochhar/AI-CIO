"""Canonical FastAPI application."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ai_cio.api.routes import router
from ai_cio.db.session import configure_engine, get_session
from ai_cio.services.instruments import seed_instrument
from ai_cio.settings import PRODUCT_ATTRIBUTION, PRODUCT_NAME


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_engine()
    db = get_session()
    try:
        seed_instrument(db)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    yield


app = FastAPI(
    title=f"{PRODUCT_NAME} API",
    description=(
        "Personal financial decision support, psychometric assessment and CAS ingest. "
        f"{PRODUCT_ATTRIBUTION}."
    ),
    version="0.2.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


def run() -> None:
    import uvicorn

    host = os.getenv("API_HOST", "127.0.0.1")
    port = int(os.getenv("API_PORT", "8000"))
    uvicorn.run("ai_cio.api.main:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    run()
