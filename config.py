import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-cyberbook")
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'cyberbook.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Cerebras (OpenAI-compatible)
    CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY", "")
    CEREBRAS_BASE_URL = os.getenv("CEREBRAS_BASE_URL", "https://api.cerebras.ai/v1")
    AI_MODEL = os.getenv("AI_MODEL", "gpt-oss-120b")
