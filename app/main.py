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
from app.token_manager import validate_token

load_dotenv()

BASE_DIR = Path(__file__).parent.parent
UPLOADS_DIR = BASE_DIR / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)

with open(BASE_DIR / "config.toml", "rb") as f:
    config = tomllib.load(f)

FB_PAGE_TOKEN = os.environ["FB_PAGE_TOKEN"]
FB_PAGE_ID = os.environ["FB_PAGE_ID"]
FB_API_VERSION = "v22.0"

DISCLAIMER = config["post"]["disclaimer"]
MAX_IMAGE_BYTES = config["post"]["max_image_size_mb"] * 1024 * 1024
FB_TEXT_LIMIT = 63206
# Effective character budget for user text (separator "\n\n" = 2 chars)
USER_TEXT_LIMIT = FB_TEXT_LIMIT - len(DISCLAIMER) - 2

templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    valid = await validate_token(FB_PAGE_TOKEN, FB_API_VERSION)
    if valid:
        print("[startup] Facebook token OK.")
    else:
        print("[startup] WARNING: Facebook token validation failed.")
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

    client = FacebookClient(FB_PAGE_TOKEN, FB_PAGE_ID, FB_API_VERSION)

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
