import httpx


async def validate_token(token: str, api_version: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"https://graph.facebook.com/{api_version}/me",
                params={"access_token": token, "fields": "id,name"},
            )
            return "id" in resp.json()
    except Exception:
        return False
