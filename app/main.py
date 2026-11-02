from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.scoring import router as scoring_router
from app.api.candidate import router as candidate_router
from app.api.hr import router as hr_router
from app.config import get_settings
from app.db.init import initialize_database
from app.db.session import engine


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    initialize_database(engine)
    yield


settings = get_settings()
app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.include_router(health_router)
app.include_router(scoring_router)
app.include_router(candidate_router)
app.include_router(hr_router)
