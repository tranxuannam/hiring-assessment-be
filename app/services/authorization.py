import hashlib
import hmac

from fastapi import Depends, Header, HTTPException, status

from app.config import Settings, get_settings


def hash_candidate_token(token: str, settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    return hashlib.sha256(f"{settings.candidate_link_secret}:{token}".encode()).hexdigest()


def require_hr_mock_token(
    x_hr_mock_token: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> str:
    if not x_hr_mock_token or not hmac.compare_digest(x_hr_mock_token, settings.hr_mock_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="HR mock sign-in required")
    return "mock-hr"
