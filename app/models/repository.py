"""SQL parametrizado y validación compartida de mensajes y filtros."""

import json
import math
import re
import time
from datetime import datetime, timezone

from app.db import get_db


def utcnow():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def number(value, name, minimum, maximum):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name}: se requiere un número")
    if not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError(f"{name}: fuera de rango [{minimum}, {maximum}]")
    return float(value)


def timestamp(value):
    if not isinstance(value, str) or len(value) > 40:
        raise ValueError("Timestamp ISO 8601 requerido")
    try:
        date = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("Timestamp ISO 8601 inválido") from None
    if date.tzinfo is None:
        raise ValueError("El timestamp debe incluir zona horaria, por ejemplo Z o -03:00")
    return date.astimezone(timezone.utc).isoformat(timespec="milliseconds")


def types():
    return [dict(row) for row in get_db().execute("SELECT * FROM sensor_types ORDER BY id")]


def audit(action, details="", user_id=None):
    get_db().execute("INSERT INTO audit_log(timestamp,user_id,action,details) VALUES (?,?,?,?)",
                     (utcnow(), user_id, action, str(details)[:2000]))


def parameter(key, default):
    row = get_db().execute("SELECT value_json FROM system_parameters WHERE key=?", (key,)).fetchone()
    return json.loads(row[0]) if row else default


def set_parameter(key, value):
    get_db().execute("INSERT INTO system_parameters VALUES (?,?,?) ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json,updated_at=excluded.updated_at",
                     (key, json.dumps(value, allow_nan=False), utcnow()))


def store_reading(payload, topic_variable=None):
    started = time.perf_counter()
    if not isinstance(payload, dict):
        raise ValueError("Se requiere un objeto JSON")
    variable = payload.get("variable")
    if not isinstance(variable, str) or (topic_variable and variable != topic_variable):
        raise ValueError("Variable y topic no coinciden")
    db = get_db()
    sensor = db.execute("SELECT * FROM sensor_types WHERE variable=?", (variable,)).fetchone()
    if not sensor or payload.get("unit") != sensor["unit"]:
        raise ValueError("Variable o unidad inválida")
    value = number(payload.get("value"), "value", sensor["physical_min"], sensor["physical_max"])
    device = payload.get("device_id")
    if not isinstance(device, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", device):
        raise ValueError("device_id inválido")
    measured = timestamp(payload.get("timestamp"))
    received = utcnow()
    latency = (datetime.fromisoformat(received) - datetime.fromisoformat(measured)).total_seconds() * 1000
    if latency < -5000 or latency > 86400000:
        raise ValueError("Lectura fuera de ventana temporal (máximo 24 horas, futuro 5 segundos)")
    message_id = payload.get("message_id", f"{variable}:{measured}")
    if not isinstance(message_id, str) or not 1 <= len(message_id) <= 128:
        raise ValueError("message_id inválido")
    source = payload.get("source", "esp32")
    if source not in {"simulator", "wokwi", "esp32"}:
        raise ValueError("Origen inválido")
    with db:
        db.execute("INSERT INTO devices VALUES (?,?,?) ON CONFLICT(id) DO UPDATE SET last_seen=excluded.last_seen",
                   (device, source, received))
        cursor = db.execute("INSERT OR IGNORE INTO sensor_readings(sensor_type_id,device_id,message_id,value,measured_at,received_at,stored_at,transport_ms) VALUES (?,?,?,?,?,?,?,?)",
                            (sensor["id"], device, message_id, value, measured, received, utcnow(), latency))
        if not cursor.rowcount:
            return None
        reading_id = cursor.lastrowid
    storage_ms = (time.perf_counter() - started) * 1000
    with db:
        db.execute("UPDATE sensor_readings SET storage_ms=? WHERE id=?", (storage_ms, reading_id))
    return dict(db.execute("SELECT * FROM sensor_readings WHERE id=?", (reading_id,)).fetchone())


READINGS = """SELECT r.*, s.variable,s.label,s.unit,s.minimum,s.maximum,d.source
 FROM sensor_readings r JOIN sensor_types s ON s.id=r.sensor_type_id
 JOIN devices d ON d.id=r.device_id"""


def latest(device_id=None):
    result = []
    for sensor in types():
        query = READINGS + " WHERE s.id=?"
        args = [sensor["id"]]
        if device_id:
            query += " AND r.device_id=?"
            args.append(device_id)
        row = get_db().execute(query + " ORDER BY r.measured_at DESC,r.id DESC LIMIT 1", args).fetchone()
        result.append(dict(row) if row else {**sensor, "value": None})
    return result


def history(variable, start=None, end=None, limit=1000):
    if variable not in {row["variable"] for row in types()}:
        raise ValueError("Variable desconocida")
    if not isinstance(limit, int) or not 1 <= limit <= 10000:
        raise ValueError("limit debe estar entre 1 y 10000")
    start = timestamp(start) if start else None
    end = timestamp(end) if end else None
    if start and end and start > end:
        raise ValueError("Intervalo de fechas invertido")
    query, args = READINGS + " WHERE s.variable=?", [variable]
    for clause, value in [(" AND r.measured_at>=?", start), (" AND r.measured_at<=?", end)]:
        if value:
            query += clause
            args.append(value)
    args.append(limit)
    return [dict(r) for r in get_db().execute(query + " ORDER BY r.measured_at DESC,r.id DESC LIMIT ?", args)][::-1]
