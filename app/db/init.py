from collections.abc import Mapping

from hashlib import sha256
from uuid import uuid4

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from app.db.base import Base
from app.db import models  # noqa: F401
from app.db import api_models  # noqa: F401
from app.db import import_models  # noqa: F401


def initialize_database(engine: Engine) -> None:
    Base.metadata.create_all(bind=engine)
    additions = {
        "roles": {"external_id": "VARCHAR(80)"},
        "candidates": {
            "external_id": "VARCHAR(80)",
            "access_token_hash": "VARCHAR(64)",
            "submitted_at": "DATETIME",
        },
        "questions": {"external_id": "VARCHAR(80)"},
        "answers": {
            "audio_path": "VARCHAR(500)",
            "submitted_at": "DATETIME",
        },
        "scoring_jobs": {"answer_id": "VARCHAR(36)"},
        "scores": {
            "reason": "TEXT",
            "override_score": "INTEGER",
            "override_reason": "TEXT",
            "overridden_by": "VARCHAR(100)",
        },
    }
    with engine.begin() as connection:
        inspector = inspect(connection)
        for table_name, columns in additions.items():
            existing = {column["name"] for column in inspector.get_columns(table_name)}
            for column_name, column_type in columns.items():
                if column_name not in existing:
                    connection.execute(text(f'ALTER TABLE "{table_name}" ADD COLUMN "{column_name}" {column_type}'))
        candidates = connection.execute(
            text('SELECT id FROM "candidates" WHERE access_token_hash IS NULL OR access_token_hash = ""')
        ).fetchall()
        for (candidate_id,) in candidates:
            token_hash = sha256(f"migrated:{candidate_id}:{uuid4()}".encode()).hexdigest()
            connection.execute(
                text('UPDATE "candidates" SET access_token_hash = :token_hash WHERE id = :candidate_id'),
                {"token_hash": token_hash, "candidate_id": candidate_id},
            )


def list_database_schema(engine: Engine) -> Mapping[str, list[str]]:
    inspector = inspect(engine)
    return {
        table_name: [column["name"] for column in inspector.get_columns(table_name)]
        for table_name in inspector.get_table_names()
    }
