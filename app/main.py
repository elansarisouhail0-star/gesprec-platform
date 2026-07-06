from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect, text

from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.routers import auth, dashboard, declarations, notifications, qr, system, uploads
from app.seed import seed_default_users


settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="Backend API pour la plateforme Gestion Precurseurs EMIC - TMLC.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def apply_lightweight_migrations() -> None:
    inspector = inspect(engine)
    if "declarations" not in inspector.get_table_names():
        return
    declaration_columns = {column["name"] for column in inspector.get_columns("declarations")}
    declaration_additions = {
        "intervention_days": "INTEGER",
        "intervention_date": "VARCHAR(80)",
    }
    with engine.begin() as conn:
        for name, sql_type in declaration_additions.items():
            if name not in declaration_columns:
                conn.execute(text(f"ALTER TABLE declarations ADD COLUMN {name} {sql_type}"))
        if "photos" in inspector.get_table_names():
            photo_columns = {column["name"] for column in inspector.get_columns("photos")}
            if "phase" not in photo_columns:
                conn.execute(text("ALTER TABLE photos ADD COLUMN phase VARCHAR(40) DEFAULT 'declaration'"))
            if "data_url" not in photo_columns:
                conn.execute(text("ALTER TABLE photos ADD COLUMN data_url TEXT"))


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    apply_lightweight_migrations()
    if settings.seed_default_users:
        db = SessionLocal()
        try:
            seed_default_users(db)
        finally:
            db.close()


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(auth.router)
app.include_router(declarations.router)
app.include_router(uploads.router)
app.include_router(notifications.router)
app.include_router(dashboard.router)
app.include_router(qr.router)
app.include_router(system.router)

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
UPLOAD_DIR = Path(settings.upload_dir)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/assets", StaticFiles(directory=STATIC_DIR), name="assets")
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


@app.get("/", include_in_schema=False)
def frontend() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
