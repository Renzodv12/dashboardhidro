"""Configuración local. Las rutas relativas parten del proyecto, no del shell."""

import os
import secrets
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent


def env_bool(name, default=False):
    value = os.getenv(name, str(default)).strip().lower()
    if value not in {"true", "false", "1", "0"}:
        raise ValueError(f"{name} debe ser true, false, 1 o 0")
    return value in {"true", "1"}


def env_port(name, default):
    value = int(os.getenv(name, str(default)))
    if not 1 <= value <= 65535:
        raise ValueError(f"{name} debe estar entre 1 y 65535")
    return value


def load_config():
    load_dotenv(BASE_DIR / ".env", override=False)
    return {
        "SECRET_KEY": os.getenv("SECRET_KEY") or secrets.token_hex(32),
        "DATABASE_PATH": os.getenv("DATABASE_PATH", "data/hidroponia.sqlite3"),
        "HOST": os.getenv("HOST", "127.0.0.1"),
        "PORT": env_port("PORT", 5000),
        "DEBUG": env_bool("HYDRO_DEBUG"),
        "LOG_LEVEL": os.getenv("LOG_LEVEL", "INFO").upper(),
        "SIMULATION_ENABLED": env_bool("SIMULATION_ENABLED"),
        "MQTT_HOST": os.getenv("MQTT_HOST", "localhost"),
        "MQTT_PORT": env_port("MQTT_PORT", 1883),
        "MQTT_USERNAME": os.getenv("MQTT_USERNAME", ""),
        "MQTT_PASSWORD": os.getenv("MQTT_PASSWORD", ""),
        "CONTROL_DEVICE_ID": os.getenv("CONTROL_DEVICE_ID", "simulator-01"),
        "IMAGES_PATH": str(BASE_DIR / "data" / "images"),
        "PROCESSED_PATH": str(BASE_DIR / "data" / "processed"),
        "CAMERA_INDEX": int(os.getenv("CAMERA_INDEX", "0")),
        "SESSION_COOKIE_HTTPONLY": True,
        "SESSION_COOKIE_SAMESITE": "Lax",
        "PERMANENT_SESSION_LIFETIME": timedelta(hours=8),
        "MAX_CONTENT_LENGTH": 2 * 1024 * 1024,
    }
