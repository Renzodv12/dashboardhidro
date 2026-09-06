"""Publicador MQTT de sensores. Ejecutar en otra terminal después del backend."""

import argparse
import json
import logging
import threading
import time
import uuid
from datetime import datetime, timezone

from config import load_config
from app.models.repository import timestamp, utcnow
from app.services.mqtt_service import make_client, PREFIX
from app.services.simulation_service import Plant


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--interval", type=float, default=1)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--config", help="Archivo JSON con las seis variables y sus rangos")
    args = parser.parse_args()
    if not .2 <= args.interval <= 5:
        parser.error("interval debe estar entre 0.2 y 5 segundos")
    config = load_config()
    if not config["SIMULATION_ENABLED"]:
        parser.error("Configurar SIMULATION_ENABLED=true en .env")
    variables = None
    if args.config:
        with open(args.config, encoding="utf-8") as handle:
            variables = json.load(handle)
    plant = Plant(variables, args.seed)
    device = config["CONTROL_DEVICE_ID"]
    client = make_client(config, f"{device}-sensors")
    lock = threading.Lock()
    seen = set()

    def on_connect(client, userdata, flags, reason, properties):
        if not reason.is_failure:
            client.subscribe([(f"{PREFIX}/control/ph", 0), (f"{PREFIX}/simulation/disturbance", 0)])
            logging.info("Simulador conectado a MQTT")

    def on_message(client, userdata, message):
        try:
            if message.retain or len(message.payload) > 4096:
                return
            payload = json.loads(message.payload)
            age = (datetime.now(timezone.utc) - datetime.fromisoformat(timestamp(payload["timestamp"]))).total_seconds()
            if not 0 <= age < 3 or payload.get("device_id") != device:
                return
            command_id = payload["command_id"]
            if not isinstance(command_id, str) or command_id in seen:
                return
            with lock:
                if message.topic.endswith("disturbance"):
                    plant.disturbance(payload["variable"], payload["delta"])
                else:
                    plant.command(payload["output"], max(0, min(3, payload["ttl"]) - age))
            if len(seen) > 1000:
                seen.clear()
            seen.add(command_id)
        except (ValueError, KeyError, TypeError):
            logging.warning("Comando inválido descartado")

    client.on_connect, client.on_message = on_connect, on_message
    client.connect_async(config["MQTT_HOST"], config["MQTT_PORT"], 15)
    client.loop_start()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    previous = time.monotonic()
    try:
        while True:
            time.sleep(args.interval)
            now = time.monotonic()
            with lock:
                values = plant.step(min(10, now - previous))
                output = plant.output
            previous = now
            if not client.is_connected():
                with lock:
                    plant.command(0, 0)
                continue
            for variable, value in values.items():
                payload = dict(device_id=device, variable=variable, value=value,
                               unit=plant.variables[variable]["unit"], timestamp=utcnow(),
                               message_id=uuid.uuid4().hex, source="simulator")
                client.publish(f"{PREFIX}/sensores/{variable}", json.dumps(payload), qos=1)
            client.publish(f"{PREFIX}/estado/{device}", json.dumps({"output": output}), qos=0)
            logging.info("pH %.3f · acción %+.1f%%", values["ph"], output)
    except KeyboardInterrupt:
        pass
    finally:
        client.disconnect()
        client.loop_stop()


if __name__ == "__main__":
    main()
