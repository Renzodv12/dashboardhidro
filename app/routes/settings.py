import io
import sqlite3
import tempfile
from pathlib import Path
from flask import Blueprint, g, jsonify, request, send_file
from app.db import get_db
from app.models.repository import number, utcnow, audit
from app.routes.auth import create_user

bp=Blueprint('settings',__name__,url_prefix='/api')

@bp.post('/settings/ranges')
def ranges():
    data=request.get_json()
    if not isinstance(data.get('variable'),str): raise ValueError('Variable inválida')
    sensor=get_db().execute('SELECT * FROM sensor_types WHERE variable=?',(data.get('variable'),)).fetchone()
    if not sensor: raise ValueError('Variable inválida')
    minimum=number(data.get('minimum'),'minimum',sensor['physical_min'],sensor['physical_max'])
    maximum=number(data.get('maximum'),'maximum',sensor['physical_min'],sensor['physical_max'])
    if minimum>=maximum: raise ValueError('El mínimo debe ser menor que el máximo')
    with get_db() as db:
        db.execute('UPDATE sensor_types SET minimum=?,maximum=? WHERE id=?',(minimum,maximum,sensor['id']))
        audit('settings.ranges',str(data),g.user['id'])
    return jsonify(status='ok')

@bp.route('/users',methods=['GET','POST'])
def users():
    if request.method=='POST':
        data=request.get_json()
        with get_db():
            user_id=create_user(data.get('username'),data.get('password'),data.get('role'))
            audit('user.create',data.get('username'),g.user['id'])
        return jsonify(id=user_id),201
    return jsonify([dict(r) for r in get_db().execute('SELECT id,username,role,active,created_at FROM users ORDER BY id')])

@bp.get('/audit')
def audit_events():
    return jsonify([dict(r) for r in get_db().execute('SELECT a.*,u.username FROM audit_log a LEFT JOIN users u ON a.user_id=u.id ORDER BY a.id DESC LIMIT 300')])

@bp.post('/backup')
def backup():
    with get_db(): audit('backup.create','Respaldo consistente SQLite',g.user['id'])
    # backup() incluye el estado comprometido en WAL; no copiar solo el archivo .sqlite3.
    with tempfile.TemporaryDirectory() as directory:
        path=Path(directory)/'backup.sqlite3'
        target=sqlite3.connect(str(path))
        try: get_db().backup(target)
        finally: target.close()
        payload=io.BytesIO(path.read_bytes())
    return send_file(payload,mimetype='application/vnd.sqlite3',as_attachment=True,download_name='hidroponia-backup.sqlite3')

@bp.get('/metrics')
def metrics():
    db=get_db()
    readings=dict(db.execute('SELECT count(*) AS received,avg(transport_ms) AS mean_transport_ms,avg(storage_ms) AS mean_storage_ms FROM sensor_readings').fetchone())
    web=dict(db.execute('SELECT count(*) AS requests,avg(duration_ms) AS mean_ms,max(duration_ms) AS max_ms FROM web_metrics').fetchone())
    samples=dict(db.execute('SELECT count(*) AS samples,avg(mqtt_connected)*100 AS mqtt_connected_pct,avg(sensor_fresh)*100 AS fresh_sensor_pct FROM service_samples').fetchone())
    return jsonify(readings=readings,web=web,service_samples=samples,alerts=db.execute('SELECT count(*) FROM alerts').fetchone()[0],note='Muestras mientras el proceso está activo. No equivalen a disponibilidad total ni prueban RNF-01. Latencia requiere relojes sincronizados. Pérdida requiere conteo de emisiones del productor.')
