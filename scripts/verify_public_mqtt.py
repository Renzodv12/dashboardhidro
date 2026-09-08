"""Prueba breve con seis lecturas sintéticas y un comando OFF. No ejecuta Wokwi."""
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--broker',choices=['test.mosquitto.org','broker.hivemq.com'],default=None)
    args=parser.parse_args()
    os.environ['HYDRO_PROFILE']='wokwi'
    from app import create_app
    from app.models.repository import latest, utcnow
    from app.services.mqtt_service import MQTTService, make_client
    with tempfile.TemporaryDirectory() as directory:
        # Namespace separado del circuito preparado para el usuario.
        prefix='hidroponia/demo/'+uuid.uuid4().hex
        settings={'DATABASE_PATH':str(Path(directory)/'public-test.sqlite3'),'MQTT_TOPIC_PREFIX':prefix}
        if args.broker: settings['MQTT_HOST']=args.broker
        app=create_app(settings)
        service=MQTTService(app)
        peer=make_client(app.config,'synthetic-probe')
        subscribed=threading.Event()
        received=threading.Event()
        def on_connect(client,userdata,flags,reason,properties):
            if not reason.is_failure: client.subscribe(prefix+'/control/ph')
        peer.on_connect=on_connect
        peer.on_subscribe=lambda *args:subscribed.set()
        def on_message(client,userdata,message):
            payload=json.loads(message.payload)
            if payload.get('output')==0:received.set()
        peer.on_message=on_message
        service.start()
        peer.connect_async(app.config['MQTT_HOST'],app.config['MQTT_PORT'],15)
        peer.loop_start()
        try:
            if not subscribed.wait(20): raise RuntimeError('Broker público no disponible o bloqueado por la red')
            deadline=time.monotonic()+10
            while not service.connected and time.monotonic()<deadline: time.sleep(.1)
            if not service.connected: raise RuntimeError('Backend sin conexión MQTT pública')
            time.sleep(.5)
            for variable,value,unit in [('ph',6.2,'pH'),('tds',850,'ppm'),('temperatura_agua',22,'°C'),('temperatura_ambiente',27,'°C'),('humedad',65,'%'),('nivel',78,'%')]:
                payload=dict(device_id=app.config['CONTROL_DEVICE_ID'],source='wokwi',variable=variable,value=value,unit=unit,timestamp=utcnow(),message_id=uuid.uuid4().hex)
                peer.publish(prefix+'/sensores/'+variable,json.dumps(payload),qos=1)
            deadline=time.monotonic()+15
            count=0
            while time.monotonic()<deadline:
                with app.app_context():count=sum(r['value'] is not None for r in latest())
                if count==6:break
                time.sleep(.2)
            if count!=6:raise RuntimeError(f'Solo se recibieron {count}/6 variables')
            service.publish(prefix+'/control/ph',dict(output=0,ttl=0,device_id=app.config['CONTROL_DEVICE_ID'],timestamp=utcnow(),command_id=uuid.uuid4().hex))
            if not received.wait(10):raise RuntimeError('No regresó el comando OFF')
            print('APROBADO: 6 variables → broker público → SQLite; comando OFF → receptor de prueba.')
            print('No se ejecutó firmware en Wokwi; esta prueba verifica el transporte público desde el PC.')
        finally:
            service.stop()
            peer.disconnect()
            peer.loop_stop()


if __name__=='__main__':main()
