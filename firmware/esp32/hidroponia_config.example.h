#pragma once
// Copiar a hidroponia_config.h y ajustar. No guardar credenciales reales en Git.
#define WIFI_SSID "Wokwi-GUEST"
#define WIFI_PASSWORD ""
// host.wokwi.internal requiere gateway privado de Wokwi (ver README).
// En ESP32 físico, colocar la IP LAN de la Raspberry Pi y autenticar Mosquitto.
#define MQTT_HOST "host.wokwi.internal"
#define MQTT_PORT 1883
#define MQTT_USERNAME ""
#define MQTT_PASSWORD ""
#define DEVICE_ID "esp32-01"
#define MQTT_TOPIC_PREFIX "hidroponia"
