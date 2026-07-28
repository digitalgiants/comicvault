from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import Base, engine
from app.routes import admin, comics, uploads, users
from app.routes import preferences, bug_reports, scan, kiosk, search

Base.metadata.create_all(bind=engine)

app = FastAPI(title="ComicVault API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/uploads", StaticFiles(directory="/app/uploads"), name="uploads")

app.include_router(users.router)
app.include_router(comics.router)
app.include_router(uploads.router)
app.include_router(admin.router)
app.include_router(preferences.router)
app.include_router(bug_reports.router)
app.include_router(scan.router)
app.include_router(kiosk.router)
app.include_router(search.router)


@app.get("/health")
@app.get("/v1/health")
def health():
    return {"status": "ok"}
