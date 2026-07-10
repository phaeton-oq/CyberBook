#!/usr/bin/env python3
"""Генерирует SECRET_KEY на каждый билд. Остальные ключи в .env не трогает."""
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"
EXAMPLE_PATH = ROOT / ".env.example"
BUILD_ID_PATH = ROOT / ".build-id"

DEV_PLACEHOLDER = "change-me-in-prod"


def read_lines(path: Path) -> list[str]:
    if not path.is_file():
        return []
    return path.read_text(encoding="utf-8").splitlines()


def write_env(lines: list[str]) -> None:
    ENV_PATH.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def upsert_key(lines: list[str], key: str, value: str) -> list[str]:
    prefix = f"{key}="
    out = []
    found = False
    for line in lines:
        if line.startswith(prefix):
            out.append(f"{prefix}{value}")
            found = True
        else:
            out.append(line)
    if not found:
        if out and out[-1].strip():
            out.append("")
        out.append(f"{prefix}{value}")
    return out


def main() -> None:
    if not ENV_PATH.is_file():
        base = read_lines(EXAMPLE_PATH)
        if not base:
            base = [
                "CEREBRAS_API_KEY=",
                "CEREBRAS_BASE_URL=https://api.cerebras.ai/v1",
                "AI_MODEL=gpt-oss-120b",
                "VIRUSTOTAL_API_KEY=",
                "SCAN_MAX_FILE_MB=32",
                f"SECRET_KEY={DEV_PLACEHOLDER}",
                "DATABASE_URL=sqlite:///cyberbook.db",
            ]
        write_env(base)

    secret = secrets.token_urlsafe(48)
    lines = upsert_key(read_lines(ENV_PATH), "SECRET_KEY", secret)
    write_env(lines)

    BUILD_ID_PATH.write_text(
        datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        encoding="utf-8",
    )
    print(f"SECRET_KEY rotated -> {ENV_PATH}")
    print(f"build id -> {BUILD_ID_PATH.name}")


if __name__ == "__main__":
    main()
