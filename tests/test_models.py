from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.init import initialize_database
from app.db.models import Answer, Candidate, Question, Role, ScoringJob, Score


def test_models_persist_relationships(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'models.db'}")
    initialize_database(engine)

    with Session(engine) as session:
        role = Role(name="Backend Engineer")
        candidate = Candidate(email="candidate@example.com", full_name="Candidate", role=role)
        question = Question(prompt="Explain transactions", position=0, role=role)
        answer = Answer(candidate=candidate, question=question, answer_text="A transaction is atomic.")
        job = ScoringJob(candidate=candidate)
        score = Score(
            answer=answer,
            scoring_job=job,
            score=8,
            max_score=10,
            feedback="Clear answer",
            model_name="test-model",
            prompt_version="v1",
        )
        session.add_all([role, candidate, question, answer, job, score])
        session.commit()

        assert session.query(Score).one().answer.answer_text == "A transaction is atomic."
