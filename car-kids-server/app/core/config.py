import os
from pathlib import Path
from typing import List


BASE_DIR = Path(__file__).resolve().parent.parent.parent


def _load_dotenv_file(env_path: Path) -> None:
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        k, v = stripped.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


_load_dotenv_file(BASE_DIR / ".env")


class Settings:
    def __init__(self) -> None:
        self.APP_ENV: str = os.getenv("APP_ENV", "development")
        self.APP_HOST: str = os.getenv("APP_HOST", "127.0.0.1")
        self.APP_PORT: int = int(os.getenv("APP_PORT", "8000"))

        self.DATABASE_PATH: Path = BASE_DIR / "data" / "car_kids.db"
        self.STORAGE_ROOT: Path = BASE_DIR / "storage"

        self.MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "10"))
        self.IMAGE_ALLOWED_MIME_TYPES: str = os.getenv(
            "IMAGE_ALLOWED_MIME_TYPES", "image/jpeg,image/png,image/webp"
        )

        self.RECOGNITION_PROVIDER: str = os.getenv(
            "RECOGNITION_PROVIDER", "configurable_adapter"
        )
        self.RECOGNITION_API_KEY: str = os.getenv("RECOGNITION_API_KEY", "")
        self.RECOGNITION_API_BASE_URL: str = os.getenv("RECOGNITION_API_BASE_URL", "")
        self.RECOGNITION_TIMEOUT_SECONDS: int = int(
            os.getenv("RECOGNITION_TIMEOUT_SECONDS", "20")
        )
        self.RECOGNITION_MAX_CONCURRENCY: int = int(
            os.getenv("RECOGNITION_MAX_CONCURRENCY", "2")
        )

        self.HIGH_CONFIDENCE_THRESHOLD: float = float(
            os.getenv("HIGH_CONFIDENCE_THRESHOLD", "0.80")
        )
        self.CANDIDATE_CONFIDENCE_THRESHOLD: float = float(
            os.getenv("CANDIDATE_CONFIDENCE_THRESHOLD", "0.50")
        )

        self.API_ACCESS_TOKEN: str = os.getenv(
            "API_ACCESS_TOKEN", "dev_app_access_token_change_in_prod"
        )
        self.ADMIN_ACCESS_TOKEN: str = os.getenv(
            "ADMIN_ACCESS_TOKEN", "dev_admin_secret_token_change_in_prod"
        )
        self.CORS_ALLOW_ORIGINS: str = os.getenv("CORS_ALLOW_ORIGINS", "*")

    @property
    def cors_origins_list(self) -> List[str]:
        return [
            o.strip()
            for o in self.CORS_ALLOW_ORIGINS.split(",")
            if o.strip()
        ] or ["*"]

    @property
    def allowed_mime_set(self) -> List[str]:
        return [
            m.strip().lower()
            for m in self.IMAGE_ALLOWED_MIME_TYPES.split(",")
            if m.strip()
        ]


settings = Settings()
