import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DEV_SECRET = "dev-secret-cyberbook"


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", DEV_SECRET)
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", f"sqlite:///{BASE_DIR / 'cyberbook.db'}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY", "")
    CEREBRAS_BASE_URL = os.getenv("CEREBRAS_BASE_URL", "https://api.cerebras.ai/v1")
    AI_MODEL = os.getenv("AI_MODEL", "gpt-oss-120b")

    VIRUSTOTAL_API_KEY = os.getenv("VIRUSTOTAL_API_KEY", "")
    SCAN_MAX_FILE_MB = int(os.getenv("SCAN_MAX_FILE_MB", "32"))

    @classmethod
    def using_dev_secret(cls) -> bool:
        return cls.SECRET_KEY in ("", DEV_SECRET, "change-me-in-prod")
