"""Prepara archivos públicos de simulación y configuración local independiente."""
import json
import os
from pathlib import Path
import secrets
import sqlite3
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def prepare(root=ROOT, broker=None):
    from dotenv import dotenv_values
    env_path = root / '.env.wokwi'
    if not env_path.exists():
        prefix = 'hidroponia/demo/' + secrets.token_hex(16)
        content = '\n'.join([
            '# Perfil independiente; solo datos sintéticos por broker público.',
            'SECRET_KEY=' + secrets.token_hex(32),
            'DATABASE_PATH=data/hidroponia-wokwi.sqlite3',
            'HOST=127.0.0.1', 'PORT=5001', 'HYDRO_DEBUG=false',
            'SIMULATION_ENABLED=true', 'MQTT_HOST=' + (broker or 'broker.hivemq.com'),
            'MQTT_PORT=1883', 'MQTT_TLS=false', 'MQTT_USERNAME=', 'MQTT_PASSWORD=',
            'MQTT_TOPIC_PREFIX=' + prefix,
            'CONTROL_DEVICE_ID=wokwi-' + prefix.rsplit('/',1)[1][:12], '',
        ])
        env_path.write_text(content, encoding='utf-8')
        env_path.chmod(0o600)
    if broker is not None:
        if broker not in {'test.mosquitto.org','broker.hivemq.com'}:
            raise ValueError('Broker de pruebas desconocido')
        import re
        env_path.write_text(re.sub(r'^MQTT_HOST=.*$', 'MQTT_HOST='+broker,env_path.read_text(),flags=re.MULTILINE))
    values = dotenv_values(env_path)
    import re
    prefix = values.get('MQTT_TOPIC_PREFIX','')
    device = values.get('CONTROL_DEVICE_ID','')
    if not re.fullmatch(r'hidroponia/demo/[a-f0-9]{32}',prefix):
        raise ValueError('Prefijo de prueba inválido; no se sobrescribió .env.wokwi')
    if not re.fullmatch(r'wokwi-[a-zA-Z0-9_-]{1,40}',device):
        raise ValueError('Dispositivo Wokwi inválido')
    if values.get('MQTT_HOST') not in {'test.mosquitto.org','broker.hivemq.com'} or values.get('MQTT_PORT') != '1883' or values.get('MQTT_USERNAME') or values.get('MQTT_PASSWORD') or values.get('MQTT_TLS') != 'false':
        raise ValueError('Este paquete requiere un broker de pruebas permitido, puerto 1883 y sin credenciales')
    # Lista explícita: nunca se empaquetan .env, base de datos, imágenes ni contraseñas.
    source = root/'firmware/esp32'
    folder = root/'data/wokwi'
    folder.mkdir(parents=True,exist_ok=True)
    settings = dict(WIFI_SSID='Wokwi-GUEST',WIFI_PASSWORD='',MQTT_HOST=values['MQTT_HOST'],
                    MQTT_PORT=1883,MQTT_USERNAME='',MQTT_PASSWORD='',DEVICE_ID=device,MQTT_TOPIC_PREFIX=prefix)
    header = '#pragma once\n// SOLO SIMULACIÓN. Este archivo puede subirse a Wokwi.\n'
    header += '\n'.join(f'#define {key} {json.dumps(value)}' for key,value in settings.items())+'\n'
    bundle = {
        'sketch.ino': (source/'esp32.ino').read_text(),
        'diagram.json': (source/'diagram.json').read_text(),
        'libraries.txt': (source/'libraries.txt').read_text(),
        'hidroponia_config.h': header,
        'hidroponia_config.example.h': (source/'hidroponia_config.example.h').read_text(),
    }
    for name,content in bundle.items():
        (folder/name).write_text(content,encoding='utf-8')
    with zipfile.ZipFile(folder/'wokwi-gratuito.zip','w',zipfile.ZIP_DEFLATED) as archive:
        for name,content in bundle.items():
            archive.writestr(name,content)
    return folder


def provision_users():
    """Copia inicial de hashes entre bases locales; nunca al paquete Wokwi."""
    from app import create_app
    from app.db import get_db
    from config import load_config
    from app.models.repository import audit
    old = os.environ.get('HYDRO_PROFILE')
    try:
        os.environ['HYDRO_PROFILE'] = 'local'
        local = Path(load_config()['DATABASE_PATH'])
        if not local.is_absolute(): local = ROOT/local
        os.environ['HYDRO_PROFILE'] = 'wokwi'
        app = create_app()
        if not local.is_file(): return 0
        with app.app_context():
            if Path(app.config['DATABASE_PATH']).resolve() == local.resolve():
                raise ValueError('Wokwi debe usar otra base de datos')
            source = sqlite3.connect(f'{local.resolve().as_uri()}?mode=ro',uri=True)
            try:
                rows = source.execute('SELECT username,password_hash,role,active,created_at FROM users').fetchall()
            finally:
                source.close()
            with get_db() as db:
                count = 0
                for row in rows:
                    count += db.execute('INSERT OR IGNORE INTO users(username,password_hash,role,active,created_at) VALUES (?,?,?,?,?)',row).rowcount
                if count: audit('profile.provision',f'{count} cuentas importadas localmente; hashes sin exportar')
            return count
    finally:
        if old is None: os.environ.pop('HYDRO_PROFILE',None)
        else: os.environ['HYDRO_PROFILE']=old


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--broker',choices=['broker.hivemq.com','test.mosquitto.org'])
    args=parser.parse_args()
    folder=prepare(broker=args.broker)
    count=provision_users()
    print('Paquete:',folder/'wokwi-gratuito.zip')
    print('Cuentas copiadas localmente:',count)
    print('Iniciar: python run.py --profile wokwi → http://localhost:5001')
