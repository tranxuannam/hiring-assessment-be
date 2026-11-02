from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.init import list_database_schema
from app.db.session import get_db
from app.schemas import HealthResponse, SchemaResponse
from app.services.health import check_database

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health_check(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> HealthResponse:
    check_database(db)
    return HealthResponse(status="ok", environment=settings.environment)


@router.get("/health/schema", response_model=SchemaResponse)
def database_schema(db: Session = Depends(get_db)) -> SchemaResponse:
    bind = db.get_bind()
    return SchemaResponse(tables=dict(list_database_schema(bind)))
