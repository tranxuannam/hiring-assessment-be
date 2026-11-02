"""One-time importer for the supplied business systems export pack."""

import csv
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.init import initialize_database
from app.db.import_models import (
    ImportRun,
    ImportedAudioAsset,
    ImportedHRTimeLog,
    ImportedInboxMessage,
    ImportedPipelineRecord,
    ImportedReferenceScore,
    ImportedScoringRecord,
)
from app.db.models import Answer, Candidate, Question, Role, Score, ScoringJob
from app.db.session import engine

IMPORT_NAME = "business-systems-pack-v1"


@dataclass(frozen=True)
class ImportSummary:
    roles: int
    candidates: int
    scores: int
    reference_scores: int
    inbox_messages: int
    time_logs: int
    audio_files: int


def _read_csv(pack_dir: Path, filename: str, required: set[str]) -> list[dict[str, str]]:
    path = pack_dir / filename
    if not path.is_file():
        raise FileNotFoundError(f"Required import file not found: {path}")
    with path.open(newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        headers = set(reader.fieldnames or [])
        missing = required - headers
        if missing:
            raise ValueError(f"{filename} is missing columns: {', '.join(sorted(missing))}")
        return list(reader)


def run_import(pack_dir: Path, upload_dir: Path, db: Session) -> ImportSummary:
    pack_dir = pack_dir.resolve()
    if db.scalar(select(ImportRun).where(ImportRun.name == IMPORT_NAME)) is not None:
        raise RuntimeError(f"Import {IMPORT_NAME!r} has already completed")

    pipeline = _read_csv(
        pack_dir,
        "pipeline_log.csv",
        {"candidate_id", "candidate_name", "candidate_email", "role", "answers_submitted_on"},
    )
    scoring = _read_csv(
        pack_dir,
        "scoring_sheet.csv",
        {"answer_ref", "candidate_id", "role", "question_id", "score_1", "score_2"},
    )
    reference = _read_csv(pack_dir, "hr_reference_scores.csv", {"answer_id", "question_id", "score", "scored_by"})
    inbox = _read_csv(
        pack_dir,
        "inbox_export.csv",
        {"received_at", "from_name", "from_address", "subject", "body_preview"},
    )
    time_logs = _read_csv(pack_dir, "hr_time_log.csv", {"week_starting", "task", "hours"})

    roles: dict[str, Role] = {}
    candidates: dict[str, Candidate] = {}
    for row in pipeline:
        db.add(ImportedPipelineRecord(**row))
        role = roles.get(row["role"])
        if role is None:
            role = Role(name=row["role"])
            db.add(role)
            db.flush()
            roles[row["role"]] = role
        candidate = Candidate(
            external_id=row["candidate_id"],
            email=row["candidate_email"],
            full_name=row["candidate_name"],
            role_id=role.id,
        )
        submitted = row["answers_submitted_on"].strip()
        if submitted:
            candidate.submitted_at = datetime.fromisoformat(submitted).replace(tzinfo=None)
        db.add(candidate)
        candidates[row["candidate_id"]] = candidate
    db.flush()

    question_cache: dict[tuple[str, str], Question] = {}
    score_count = 0
    for row in scoring:
        db.add(
            ImportedScoringRecord(
                answer_ref=row["answer_ref"],
                candidate_id=row["candidate_id"],
                role=row["role"],
                question_id=row["question_id"],
                scored_on=row.get("scored_on"),
                scorer_1=row.get("scorer_1"),
                score_1=int(row["score_1"]),
                scorer_2=row.get("scorer_2"),
                score_2=int(row["score_2"]),
            )
        )
        candidate = candidates.get(row["candidate_id"])
        role = roles.get(row["role"])
        if candidate is None or role is None:
            raise ValueError(f"Scoring row {row['answer_ref']} references unknown candidate or role")
        key = (role.id, row["question_id"])
        question = question_cache.get(key)
        if question is None:
            question = Question(
                external_id=row["question_id"],
                role_id=role.id,
                prompt=f"Imported question {row['question_id']}",
                expected_topics="Imported historical score; grading guide unavailable in source pack.",
                max_score=4,
                position=len([item for item in question_cache if item[0] == role.id]),
            )
            db.add(question)
            db.flush()
            question_cache[key] = question
        answer = Answer(
            id=str(uuid4()),
            candidate_id=candidate.id,
            question_id=question.id,
            answer_text="[Historical answer text was not included in the source pack.]",
            submitted_at=candidate.submitted_at,
        )
        db.add(answer)
        first, second = int(row["score_1"]), int(row["score_2"])
        imported_score = round((first + second) / 2)
        job = ScoringJob(
            id=str(uuid4()),
            candidate_id=candidate.id,
            answer_id=answer.id,
        )
        db.add(job)
        db.add(
            Score(
                answer_id=answer.id,
                scoring_job_id=job.id,
                score=imported_score,
                max_score=4,
                reason=f"Imported historical scores: scorer 1={first}, scorer 2={second}.",
                feedback="Imported historical score; no source answer text was provided.",
                model_name="historical-import",
                prompt_version="business-systems-pack-v1",
            )
        )
        job.status = "scored"
        score_count += 1

    for row in reference:
        db.add(
            ImportedReferenceScore(
                source_answer_id=row["answer_id"],
                question_id=row["question_id"],
                score=int(row["score"]),
                scored_by=row["scored_by"],
            )
        )
    for row in inbox:
        db.add(ImportedInboxMessage(**row))
    for row in time_logs:
        db.add(ImportedHRTimeLog(week_starting=row["week_starting"], task=row["task"], hours=float(row["hours"])))

    audio_count = 0
    source_audio_dir = pack_dir / "answers"
    if source_audio_dir.is_dir():
        upload_dir.mkdir(parents=True, exist_ok=True)
        for source in sorted(source_audio_dir.iterdir()):
            if not source.is_file():
                continue
            destination = upload_dir / "business-systems-pack" / source.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            db.add(
                ImportedAudioAsset(
                    source_filename=source.name,
                    stored_path=str(destination.relative_to(upload_dir)),
                    size_bytes=source.stat().st_size,
                )
            )
            audio_count += 1

    db.add(ImportRun(name=IMPORT_NAME, source_directory=str(pack_dir)))
    db.commit()
    return ImportSummary(
        roles=len(roles),
        candidates=len(candidates),
        scores=score_count,
        reference_scores=len(reference),
        inbox_messages=len(inbox),
        time_logs=len(time_logs),
        audio_files=audio_count,
    )


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Import business-systems-pack once")
    parser.add_argument("pack_dir", type=Path)
    parser.add_argument("--upload-dir", type=Path, default=Path("./uploads"))
    args = parser.parse_args()
    initialize_database(engine)
    with Session(engine) as db:
        summary = run_import(args.pack_dir, args.upload_dir, db)
    print(summary)


if __name__ == "__main__":
    main()
