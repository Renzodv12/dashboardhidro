"""Configuración local. Las rutas relativas parten del proyecto, no del shell."""

import os
import secrets
import re
from datetime import timedelta
from pathlib import Path

from dotenv import dotenv_values

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
    profile = os.getenv("HYDRO_PROFILE", "local")
    if profile not in {"local", "wokwi", "hardware"}:
        raise ValueError("HYDRO_PROFILE debe ser local, wokwi o hardware")
    path = BASE_DIR / (".env" if profile == "local" else f".env.{profile}")
    if profile != "local" and not path.is_file():
        raise ValueError(f"Falta {path.name}; consultar docs/WOKWI_GRATUITO.md")
    # Leer sin modificar os.environ: las factorías no contaminan otros perfiles.
    values = {**dotenv_values(path), **os.environ}
    def boolean(key, default=False):
        value = str(values.get(key, str(default))).lower()
        if value not in {"true", "false", "1", "0"}:
            raise ValueError(f"{key} debe ser true, false, 1 o 0")
        return value in {"true", "1"}
    def port(key, default):
        value = int(values.get(key, default))
        if not 1 <= value <= 65535:
            raise ValueError(f"{key} debe estar entre 1 y 65535")
        return value
    config = {
        "SECRET_KEY": values.get("SECRET_KEY") or secrets.token_hex(32),
        "DATABASE_PATH": values.get("DATABASE_PATH", "data/hidroponia.sqlite3"),
        "HOST": values.get("HOST", "127.0.0.1"),
        "PORT": port("PORT", 5000),
        "DEBUG": boolean("HYDRO_DEBUG"),
        "LOG_LEVEL": values.get("LOG_LEVEL", "INFO").upper(),
        "SIMULATION_ENABLED": boolean("SIMULATION_ENABLED"),
        "HYDRO_PROFILE": profile,
        "CONTROL_ENABLED": profile != "hardware",
        "MQTT_TOPIC_PREFIX": values.get("MQTT_TOPIC_PREFIX", "hidroponia"),
        "MQTT_TLS": boolean("MQTT_TLS"),
        "MQTT_CA_FILE": values.get("MQTT_CA_FILE") or None,
        "MQTT_HOST": values.get("MQTT_HOST", "localhost"),
        "MQTT_PORT": port("MQTT_PORT", 1883),
        "MQTT_USERNAME": values.get("MQTT_USERNAME", ""),
        "MQTT_PASSWORD": values.get("MQTT_PASSWORD", ""),
        "CONTROL_DEVICE_ID": values.get("CONTROL_DEVICE_ID", "simulator-01"),
        "IMAGES_PATH": str(BASE_DIR / "data" / "images"),
        "PROCESSED_PATH": str(BASE_DIR / "data" / "processed"),
        "CAMERA_INDEX": int(values.get("CAMERA_INDEX", "0")),
        "SESSION_COOKIE_HTTPONLY": True,
        "SESSION_COOKIE_NAME": "session" if profile == "local" else "hidroponia_" + profile,
        "SESSION_COOKIE_SAMESITE": "Lax",
        "PERMANENT_SESSION_LIFETIME": timedelta(hours=8),
        "MAX_CONTENT_LENGTH": 2 * 1024 * 1024,
    }

    prefix = config["MQTT_TOPIC_PREFIX"]
    if not re.fullmatch(r"[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*", prefix) or len(prefix) > 120:
        raise ValueError("MQTT_TOPIC_PREFIX inválido: no usar comodines ni barras vacías")
    if profile == "wokwi":
        if not re.fullmatch(r"hidroponia/demo/[a-f0-9]{32}", prefix):
            raise ValueError("Wokwi público requiere un prefijo único generado por prepare_wokwi.py")
        if config["MQTT_USERNAME"] or config["MQTT_PASSWORD"]:
            raise ValueError("No enviar credenciales al perfil público de Wokwi")
    if profile == "hardware":
        if config["MQTT_HOST"] in {"test.mosquitto.org", "broker.hivemq.com"}:
            raise ValueError("Hardware requiere un broker propio")
        if not config["MQTT_USERNAME"] or not config["MQTT_PASSWORD"] or not config["MQTT_TLS"]:
            raise ValueError("Hardware requiere usuario, contraseña y MQTT_TLS=true")
        if config["SIMULATION_ENABLED"]:
            raise ValueError("Deshabilitar SIMULATION_ENABLED para hardware")
    return config
