"""PID discreto con derivada sobre medición y anti-windup condicional."""
import threading
import time
import uuid
from datetime import datetime, timezone

from app.db import get_db
from app.models.repository import parameter, set_parameter, latest, number, utcnow, audit
from app.services.mqtt_service import PREFIX

DEFAULT = dict(setpoint=6.2,kp=35.,ki=.2,kd=1.,max_output=40.,sample_time=1.,max_continuous=45.,max_dose=12.)
BOUNDS = dict(setpoint=(4,9),kp=(0,100),ki=(0,10),kd=(0,20),max_output=(0,40),sample_time=(.2,2),max_continuous=(1,60),max_dose=(.1,24))


def validate_config(config):
    if set(config) != set(DEFAULT):
        raise ValueError('Se requieren todos los parámetros PID')
    return {key:number(config[key],key,*BOUNDS[key]) for key in DEFAULT}


class PID:
    def __init__(self):
        self.reset()

    def reset(self):
        self.integral=0.
        self.previous=None

    def compute(self, measured, dt, config):
        dt=number(dt,'dt',.001,10)
        error=config['setpoint']-measured
        if abs(error)<=.03:
            self.reset()
            return 0.
        derivative=0 if self.previous is None else -(measured-self.previous)/dt
        candidate=self.integral+error*dt
        raw=config['kp']*error+config['ki']*candidate+config['kd']*derivative
        bound=config['max_output']
        # Aceptar la integración si no satura, o si ayuda a salir de saturación.
        if abs(raw)<=bound or (raw>bound and error<0) or (raw < -bound and error>0):
            self.integral=candidate
        self.previous=measured
        return max(-bound,min(bound,config['kp']*error+config['ki']*self.integral+config['kd']*derivative))


