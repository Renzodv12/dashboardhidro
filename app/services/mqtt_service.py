"""Un consumidor MQTT por instalación; Flask permanece independiente del broker."""

import json
import threading
import time
import uuid

import paho.mqtt.client as mqtt

from app.db import get_db
from app.models.repository import audit, store_reading, utcnow, number

PREFIX = "hidroponia"


def make_client(config, client_id):
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
    if config.get("MQTT_USERNAME"):
        client.username_pw_set(config["MQTT_USERNAME"], config["MQTT_PASSWORD"])
    client.reconnect_delay_set(min_delay=1, max_delay=10)
    client.max_queued_messages_set(100)
    return client


class MQTTService:
    def __init__(self, app):
        self.app = app
        self.connected = False
        self.last_error = None
        self.client = make_client(app.config, "hidroponia-backend")
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_connect_fail = self.on_connect_fail
        self.client.on_message = self.on_message
        self.started = time.monotonic()
        self.stop_event = threading.Event()
        self.thread = None
        self.controller = None
        self.on_reading = None

    def start(self):
        self.client.connect_async(self.app.config["MQTT_HOST"], self.app.config["MQTT_PORT"], 15)
        self.client.loop_start()
        self.thread = threading.Thread(target=self.tick, name="control-watchdog", daemon=True)
        self.thread.start()

    def on_connect(self, client, userdata, flags, reason_code, properties):
        self.connected = not reason_code.is_failure
        if self.connected:
            self.last_error = None
            client.subscribe([(f"{PREFIX}/sensores/+", 1), (f"{PREFIX}/estado/+", 1)])
            self.app.logger.info("MQTT conectado")
        else:
            self.last_error = "Broker rechazó la conexión"

    def on_disconnect(self, client, userdata, flags, reason_code, properties):
        self.connected = False
        self.app.logger.warning("MQTT desconectado; actuadores sujetos a watchdog local")

    def on_connect_fail(self, client, userdata):
        self.connected = False
        self.last_error = "No se pudo conectar al broker"
        self.app.logger.warning(self.last_error)

    def on_message(self, client, userdata, message):
        try:
            if message.retain or len(message.payload) > 4096:
                raise ValueError("Mensaje retenido o demasiado grande")
            payload = json.loads(message.payload)
            with self.app.app_context():
                if message.topic.startswith(f"{PREFIX}/sensores/"):
                    reading = store_reading(payload, message.topic.rsplit("/", 1)[1])
                    if reading:
                        self.app.logger.debug("Lectura MQTT %s id=%s", message.topic, reading["id"])
                        if self.on_reading:
                            self.on_reading(reading)
                elif message.topic == f"{PREFIX}/estado/{self.app.config['CONTROL_DEVICE_ID']}":
                    output = number(payload.get("output"), "output", -40, 40)
                    with get_db() as db:
                        for name, value in [("ph_plus", max(output, 0)), ("ph_minus", max(-output, 0))]:
                            db.execute("UPDATE actuators SET reported_output=?,reported_at=? WHERE name=?", (value, utcnow(), name))
        except Exception as exc:
            self.last_error = type(exc).__name__
            self.app.logger.warning("Mensaje MQTT rechazado: %s", type(exc).__name__)

    def publish(self, topic, payload):
        if not self.connected:
            raise RuntimeError("MQTT desconectado")
        # Comandos efímeros: QoS 0, sin retención ni cola offline.
        result = self.client.publish(topic, json.dumps(payload, allow_nan=False), qos=0, retain=False)
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            raise RuntimeError("El broker no aceptó el comando")

    def tick(self):
        while not self.stop_event.wait(1):
            try:
                with self.app.app_context():
                    if self.controller:
                        self.controller.tick()
                    with get_db() as db:
                        db.execute("INSERT INTO service_samples(timestamp,mqtt_connected,sensor_fresh) VALUES (?,?,?)",
                                   (utcnow(), int(self.connected), int(bool(self.controller and self.controller.fresh))))
            except Exception:
                self.app.logger.exception("Fallo de ciclo; los comandos caducan en el receptor")

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=5)
        if self.connected:
            try:
                self.publish(f"{PREFIX}/control/ph", {"device_id": self.app.config["CONTROL_DEVICE_ID"],
                             "output": 0, "ttl": 0, "timestamp": utcnow(), "command_id": uuid.uuid4().hex})
            except RuntimeError:
                pass
        self.client.disconnect()
        self.client.loop_stop()
