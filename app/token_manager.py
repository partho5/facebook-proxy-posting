import os
import time
from pathlib import Path

import httpx
from dotenv import dotenv_values, set_key

ENV_PATH = Path(__file__).parent.parent / ".env"
REFRESH_BEFORE_EXPIRY_SECONDS = 7 * 24 * 3600  # refresh if within 7 days of expiry
API_VERSION = "v22.0"


async def validate_token(token: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"https://graph.facebook.com/{API_VERSION}/me",
                params={"access_token": token, "fields": "id"},
            )
            return "id" in resp.json()
    except Exception:
        return False


async def _exchange_long_lived_token(current_token: str, app_id: str, app_secret: str) -> tuple[str, int] | None:
    """Exchange a long-lived token for a fresh one. Returns (new_token, expires_in) or None."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"https://graph.facebook.com/oauth/access_token",
                params={
                    "grant_type": "fb_exchange_token",
                    "client_id": app_id,
                    "client_secret": app_secret,
                    "fb_exchange_token": current_token,
                },
            )
            data = resp.json()
            if "access_token" in data:
                return data["access_token"], data.get("expires_in", 5184000)
            print(f"[token] Exchange failed: {data}")
            return None
    except Exception as e:
        print(f"[token] Exchange exception: {e}")
        return None


async def _get_page_token(long_lived_token: str, page_id: str) -> str | None:
    """Derive a permanent Page Access Token from a long-lived user token."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"https://graph.facebook.com/{API_VERSION}/me/accounts",
                params={"access_token": long_lived_token},
            )
            data = resp.json()
            for page in data.get("data", []):
                if str(page.get("id")) == str(page_id):
                    return page.get("access_token")
            print(f"[token] Page ID {page_id} not found in /me/accounts")
            return None
    except Exception as e:
        print(f"[token] Get page token exception: {e}")
        return None


def _write_env(updates: dict[str, str]) -> None:
    for key, value in updates.items():
        set_key(str(ENV_PATH), key, value)


async def refresh_if_needed() -> bool:
    """
    Check if the long-lived token is expiring soon.
    If so, exchange it for a fresh one and update .env and os.environ in place.
    Returns True if token is healthy (after any refresh), False if unrecoverable.
    """
    app_id = os.environ.get("FB_APP_ID", "")
    app_secret = os.environ.get("FB_APP_SECRET", "")
    long_lived_token = os.environ.get("FB_LONG_LIVED_TOKEN", "")
    expires_at_str = os.environ.get("FB_LONG_LIVED_EXPIRES_AT", "0")
    page_id = os.environ.get("FB_PAGE_ID", "")

    if not all([app_id, app_secret, long_lived_token, page_id]):
        print("[token] Missing env vars for auto-refresh. Skipping.")
        return await validate_token(os.environ.get("FB_PAGE_TOKEN", ""))

    expires_at = int(expires_at_str)
    time_left = expires_at - int(time.time())

    if time_left > REFRESH_BEFORE_EXPIRY_SECONDS:
        days_left = time_left // 86400
        print(f"[token] Long-lived token healthy — {days_left} day(s) remaining.")
        return True

    print(f"[token] Token expiring in {time_left // 3600}h — refreshing now...")

    result = await _exchange_long_lived_token(long_lived_token, app_id, app_secret)
    if result is None:
        print("[token] Failed to refresh long-lived token.")
        return False

    new_long_lived_token, expires_in = result
    new_expires_at = int(time.time()) + expires_in

    new_page_token = await _get_page_token(new_long_lived_token, page_id)
    if new_page_token is None:
        print("[token] Refreshed user token but could not get page token.")
        return False

    # Persist to .env file
    _write_env({
        "FB_LONG_LIVED_TOKEN": new_long_lived_token,
        "FB_LONG_LIVED_EXPIRES_AT": str(new_expires_at),
        "FB_PAGE_TOKEN": new_page_token,
    })

    # Update in-memory env so the running app uses the new token immediately
    os.environ["FB_LONG_LIVED_TOKEN"] = new_long_lived_token
    os.environ["FB_LONG_LIVED_EXPIRES_AT"] = str(new_expires_at)
    os.environ["FB_PAGE_TOKEN"] = new_page_token

    days = expires_in // 86400
    print(f"[token] Token refreshed successfully. New token valid for {days} days.")
    return True
