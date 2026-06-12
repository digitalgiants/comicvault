from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app.routes import admin, comics, uploads, users

Base.metadata.create_all(bind=engine)

app = FastAPI(title="ComicVault API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users.router)
app.include_router(comics.router)
app.include_router(uploads.router)
app.include_router(admin.router)


@app.get("/health")
def health():
    return {"status": "ok"}
