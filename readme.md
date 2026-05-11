# Facebook Proxy Poster

A privacy-first web app that lets anyone post to a Facebook Page anonymously. No accounts, no logins, no user data stored — ever. Built with Python FastAPI and deployed behind Nginx.

---

## Features

- **Fully anonymous** — no user identity is recorded or stored at any point
- **Text posts** with a live character counter (respects Facebook's 63,206-char limit)
- **Optional image upload** — image is posted to Facebook then immediately deleted from the server
- **Concurrent-safe uploads** — each uploaded file gets a UUID filename; multiple simultaneous users never collide
- **Auto disclaimer** — a configurable notice is appended to every post
- **Post link on success** — users get a direct link to their post and a one-click copy button
- **Meaningful error messages** — every failure state shows a user-friendly message
- **Token health check** — app validates the Facebook token on startup and logs a warning if it's invalid
- **1-command deploy** — `./deploy.sh` pulls, installs, and restarts the service

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12, FastAPI |
| HTTP client | httpx (async) |
| Frontend | Tailwind CSS (CDN), vanilla JS |
| Server | Uvicorn + Nginx reverse proxy |
| Process manager | Systemd |
| Config | `config.toml` (non-secret), `.env` (secrets) |

---

## Project Structure

```
proxy-facebook-posting/
├── app/
│   ├── main.py                  # FastAPI app, routes, startup checks
│   ├── facebook.py              # Graph API client (text & photo posting)
│   ├── token_manager.py         # Token validation on startup
│   ├── templates/
│   │   └── index.html           # Jinja2 template — Tailwind UI
│   └── static/                  # Static assets (if any)
├── uploads/                     # Temp image storage — files deleted after posting
├── nginx/
│   └── site.conf.template       # Nginx config template (fill in your domain)
├── config.toml                  # App configuration (committed to git)
├── .env.example                 # Environment variable template
├── requirements.txt
├── deploy.sh                    # 1-command deployment script
└── proxy-facebook-posting.service.template  # Systemd unit template
```

---

## Setup — Local Development

**1. Clone and create virtual environment**
```bash
git clone git@github.com:partho5/facebook-proxy-posting.git
cd facebook-proxy-posting
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**2. Create your `.env` file**
```bash
cp .env.example .env
```
Edit `.env` and fill in your credentials:
```
FB_PAGE_TOKEN=your_permanent_page_access_token
FB_PAGE_ID=your_numeric_page_id
```
See [Getting a Facebook Token](#getting-a-facebook-token) below.

**3. (Optional) Edit `config.toml`**

Adjust the disclaimer text or max image size:
```toml
[post]
disclaimer = "The author of this post is solely accountable for its content. The page admin bears no responsibility."
max_image_size_mb = 5
```

**4. Run the development server**
```bash
venv/bin/uvicorn app.main:app --reload
```
Open [http://localhost:8000](http://localhost:8000).

---

## Setup — Production Server

**1. Clone the repo on your server**
```bash
git clone git@github.com:partho5/facebook-proxy-posting.git /path/to/app
cd /path/to/app
python3 -m venv venv
venv/bin/pip install -r requirements.txt
cp .env.example .env
# fill in .env with your credentials
```

**2. Configure Systemd**
```bash
cp proxy-facebook-posting.service.template /etc/systemd/system/proxy-facebook-posting.service
```
Edit the service file — replace `YOUR_LINUX_USER` and `/path/to/...` with real values, then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable proxy-facebook-posting
sudo systemctl start proxy-facebook-posting
```

**3. Configure Nginx**
```bash
cp nginx/site.conf.template /etc/nginx/sites-available/facebook-proxy
```
Replace `YOUR_DOMAIN_HERE` with your actual domain, then:
```bash
sudo ln -s /etc/nginx/sites-available/facebook-proxy /etc/nginx/sites-enabled/
sudo nginx -t && sudo nginx -s reload
```

**4. Deploy future updates**
```bash
./deploy.sh
```
This runs `git pull`, installs any new dependencies, and restarts the service.

---

## Getting a Facebook Token

You need a **permanent Page Access Token** — this is a one-time setup.

> A Page Access Token derived from a long-lived User Token does not expire. You will only need to repeat this if the token is revoked or your Facebook App changes.

**Step 1 — Create a Facebook App**
1. Go to [developers.facebook.com](https://developers.facebook.com) → **My Apps** → **Create App**
2. Choose **Business** type
3. Fill in the app name and contact email → **Create App**

**Step 2 — Get a short-lived User Token**
1. Inside your app dashboard, go to **Tools** → **Graph API Explorer**
2. Select your app from the top-right dropdown
3. Click **Generate Access Token** → log in and grant permissions
4. Required permissions: `pages_manage_posts`, `pages_read_engagement`

**Step 3 — Exchange for a long-lived User Token**

Run this in your terminal (replace values):
```bash
curl "https://graph.facebook.com/oauth/access_token?grant_type=fb_exchange_token&client_id=APP_ID&client_secret=APP_SECRET&fb_exchange_token=SHORT_LIVED_TOKEN"
```
Copy the `access_token` from the response.

**Step 4 — Get the permanent Page Access Token**
```bash
curl "https://graph.facebook.com/v22.0/me/accounts?access_token=LONG_LIVED_USER_TOKEN"
```
Find your page in the response and copy its `access_token`. This is your permanent Page Access Token.

**Step 5 — Get your Page ID**

The same response contains `"id"` for each page — that is your `FB_PAGE_ID`.

**Step 6 — Save to `.env`**
```
FB_PAGE_TOKEN=<permanent page access token>
FB_PAGE_ID=<numeric page id>
```

---

## Privacy Notes

- No IP addresses, cookies, sessions, or user identifiers are stored
- Uploaded images exist on disk only for the duration of the API call, then are permanently deleted
- No database is used
- No analytics or tracking scripts are included

---

## Planned Improvements

- LLM-based content moderation before posting
- Rate limiting per IP
- CAPTCHA support

---

## License

See [LICENSE](LICENSE).
