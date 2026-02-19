from datetime import datetime, timezone

from authlib.integrations.httpx_client import AsyncOAuth2Client
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.users import User
from app.services.auth import get_or_create_user
from app.utils.dependencies import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

# scopes we need: profile info + read-only access to youtube + analytics
SCOPES = " ".join([
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
])


@router.get("/google")
async def google_login(request: Request):
    """kick off the google oauth flow — redirects the user to google's login page."""
    async with AsyncOAuth2Client(
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        scope=SCOPES,
        redirect_uri=settings.google_redirect_uri,
    ) as client:
        uri, state = client.create_authorization_url(
            GOOGLE_AUTH_URL,
            access_type="offline",  # needed to get a refresh token
            prompt="consent",       # force consent screen so we always get refresh token
        )
        request.session["oauth_state"] = state
        return RedirectResponse(uri)


@router.get("/google/callback")
async def google_callback(request: Request, db: AsyncSession = Depends(get_db)):
    """google redirects back here after login. exchange the code for tokens,
    grab user info, and create or update the user in our database."""
    state = request.session.get("oauth_state")
    if not state:
        raise HTTPException(status_code=400, detail="missing oauth state")

    async with AsyncOAuth2Client(
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        redirect_uri=settings.google_redirect_uri,
        state=state,
    ) as client:
        token = await client.fetch_token(
            GOOGLE_TOKEN_URL,
            authorization_response=str(request.url),
        )
        resp = await client.get(GOOGLE_USERINFO_URL)
        user_info = resp.json()

    expires_at = None
    if "expires_at" in token:
        expires_at = datetime.fromtimestamp(token["expires_at"], tz=timezone.utc)

    user = await get_or_create_user(
        db=db,
        google_id=user_info["sub"],
        email=user_info["email"],
        name=user_info.get("name", ""),
        picture_url=user_info.get("picture"),
        access_token=token["access_token"],
        refresh_token=token.get("refresh_token"),
        token_expires_at=expires_at,
    )

    request.session["user_id"] = str(user.id)
    return RedirectResponse(settings.frontend_url)


@router.get("/me")
async def me(current_user: User = Depends(get_current_user)):
    """returns the currently logged-in user's info."""
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "name": current_user.name,
        "picture_url": current_user.picture_url,
    }


@router.post("/logout")
async def logout(request: Request):
    """clears the session — logs the user out."""
    request.session.clear()
    return {"ok": True}
