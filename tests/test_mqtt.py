import json
from types import SimpleNamespace
from app.services.mqtt_service import MQTTService
from app.models.repository import history, utcnow


def test_mqtt_validates_and_stores(app):
    service = MQTTService(app)
    payload = dict(variable="ph", value=6.3, unit="pH", device_id="simulator-01", timestamp=utcnow())
    message = SimpleNamespace(topic="hidroponia/sensores/ph", retain=False, payload=json.dumps(payload).encode())
    service.on_message(None, None, message)
    with app.app_context():
        assert len(history("ph")) == 1
    message.topic = "hidroponia/sensores/tds"
    service.on_message(None, None, message)
    assert service.last_error == "ValueError"
