import hmac
from fastapi import Header, HTTPException
from backend.config.settings import get_settings


def require_authority_token(authorization: str | None = Header(default=None)) -> None:
    expected = f"Bearer {get_settings().api_token}"
    if authorization and hmac.compare_digest(authorization, expected):
        return
    raise HTTPException(status_code=401, detail="Authority token required")
