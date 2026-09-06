# Verificación local — 6 de septiembre de 2026

Entorno: macOS ARM64, Python 3.9.6, Flask 3.1.2, paho-mqtt 2.1.0,
OpenCV headless 4.12, Mosquitto local. Ningún sensor ni bomba física conectado.

## Comprobaciones realizadas

- `python -m pytest -q`: 32 pruebas aprobadas.
- Compilación de módulos Python y sintaxis JavaScript correctas.
- `pip check`: sin requisitos incompatibles.
- Firmware ESP32 compilado correctamente: RAM 46520 bytes (14.2 %), flash
  791409 bytes (60.4 %), binario `.pio/build/esp32dev/firmware.bin`.
- `python scripts/verify_integration.py --browser`: aprobado.
- Chrome: login y panel; históricos, PID, visión, configuración, usuarios y
  auditoría sin errores JavaScript. Sin desbordamiento horizontal en 1440×1000,
  768×1024 y 390×844. La captura es de la prueba sintética, no de un cultivo real.

## Recorrido MQTT + HTTP registrado

| Medida | Resultado |
| --- | --- |
| pH inicial | 6.2008 |
| pH tras perturbación | 7.0032 |
| pH corregido | 6.2419 |
| Tiempo hasta pH <6.25 | 26.26 s |
| Lecturas únicas recibidas | 246 |
| Tiempo medio de recepción respecto al timestamp productor | 10.39 ms |
| Tiempo medio hasta commit de lectura | 1.69 ms |
| Tres solicitudes web simultáneas autenticadas | 6.50 / 4.20 / 4.15 ms |
| Alertas | pH alto y nivel bajo generadas; pH resuelta |
| Parada de emergencia y bloqueo por nivel bajo | Aprobados |

La captura [dashboard.png](evidence/dashboard.png) muestra el estado posterior al
ensayo de nivel bajo, con salida cero y alerta de depósito. El histórico conserva
la perturbación y la corrección de pH anteriores.

Estos tiempos son una observación breve en computadora, no resultados finales en
Raspberry Pi. El muestreo interno no mide caídas del propio proceso. No se afirma
cumplimiento del 95 % de disponibilidad, pérdida <5 %, tiempos web de extremo a
extremo ni mejora productiva del cultivo.

## Pendientes físicos

- Ejecución del firmware dentro de Wokwi con gateway y broker accesibles.
- Instalación en Raspberry Pi OS, cámara física y sincronización de relojes.
- Calibración de pH/TDS, montaje eléctrico, caudal real y dosis en mililitros.
- Pruebas prolongadas según RNF, con sonda externa y conteo de emisiones esperadas.
- Evaluación de interfaz por operadores y comparación de fotografías reales con
  encuadre, luz y ROI constantes.
