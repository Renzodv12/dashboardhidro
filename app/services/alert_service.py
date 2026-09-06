"""Una alerta abierta por dispositivo, variable y condición."""
from datetime import datetime
from app.db import get_db
from app.models.repository import utcnow


def evaluate(reading):
    db = get_db()
    sensor = db.execute('SELECT * FROM sensor_types WHERE id=?', (reading['sensor_type_id'],)).fetchone()
    newest = db.execute('SELECT id FROM sensor_readings WHERE sensor_type_id=? AND device_id=? ORDER BY measured_at DESC,id DESC LIMIT 1', (sensor['id'],reading['device_id'])).fetchone()
    if newest['id'] != reading['id']:
        return
    value = reading['value']
    condition = 'LOW' if value < sensor['minimum'] else 'HIGH' if value > sensor['maximum'] else None
    now = utcnow()
    with db:
        db.execute('UPDATE alerts SET resolved_at=? WHERE sensor_type_id=? AND device_id=? AND resolved_at IS NULL AND condition!=?', (now,sensor['id'],reading['device_id'],condition or 'NORMAL'))
        if condition:
            span = sensor['maximum']-sensor['minimum']
            deviation = max(sensor['minimum']-value,value-sensor['maximum'])
            severity = 'CRITICAL' if deviation > span/2 else 'WARNING'
            message = f"{sensor['label']} {condition}: {value:.2f} {sensor['unit']}"
            db.execute('INSERT OR IGNORE INTO alerts(sensor_type_id,device_id,reading_id,condition,severity,message,opened_at) VALUES (?,?,?,?,?,?,?)', (sensor['id'],reading['device_id'],reading['id'],condition,severity,message,now))
            db.execute('UPDATE alerts SET severity=?,message=? WHERE sensor_type_id=? AND device_id=? AND condition=? AND resolved_at IS NULL', (severity,message,sensor['id'],reading['device_id'],condition))


def list_alerts(active=True):
    clause = ' WHERE resolved_at IS NULL' if active else ''
    return [dict(row) for row in get_db().execute('SELECT * FROM alerts'+clause+' ORDER BY id DESC LIMIT 300')]
