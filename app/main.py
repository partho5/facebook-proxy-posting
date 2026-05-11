import asyncio
import os
import tomllib
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from app.facebook import FacebookClient
from app.token_manager import refresh_if_needed, validate_token

load_dotenv()

BASE_DIR = Path(__file__).parent.parent
UPLOADS_DIR = BASE_DIR / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)

with open(BASE_DIR / "config.toml", "rb") as f:
    config = tomllib.load(f)

FB_PAGE_ID = os.environ["FB_PAGE_ID"]
FB_API_VERSION = "v22.0"

DISCLAIMER = config["post"]["disclaimer"]
MAX_IMAGE_BYTES = config["post"]["max_image_size_mb"] * 1024 * 1024
FB_TEXT_LIMIT = 63206
USER_TEXT_LIMIT = FB_TEXT_LIMIT - len(DISCLAIMER) - 2

templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))


async def _token_refresh_loop():
    """Background task: check and refresh token every 24 hours."""
    while True:
        await asyncio.sleep(24 * 3600)
        print("[token] Running scheduled refresh check...")
        await refresh_if_needed()


@asynccontextmanager
async def lifespan(app: FastAPI):
    healthy = await refresh_if_needed()
    if not healthy:
        print("[startup] WARNING: Token is invalid and could not be refreshed.")
    asyncio.create_task(_token_refresh_loop())
    yield


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "app" / "static")), name="static")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "user_text_limit": USER_TEXT_LIMIT,
            "max_image_mb": config["post"]["max_image_size_mb"],
            "disclaimer": DISCLAIMER,
        },
    )


@app.post("/post")
async def create_post(
    text: str = Form(...),
    image: UploadFile | None = File(None),
):
    text = text.strip()

    if not text:
        return JSONResponse({"ok": False, "message": "Please write something before submitting."})

    full_message = f"{text}\n\n{DISCLAIMER}"

    if len(full_message) > FB_TEXT_LIMIT:
        over = len(full_message) - FB_TEXT_LIMIT
        return JSONResponse({
            "ok": False,
            "message": f"Your message is {over} character(s) too long. Please shorten it.",
        })

    # Always read from os.environ so refreshed token is used without restart
    page_token = os.environ.get("FB_PAGE_TOKEN", "")
    if not page_token:
        return JSONResponse({
            "ok": False,
            "message": "Posting service is temporarily unavailable. Please try again later.",
        })

    client = FacebookClient(page_token, FB_PAGE_ID, FB_API_VERSION)

    if image and image.filename:
        contents = await image.read()

        if len(contents) > MAX_IMAGE_BYTES:
            return JSONResponse({
                "ok": False,
                "message": f"Image must be under {config['post']['max_image_size_mb']} MB.",
            })

        suffix = Path(image.filename).suffix.lower() or ".jpg"
        content_type = image.content_type or "image/jpeg"
        temp_path = UPLOADS_DIR / f"{uuid.uuid4()}{suffix}"

        try:
            temp_path.write_bytes(contents)
            post_url = await client.post_photo(full_message, temp_path, content_type)
        finally:
            if temp_path.exists():
                temp_path.unlink()
    else:
        post_url = await client.post_text(full_message)

    if post_url is None:
        return JSONResponse({
            "ok": False,
            "message": "Your post could not be shared right now. Please try again in a moment.",
        })

    return JSONResponse({"ok": True, "url": post_url})
