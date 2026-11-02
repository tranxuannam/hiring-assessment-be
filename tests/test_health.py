def test_health_check(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_schema_lists_expected_tables(client):
    response = client.get("/health/schema")

    assert response.status_code == 200
    tables = response.json()["tables"]
    assert {"roles", "candidates", "questions", "answers", "scoring_jobs", "scores"} <= set(tables)
    assert "answer_text" in tables["answers"]
    assert "status" in tables["scoring_jobs"]
