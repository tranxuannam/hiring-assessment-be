from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.init import initialize_database
from app.db.import_models import ImportRun, ImportedAudioAsset, ImportedInboxMessage
from app.db.models import Candidate, Role, Score
from app.import_business_pack import run_import


def test_business_pack_is_imported_once(tmp_path):
    source = Path(__file__).parents[1] / "business-systems-pack"
    engine = create_engine(f"sqlite:///{tmp_path / 'import.db'}")
    initialize_database(engine)

    with Session(engine) as db:
        summary = run_import(source, tmp_path / "uploads", db)
        assert summary.roles > 0
        assert summary.candidates > 0
        assert summary.scores > 0
        assert summary.audio_files == 5
        assert db.scalar(select(Candidate).where(Candidate.external_id == "C3024")) is not None
        assert db.scalar(select(Score)) is not None
        assert db.scalar(select(ImportedInboxMessage)) is not None
        assert db.scalar(select(ImportedAudioAsset)) is not None
        assert db.scalar(select(ImportRun)) is not None

        try:
            run_import(source, tmp_path / "uploads", db)
        except RuntimeError as exc:
            assert "already completed" in str(exc)
        else:
            raise AssertionError("A one-time import must reject a second run")
