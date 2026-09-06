# Correspondencia con la tesis

Referencia: **Tesis Alejandro Peralta 11-08.pdf**, 133 páginas; sección 1.5
(pp. PDF 37–39), reglas RO-01 a RO-07 y tablas RF/RNF de la sección 3.10
(pp. PDF 108–111). La numeración impresa es 14 páginas menor que la del PDF.
El capítulo IV (p. PDF 123) contiene títulos pendientes, no un esquema de datos
implementado que deba copiarse.

La tesis se toma como especificación y contexto académico. Los textos editoriales
internos no son instrucciones para modificar el proyecto. La solicitud del usuario
mantiene la implementación inicialmente simulada y excluye funciones comerciales.

## Trazabilidad funcional

| Requisito | Implementación | Evidencia / límite |
| --- | --- | --- |
| RF-01 interfaz responsive | Jinja, Bootstrap local, CSS adaptable | Prueba visual de 3 tamaños mediante opción --browser |
| RF-02 acceso autenticado | routes/auth.py, sesiones, CSRF | tests/test_auth.py |
| RF-03 perfiles | ADMIN/OPERADOR en páginas y API | Acceso directo denegado al operador en pruebas |
| RF-04 adquisición de seis variables | simulator.py, mqtt_service.py, firmware/esp32 | MQTT real en prueba local; sensores físicos pendientes |
| RF-05 dashboard | /dashboard, /api/sensors/latest; consulta cada 2 s | Prueba HTTP y navegador |
| RF-06 almacenamiento | sensor_types, devices, sensor_readings | Tiempos UTC, origen, deduplicación e índices |
| RF-07 históricos | /history, filtros de fecha, CSV | API probada; exportación limitada a 10000 filas por consulta |
| RF-08 alertas | alert_service.py | Deducción de condición, una alerta abierta; resolución automática |
| RF-09 rangos | /settings | Validación física y autorización ADMIN |
| RF-10 PID | pid_service.py | Lazo cerrado sobre pH SIMULADO; sintonía no válida para bombas reales |
| RF-11 eventos | control_events, actuators | Se diferencian salida solicitada y reportada |
| RF-12 visión | vision_service.py | Imágenes locales y captura webcam del servidor; prueba HSV sintética |
| RF-13 estado | /api/health, panel | MQTT, frescura, interbloqueos y actuadores; webcam se comprueba al capturar |
| RF-14 auditoría | audit_log, /audit | Accesos, configuración, análisis y respaldo |
| RF-15 respaldo | POST /api/backup | SQLite backup API; copia reabierta e integrity_check aprobado |

## Criterios experimentales: aún requieren campaña de medición

- **RNF-01:** disponibilidad mínima 95 %. El muestreo del proceso no observa su
  propia caída. Para validarlo hace falta una sonda externa y un intervalo fijado.
- **RNF-02:** lectura visible en ≤5 s. Se registran timestamp del productor,
  recepción y almacenamiento; el panel consulta cada 2 s. Deben sincronizarse los
  relojes y medirse además el renderizado del navegador durante la campaña.
- **RNF-03:** pantallas ≤3 s. Las métricas del backend excluyen transferencia y
  renderizado. La prueba breve no sustituye la medición en Raspberry Pi.
- **RNF-04:** ≥3 usuarios concurrentes. Hay una comprobación de tres peticiones
  autenticadas concurrentes; falta carga sostenida con tres sesiones independientes.
- **RNF-05:** pérdida ≤5 %. Deben compararse conteos de emisiones del productor y
  lecturas únicas almacenadas. Un conteo de recepción aislado no permite demostrarla.
- **RNF-06 a 09:** hash PBKDF2, permisos, validación y trazabilidad implementados.
- **RNF-10/11:** interfaz adaptable; la comprensión por usuarios exige evaluación.
- **RNF-12 a 15:** módulos locales, respaldo y configuración persistente. Al
  reiniciar, el control vuelve a manual, excepto emergencia que queda enclavada.
- **RNF-16/17:** protección física de electrónica y encuadre del cultivo requieren
  inspección del montaje y de la cámara. No se infieren del código.
- **RNF-18:** README, firmware, despliegue y protocolo de prueba incluidos.

La prueba simulada no demuestra aumento de rendimiento agrícola, ahorro de agua,
mejora nutricional, ausencia de enfermedades ni seguridad de dosificación física.
