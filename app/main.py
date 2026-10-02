from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.api import decisions, health, reviews, routes
from app.core.logging_config import configure_logging
from app.db.database import engine
from app.db.migrations import upgrade_database
from app.db.seed import seed


def initialize_database() -> None:
    upgrade_database()
    with Session(engine) as session:
        seed(session)


@asynccontextmanager
async def lifespan(application: FastAPI):
    configure_logging()
    await run_in_threadpool(initialize_database)
    yield


app = FastAPI(title="Jev SQL Agent Router", lifespan=lifespan)
app.include_router(health.router)
app.include_router(routes.router)
app.include_router(decisions.router)
app.include_router(reviews.router)