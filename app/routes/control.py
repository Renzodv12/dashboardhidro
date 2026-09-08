import uuid
from flask import Blueprint, current_app, g, jsonify, request
from app.db import get_db
from app.models.repository import parameter, number, types, utcnow, audit
from app.services.pid_service import DEFAULT
from app.services.mqtt_service import PREFIX

bp=Blueprint('control',__name__,url_prefix='/api')

def service():
    mqtt=current_app.extensions.get('mqtt')
    if not mqtt or not mqtt.controller:
        raise RuntimeError('Servicio de control no iniciado; ejecutar python run.py')
    return mqtt

@bp.get('/control/status')
def status():
    mqtt=current_app.extensions.get('mqtt')
    if mqtt and mqtt.controller:
        with mqtt.controller.lock:
            return jsonify(mqtt.controller.status())
    return jsonify(mode=parameter('control_mode','manual'),config=parameter('pid',DEFAULT),output=0,reason='Servicio no iniciado',fresh=False,actuators=[dict(r) for r in get_db().execute('SELECT * FROM actuators')],events=[])

@bp.get('/control/events')
def events():
    return jsonify([dict(r) for r in get_db().execute('SELECT * FROM control_events ORDER BY id DESC LIMIT 10000')])

@bp.post('/control/<action>')
def operate(action):
    if action not in {'config','setpoint','mode','manual','emergency','reset'}:
        raise ValueError('Acción desconocida')
    return jsonify(service().controller.operate(action,request.get_json(),g.user['id']))

@bp.post('/simulation/disturbance')
def disturbance():
    if not current_app.config['SIMULATION_ENABLED']:
        raise ValueError('Simulación deshabilitada')
    data=request.get_json()
    if not isinstance(data.get('variable'),str) or data.get('variable') not in {s['variable'] for s in types()}:
        raise ValueError('Variable inválida')
    delta=number(data.get('delta'),'delta',-1000,1000)
    payload=dict(device_id=current_app.config['CONTROL_DEVICE_ID'],variable=data['variable'],delta=delta,timestamp=utcnow(),command_id=uuid.uuid4().hex)
    service().publish(f"{current_app.config['MQTT_TOPIC_PREFIX']}/simulation/disturbance",payload)
    with get_db():
        audit('simulation.disturbance',str(payload),g.user['id'])
    return jsonify(status='sent',command_id=payload['command_id'])
