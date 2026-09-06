"""Servidor local de desarrollo: python run.py."""

from app import create_app
from app.services.mqtt_service import MQTTService


if __name__ == "__main__":
    app = create_app()
    service = MQTTService(app)
    from app.services.alert_service import evaluate
    service.on_reading = evaluate
    from app.services.pid_service import ControlService
    with app.app_context():
        service.controller = ControlService(service)
    app.extensions["mqtt"] = service
    service.start()
    try:
        app.run(host=app.config["HOST"], port=app.config["PORT"], debug=app.config["DEBUG"], use_reloader=False)
    finally:
        service.stop()
