import sqlite3
from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify

from app.db import get_db

bp = Blueprint("api", __name__, url_prefix="/api")


@bp.get("health")
def health():
    try:
        row = get_db().execute("SELECT MAX(version) AS version FROM schema_migrations").fetchone()
        if row["version"] is None:
            raise sqlite3.DatabaseError("No hay versión del esquema")
    except sqlite3.Error:
        current_app.logger.exception("Fallo de disponibilidad SQLite")
        return jsonify(status="degraded", database="unavailable"), 503
    return jsonify(
        status="ok",
        database="ok",
        schema_version=row["version"],
        phase=12,
        timestamp=datetime.now(timezone.utc).isoformat(),
        services={"mqtt": "connected" if current_app.extensions.get("mqtt") and current_app.extensions["mqtt"].connected else "disconnected"},
    )