class ControlService:
    def __init__(self, mqtt):
        self.mqtt=mqtt
        self.lock=threading.RLock()
        self.pid=PID()
        self.output=0.
        self.reason='Inicio en manual'
        self.fresh=False
        self.last_tick=time.monotonic()
        self.continuous=0.
        self.manual_until=0.
        self.manual_output=0.
        self.previous_config=None
        with get_db() as db:
            if parameter('control_mode','manual')!='emergency':
                set_parameter('control_mode','manual')
            db.execute('UPDATE actuators SET requested_output=0,updated_at=?',(utcnow(),))

    def status(self):
        return dict(mode=parameter('control_mode','manual'),config=parameter('pid',DEFAULT),
                    output=self.output,reason=self.reason,fresh=self.fresh,
                    actuators=[dict(r) for r in get_db().execute('SELECT * FROM actuators')],
                    events=[dict(r) for r in get_db().execute('SELECT * FROM control_events ORDER BY id DESC LIMIT 100')])

    def operate(self, action, data, user_id):
        with self.lock:
            mode=parameter('control_mode','manual')
            if not self.mqtt.app.config.get('CONTROL_ENABLED', True) and action not in {'emergency','reset'}:
                raise ValueError('Hardware: control deshabilitado hasta calibración y validación')
            with get_db():
                if action=='config':
                    set_parameter('pid',validate_config(data))
                    self.pid.reset()
                elif action=='setpoint':
                    config=parameter('pid',DEFAULT)
                    config['setpoint']=number(data.get('setpoint'),'setpoint',4,9)
                    set_parameter('pid',config)
                    self.pid.reset()
                elif action=='emergency':
                    set_parameter('control_mode','emergency')
                elif action=='reset':
                    set_parameter('control_mode','manual')
                    self.manual_output=0
                    self.continuous=0
                    self.pid.reset()
                elif mode=='emergency':
                    raise ValueError('Parada enclavada: rearmar antes de operar')
                elif action=='mode':
                    if not isinstance(data.get('mode'),str) or data.get('mode') not in {'automatic','manual'}:
                        raise ValueError('Modo inválido')
                    set_parameter('control_mode',data['mode'])
                    self.manual_output=0
                    self.pid.reset()
                elif action=='manual':
                    self.manual_output=number(data.get('output'),'output',-40,40)
                    self.manual_until=time.monotonic()+3
                    set_parameter('control_mode','manual')
                    self.pid.reset()
                else:
                    raise ValueError('Acción desconocida')
                audit('control.'+action,str(data),user_id)
            if action in {'emergency','reset'} or (action=='manual' and self.manual_output==0):
                self.output=0
                self.send(0)
            return self.status()

    def send(self, output):
        prefix = self.mqtt.app.config.get("MQTT_TOPIC_PREFIX", PREFIX)
        payload=dict(device_id=self.mqtt.app.config['CONTROL_DEVICE_ID'],output=output,ttl=3,
                     timestamp=utcnow(),command_id=uuid.uuid4().hex)
        if not self.mqtt.app.config.get("CONTROL_ENABLED", True):
            return
        if self.mqtt.connected:
            self.mqtt.publish(f'{prefix}/control/ph',payload)
            for name,value in [('ph_plus',max(output,0)),('ph_minus',max(-output,0))]:
                self.mqtt.publish(f'{prefix}/actuadores/{name}',{**payload,'output':value})
        with get_db() as db:
            for name,value in [('ph_plus',max(output,0)),('ph_minus',max(-output,0))]:
                db.execute('UPDATE actuators SET requested_output=?,updated_at=?,device_id=? WHERE name=?',
                           (value,utcnow(),payload['device_id'],name))

    def tick(self):
        with self.lock:
            now=time.monotonic()
            dt=now-self.last_tick
            config=parameter('pid',DEFAULT)
            if dt<config['sample_time']:
                return
            self.last_tick=now
            rows={r['variable']:r for r in latest(self.mqtt.app.config['CONTROL_DEVICE_ID'])}
            ph,level=rows['ph'],rows['nivel']
            wall=time.time()
            def fresh(row):
                if row['value'] is None:
                    return False
                age=wall-datetime.fromisoformat(row['measured_at']).timestamp()
                return 0<=age<5
            self.fresh=fresh(ph) and fresh(level)
            mode=parameter('control_mode','manual')
            history=[x for x in parameter('dose_history',[]) if wall-x[0]<60]
            # Cuenta la salida del intervalo anterior; el receptor limita cada comando a 3 s.
            history.append([wall,abs(self.output)/100*min(dt,3)])
            if self.output:
                self.continuous+=min(dt,3)
            else:
                self.continuous=0
            output=0.
            reason='Manual detenido'
            if not self.mqtt.app.config.get('CONTROL_ENABLED', True):
                reason='Hardware: solo monitoreo; control físico pendiente de validación'
                self.pid.reset()
            elif mode=='emergency':
                reason='Parada de emergencia enclavada'
            elif self.continuous>=config['max_continuous'] or sum(x[1] for x in history)>=config['max_dose']:
                mode='emergency'
                reason='Límite de dosificación; requiere rearme'
            elif not self.mqtt.connected or not self.fresh or level['value']<25 or dt>5:
                reason='Interbloqueo: MQTT, medición reciente, nivel >=25% o ciclo regular requerido'
                self.pid.reset()
            elif mode=='automatic':
                if config!=self.previous_config:
                    self.pid.reset()
                output=self.pid.compute(ph['value'],min(dt,5),config)
                reason='En banda ±0.03 pH' if output==0 else 'Corrección PID'
            elif now<self.manual_until:
                output=max(-config['max_output'],min(config['max_output'],self.manual_output))
                reason='Pulso manual'
            self.previous_config=config.copy()
            # Reservar el peor caso del TTL del próximo comando, incluso si cae el proceso.
            remaining=max(0,config['max_dose']-sum(x[1] for x in history))
            safe_bound=min(config['max_output'],remaining/3*100)
            if self.continuous+3>config['max_continuous'] and output:
                mode='emergency'
                reason='Límite de actuación continua; requiere rearme'
                output=0
            output=max(-safe_bound,min(safe_bound,output))
            self.output=output
            self.reason=reason
            self.send(output)
            stamp=utcnow()
            with get_db() as db:
                set_parameter('dose_history',history)
                set_parameter('control_mode',mode)
                db.execute('INSERT INTO control_events(timestamp,reading_id,mode,setpoint,measured,error,output,action,reason) VALUES (?,?,?,?,?,?,?,?,?)',
                           (stamp,ph.get('id') if ph['value'] is not None else None,mode,config['setpoint'],ph['value'],None if ph['value'] is None else config['setpoint']-ph['value'],output,'PH_PLUS' if output>0 else 'PH_MINUS' if output<0 else 'OFF',reason))
                if output:
                    db.execute("UPDATE alerts SET response_ms=(julianday(?) - julianday(opened_at))*86400000 WHERE sensor_type_id=1 AND device_id=? AND resolved_at IS NULL AND response_ms IS NULL",(stamp,self.mqtt.app.config['CONTROL_DEVICE_ID']))
            self.mqtt.app.logger.debug('PID %.2f%%: %s',output,reason)
