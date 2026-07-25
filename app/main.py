from pathlib import Path
import asyncio
import logging

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
logger = logging.getLogger("gesprec")
app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="Backend API pour la plateforme Gestion Précurseurs ONCF - PM - EMIC - TMLC.",
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
        "assigned_phone_numbers": "VARCHAR(500)",
        "assigned_responsible_ids": "TEXT",
    }
    with engine.begin() as conn:
        for name, sql_type in declaration_additions.items():
            if name not in declaration_columns:
                conn.execute(text(f"ALTER TABLE declarations ADD COLUMN {name} {sql_type}"))
        if "users" in inspector.get_table_names():
            user_columns = {column["name"] for column in inspector.get_columns("users")}
            user_additions = {
                "responsible_ateliers": "TEXT",
                "phone_numbers": "VARCHAR(500)",
                "manager_id": "INTEGER",
            }
            for name, sql_type in user_additions.items():
                if name not in user_columns:
                    conn.execute(text(f"ALTER TABLE users ADD COLUMN {name} {sql_type}"))
        if "photos" in inspector.get_table_names():
            photo_columns = {column["name"] for column in inspector.get_columns("photos")}
            if "phase" not in photo_columns:
                conn.execute(text("ALTER TABLE photos ADD COLUMN phase VARCHAR(40) DEFAULT 'declaration'"))
            if "data_url" not in photo_columns:
                conn.execute(text("ALTER TABLE photos ADD COLUMN data_url TEXT"))
        if "declaration_collaborators" in inspector.get_table_names():
            collaborator_columns = {column["name"] for column in inspector.get_columns("declaration_collaborators")}
            collaborator_additions = {
                "intervention_date": "VARCHAR(80)",
                "intervention_days": "INTEGER",
            }
            for name, sql_type in collaborator_additions.items():
                if name not in collaborator_columns:
                    conn.execute(text(f"ALTER TABLE declaration_collaborators ADD COLUMN {name} {sql_type}"))


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


async def whatsapp_reminder_worker() -> None:
    while True:
        await asyncio.sleep(30)
        db = SessionLocal()
        try:
            processed = system.process_whatsapp_reminders(db)
            if processed:
                logger.info("Processed %s WhatsApp reminder(s)", processed)
        except Exception as exc:
            logger.warning("WhatsApp reminder worker failed: %s", exc)
        finally:
            db.close()
        await asyncio.sleep(6 * 60 * 60)


@app.on_event("startup")
async def start_background_workers() -> None:
    asyncio.create_task(whatsapp_reminder_worker())


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
