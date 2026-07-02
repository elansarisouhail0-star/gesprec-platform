import os
from functools import lru_cache


class Settings:
    app_name: str = os.getenv("APP_NAME", "Gesprec API")
    env: str = os.getenv("ENV", "local")
    raw_database_url: str = os.getenv("DATABASE_URL", "sqlite:///./gesprec.db")
    database_url: str = (
        raw_database_url.replace("postgres://", "postgresql+psycopg://", 1)
        if raw_database_url.startswith("postgres://")
        else raw_database_url.replace("postgresql://", "postgresql+psycopg://", 1)
        if raw_database_url.startswith("postgresql://")
        else raw_database_url
    )
    jwt_secret: str = os.getenv("JWT_SECRET", "dev-secret-change-me")
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = int(os.getenv("JWT_EXPIRES_MINUTES", "480"))
    cors_origins: list[str] = [
        item.strip()
        for item in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5500").split(",")
        if item.strip()
    ]
    upload_dir: str = os.getenv("UPLOAD_DIR", "./uploads")
    max_upload_mb: int = int(os.getenv("MAX_UPLOAD_MB", "8"))
    seed_default_users: bool = os.getenv("SEED_DEFAULT_USERS", "true").lower() == "true"
    public_base_url: str = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
    smtp_host: str = os.getenv("SMTP_HOST", "")
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    smtp_username: str = os.getenv("SMTP_USERNAME", "")
    smtp_password: str = os.getenv("SMTP_PASSWORD", "")
    smtp_from: str = os.getenv("SMTP_FROM", "gesprec@tmlc.local")
    smtp_tls: bool = os.getenv("SMTP_TLS", "true").lower() == "true"


@lru_cache
def get_settings() -> Settings:
    return Settings()
