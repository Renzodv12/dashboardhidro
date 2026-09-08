import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import zipfile
import pytest

import config
from app.db import get_db
from app.models.repository import history, utcnow
from app.services.mqtt_service import MQTTService, make_client
from app.services.pid_service import ControlService
from scripts.prepare_wokwi import prepare


def test_public_bundle_contains_no_local_secrets(tmp_path):
    source=Path(__file__).resolve().parents[1]/'firmware/esp32'
    import shutil
    shutil.copytree(source,tmp_path/'firmware/esp32',ignore=shutil.ignore_patterns('.pio'))
    folder=prepare(tmp_path)
    before=(tmp_path/'.env.wokwi').read_text()
    prepare(tmp_path)
    assert (tmp_path/'.env.wokwi').read_text()==before
    with zipfile.ZipFile(folder/'wokwi-gratuito.zip') as archive:
        assert set(archive.namelist())=={'sketch.ino','diagram.json','libraries.txt','hidroponia_config.h','hidroponia_config.example.h'}
        text=''.join(archive.read(name).decode() for name in archive.namelist())
        assert 'SECRET_KEY' not in text and 'password_hash' not in text
        assert 'broker.hivemq.com' in text and 'hidroponia/demo/' in text


def test_prefix_is_used_and_other_installations_rejected(app):
    app.config.update(MQTT_TOPIC_PREFIX='hidroponia/demo/'+'a'*32,HYDRO_PROFILE='wokwi',CONTROL_DEVICE_ID='wokwi-test')
    mqtt=MQTTService(app)
    payload=dict(device_id='wokwi-test',source='wokwi',variable='ph',unit='pH',value=6.2,timestamp=utcnow())
    def receive(prefix):
        mqtt.on_message(None,None,SimpleNamespace(topic=prefix+'/sensores/ph',retain=False,payload=json.dumps(payload).encode()))
    receive('hidroponia/demo/'+'b'*32)
    with app.app_context(): assert not history('ph')
    receive(mqtt.prefix)
    with app.app_context(): assert len(history('ph'))==1
    payload['source']='esp32'
    receive(mqtt.prefix)
    assert mqtt.last_error=='ValueError'
    mqtt.connected=True
    with pytest.raises(ValueError): mqtt.publish('hidroponia/control/ph',{})


def test_hardware_cannot_dose(app):
    app.config['CONTROL_ENABLED']=False
    mqtt=SimpleNamespace(app=app,connected=True,publish=Mock())
    with app.app_context():
        control=ControlService(mqtt)
        with pytest.raises(ValueError): control.operate('mode',{'mode':'automatic'},None)
        with pytest.raises(ValueError): control.operate('manual',{'output':20},None)
        control.send(30)
        mqtt.publish.assert_not_called()


def test_hardware_requires_private_authenticated_tls(tmp_path,monkeypatch):
    monkeypatch.setattr(config,'BASE_DIR',tmp_path)
    monkeypatch.setenv('HYDRO_PROFILE','hardware')
    (tmp_path/'.env.hardware').write_text('MQTT_HOST=raspberrypi.local\nSIMULATION_ENABLED=false\n')
    with pytest.raises(ValueError,match='usuario, contraseña'): config.load_config()
    (tmp_path/'.env.hardware').write_text('MQTT_HOST=raspberrypi.local\nSIMULATION_ENABLED=false\nMQTT_USERNAME=monitor\nMQTT_PASSWORD=test-only\nMQTT_TLS=true\n')
    result=config.load_config()
    assert result['CONTROL_ENABLED'] is False
    assert result['MQTT_TLS'] is True
    assert result['SESSION_COOKIE_NAME']=='hidroponia_hardware'


def test_public_requires_unique_prefix(tmp_path,monkeypatch):
    monkeypatch.setattr(config,'BASE_DIR',tmp_path)
    monkeypatch.setenv('HYDRO_PROFILE','wokwi')
    (tmp_path/'.env.wokwi').write_text('MQTT_TOPIC_PREFIX=hidroponia\n')
    with pytest.raises(ValueError,match='prefijo único'): config.load_config()
