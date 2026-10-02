from pathlib import Path

from app.routers import moduleMaster
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .core.config import settings
from .routers import auth, profile, learning, engagement, tutor, enrollment

# The schema is owned by Flyway (db/migration); the app never creates tables.

app = FastAPI(title="vcFastApi Auth")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_origin_regex=settings.cors_origin_regex or None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# NOTE: local-disk uploads. Ephemeral on platforms like Render/Fly/Railway —
# avatars disappear on redeploy. For persistence: mount a volume + set
# UPLOADS_DIR env var to the mount path, or swap to object storage (S3/R2).
UPLOADS_DIR = Path(settings.uploads_dir)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
(UPLOADS_DIR / "avatars").mkdir(exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")

app.include_router(auth.router)
app.include_router(profile.router)
app.include_router(moduleMaster.router)
app.include_router(learning.router)
app.include_router(engagement.router)
app.include_router(tutor.router)
app.include_router(enrollment.router)

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
