import os
from urllib.parse import urlparse
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from database import Base, engine
import models  # noqa: F401  (registers tables)
import routers
from auth import auth_router

# Creates any missing tables (safe if schema.sql was already run)
# Base.metadata.create_all(bind=engine)

app = FastAPI(title="Tax Automation API", version="1.0.0")

origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "https://gateway-tax-api.onrender.com",
]

# Support configurable production frontend origins (comma-separated or single)
frontend_url_env = os.getenv("FRONTEND_URL", "").strip()
if frontend_url_env:
    for url in frontend_url_env.split(","):
        clean_url = url.strip().rstrip("/")
        if clean_url and clean_url not in origins:
            origins.append(clean_url)

# Support Render external URL if defined
render_url_env = os.getenv("RENDER_EXTERNAL_URL", "").strip().rstrip("/")
if render_url_env and render_url_env not in origins:
    origins.append(render_url_env)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def csrf_origin_protection(request: Request, call_next):
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        # Enforce on authenticated state-changing requests
        session_id = request.cookies.get("session_id")
        if session_id:
            origin = request.headers.get("origin")
            referer = request.headers.get("referer")
            if origin:
                if origin.rstrip("/") not in origins:
                    return JSONResponse(
                        status_code=403,
                        content={"detail": "CSRF verification failed: untrusted origin"}
                    )
            elif referer:
                ref_parsed = urlparse(referer)
                ref_origin = f"{ref_parsed.scheme}://{ref_parsed.netloc}"
                if ref_origin not in origins:
                    return JSONResponse(
                        status_code=403,
                        content={"detail": "CSRF verification failed: untrusted referer"}
                    )
    return await call_next(request)

app.include_router(auth_router)

for r in (routers.categories, routers.staff, routers.clients, routers.compliance,
          routers.invoices, routers.messages, routers.tasks, routers.groups,
          routers.matter_types):
    app.include_router(r)


@app.get("/", tags=["Health"])
def health():
    return {"status": "ok"}