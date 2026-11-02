# Hiring Assessment Backend

FastAPI backend foundation using SQLAlchemy and SQLite by default.

## Run

```powershell
python -m pip install -e ".[test]"
uvicorn app.main:app --reload
```

Configuration is read from `.env` or process environment variables:

- `DATABASE_URL` (default: `sqlite:///./hiring_assessment.db`)
- `ENVIRONMENT` (default: `development`)
- `APP_NAME`
- `SQL_ECHO` (`true`/`false`)
- `LLM_API_KEY` (required for production scoring)
- `LLM_MODEL` (default: `gpt-4o-mini`)
- `LLM_PROMPT_VERSION` (default: `v1`)
- `LLM_MAX_ATTEMPTS` (default: `3`)

Database tables are initialized on application startup. `GET /health/schema` lists
the current tables and their columns. For production, replace `create_all` with a
versioned migration tool such as Alembic before deploying schema changes.

## Scoring

`POST /scoring/answers/{answer_id}` queues an answer for scoring and returns an
idempotent scoring job. The worker/service entry point is
`process_scoring_job`; it uses `OpenAILLMClient` in production and accepts an
injected client in tests.

Scores are validated as JSON with an integer from 1 through 4 and a reason.
Candidate answers are sent as explicitly untrusted data and cannot change the
system grading instructions. Jobs use these statuses:

- `queued`
- `processing`
- `scored`
- `failed`
- `needs_human`

Transient client failures are retried up to `LLM_MAX_ATTEMPTS`. Invalid model
output is persisted as `needs_human` instead of being accepted as a score.

## Candidate and HR APIs

Candidate links contain a high-entropy token and require no candidate password.
The token is never stored in plaintext. Candidate routes are scoped entirely by
that token and do not return scores:

```text
GET  /candidate/{token}
GET  /candidate/{token}/questions/{position}
PUT  /candidate/{token}/questions/{position}/answer
POST /candidate/{token}/questions/{position}/audio
GET  /candidate/{token}/progress
POST /candidate/{token}/submit
```

Candidate submissions are durable in SQLite and cannot be submitted twice.
Audio is stored under `UPLOAD_DIRECTORY` with a generated filename.

## One-time business systems import

The supplied pack can be imported once with:

```powershell
python -m app.import_business_pack .\business-systems-pack --upload-dir .\uploads
```

The migration imports roles and candidates, creates historical score records,
copies the five audio files, and preserves raw pipeline, scoring, reference
score, inbox, and HR time-log data in separate tables. It records
`business-systems-pack-v1` in `import_runs` and rejects a second run.

The source pack does not contain answer text or a mapping from audio filenames
to candidates/questions. Historical answer rows therefore contain an explicit
placeholder, and audio files are stored as unassigned imported assets rather
than being guessed into candidate records.

The HR routes currently use an explicitly labelled development-only mock sign-in:

```text
POST /hr/mock-sign-in
POST /hr/mock-candidates
POST /hr/candidates/{candidate_id}/personal-link
GET  /hr/candidates
GET  /hr/candidates/{candidate_id}/answers
POST /hr/answers/{answer_id}/override
GET  /hr/candidates/{candidate_id}/audit
```

Send the returned token as `X-HR-Mock-Token`. Mock sign-in is disabled when
`ENVIRONMENT=production`. HR answer and override routes require that header;
score overrides require a non-empty reason and create an audit event.

For local testing, create a candidate and receive a personal link:

```powershell
curl -X POST http://127.0.0.1:8000/hr/mock-candidates `
  -H "Content-Type: application/json" `
  -H "X-HR-Mock-Token: development-hr-mock-token" `
  -d '{\"full_name\":\"Mock Candidate\",\"email\":\"mock@example.com\",\"role_name\":\"Backend Engineer\"}'
```

The raw candidate token is returned once. Only its hash is stored in SQLite.

If the raw token was lost, rotate it for an existing candidate:

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/hr/candidates/{candidate_id}/personal-link" `
  -Method POST `
  -Headers @{ "X-HR-Mock-Token" = "development-hr-mock-token" }
```

## Test

```powershell
pytest
```