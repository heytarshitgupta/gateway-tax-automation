from fastapi import FastAPI
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
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)

for r in (routers.categories, routers.staff, routers.clients, routers.compliance,
          routers.invoices, routers.messages, routers.tasks, routers.groups):
    app.include_router(r)


@app.get("/", tags=["Health"])
def health():
    return {"status": "ok"}
