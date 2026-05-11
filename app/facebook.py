import httpx
from pathlib import Path


class FacebookClient:
    def __init__(self, token: str, page_id: str, api_version: str):
        self.token = token
        self.page_id = page_id
        self.base = f"https://graph.facebook.com/{api_version}"

    def _build_post_url(self, compound_id: str) -> str:
        # Graph API returns IDs as "pageId_postId"
        parts = compound_id.split("_", 1)
        if len(parts) == 2:
            return f"https://www.facebook.com/{parts[0]}/posts/{parts[1]}"
        return f"https://www.facebook.com/{compound_id}"

    async def post_text(self, message: str) -> str | None:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{self.base}/{self.page_id}/feed",
                    data={"message": message, "access_token": self.token},
                )
                data = resp.json()
                if "id" in data:
                    return self._build_post_url(data["id"])
                return None
        except Exception:
            return None

    async def post_photo(self, message: str, image_path: Path, content_type: str) -> str | None:
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                with open(image_path, "rb") as f:
                    resp = await client.post(
                        f"{self.base}/{self.page_id}/photos",
                        data={"message": message, "access_token": self.token},
                        files={"source": (image_path.name, f, content_type)},
                    )
                data = resp.json()
                # photo endpoint returns both "id" (photo) and "post_id" (the feed post)
                compound_id = data.get("post_id") or data.get("id")
                if compound_id:
                    return self._build_post_url(compound_id)
                return None
        except Exception:
            return None
