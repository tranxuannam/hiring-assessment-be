import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db.init import initialize_database
from app.db.models import Answer, Candidate, Question, Role, Score, ScoringJob
from app.db.session import get_db
from app.main import app
from app.services.authorization import hash_candidate_token


@pytest.fixture
def api_context(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}", connect_args={"check_same_thread": False})
    initialize_database(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    tokens = {"one": "candidate-one-link", "two": "candidate-two-link"}
    with Session(engine) as db:
        role = Role(name="Backend Engineer")
        db.add(role)
        first = Candidate(email="one@example.com", full_name="Candidate One", role=role)
        second = Candidate(email="two@example.com", full_name="Candidate Two", role=role)
        first.access_token_hash = hash_candidate_token(tokens["one"])
        second.access_token_hash = hash_candidate_token(tokens["two"])
        db.add_all(
            [
                Question(prompt="First question", expected_topics="Accuracy", position=0, role=role),
                Question(prompt="Second question", expected_topics="Tradeoffs", position=1, role=role),
                first,
                second,
            ]
        )
        db.commit()

    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client, tokens, engine
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)


def test_candidate_link_is_required_and_scoped(api_context):
    client, tokens, _ = api_context

    assert client.get("/candidate/not-a-real-link").status_code == 401
    first = client.get(f"/candidate/{tokens['one']}/questions/0")
    assert first.status_code == 200
    assert first.json()["prompt"] == "First question"

    client.put(
        f"/candidate/{tokens['one']}/questions/0/answer",
        json={"answer_text": "Candidate one's private answer"},
    )
    assert client.get(f"/candidate/{tokens['two']}/questions/0").json()["answer_text"] is None


def test_hr_can_create_mock_candidate_and_receive_personal_link(api_context):
    client, _, _ = api_context
    response = client.post(
        "/hr/mock-candidates",
        headers={"X-HR-Mock-Token": "development-hr-mock-token"},
        json={
            "full_name": "Mock Candidate",
            "email": "mock@example.com",
            "role_name": "Backend Engineer",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert len(body["token"]) >= 32
    assert body["assessment_link"].endswith(f"/candidate/{body['token']}")
    assert client.get(f"/candidate/{body['token']}").status_code == 200


def test_candidate_progress_refresh_and_duplicate_submission(api_context):
    client, tokens, _ = api_context
    url = f"/candidate/{tokens['one']}/questions/0/answer"

    saved = client.put(url, json={"answer_text": "My answer"})
    assert saved.status_code == 200
    assert client.get(f"/candidate/{tokens['one']}/progress").json()["answered_questions"] == 1
    assert client.post(f"/candidate/{tokens['one']}/submit").status_code == 200
    assert client.post(f"/candidate/{tokens['one']}/submit").status_code == 409
    assert client.put(url, json={"answer_text": "Changed"}).status_code == 409


def test_audio_upload_is_persisted_and_hr_requires_mock_auth(api_context):
    client, tokens, engine = api_context

    assert client.get("/hr/candidates").status_code == 401
    uploaded = client.post(
        f"/candidate/{tokens['one']}/questions/0/audio",
        files={"audio": ("answer.wav", b"RIFF audio bytes", "audio/wav")},
    )
    assert uploaded.status_code == 200

    hr_headers = {"X-HR-Mock-Token": "development-hr-mock-token"}
    grouped = client.get("/hr/candidates", headers=hr_headers)
    assert grouped.status_code == 200
    assert len(grouped.json()["Backend Engineer"]) == 2


def test_hr_can_view_and_audit_override_but_not_without_auth(api_context):
    client, tokens, engine = api_context
    headers = {"X-HR-Mock-Token": "development-hr-mock-token"}
    with Session(engine) as db:
        candidate = db.query(Candidate).filter_by(email="one@example.com").one()
        question = db.query(Question).filter_by(position=0).one()
        answer = Answer(candidate_id=candidate.id, question_id=question.id, answer_text="Answer")
        db.add(answer)
        db.flush()
        job = ScoringJob(candidate_id=candidate.id, answer_id=answer.id)
        db.add(job)
        db.flush()
        db.add(
            Score(
                answer_id=answer.id,
                scoring_job_id=job.id,
                score=3,
                max_score=4,
                reason="Suggested reason",
                feedback="Suggested reason",
                model_name="test",
                prompt_version="v1",
            )
        )
        db.commit()
        answer_id = answer.id

    assert client.get(f"/hr/candidates/{answer.candidate_id}/answers", headers=headers).status_code == 200
    override = client.post(
        f"/hr/answers/{answer_id}/override",
        headers=headers,
        json={"score": 4, "reason": "Reviewed against the rubric."},
    )
    assert override.status_code == 200
    assert override.json()["final_score"] == 4
    audit = client.get(f"/hr/candidates/{answer.candidate_id}/audit", headers=headers)
    assert audit.status_code == 200
    assert audit.json()[0]["action"] == "score_override"
