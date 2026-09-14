# Sistema local de monitoreo hidropónico

Prototipo académico para la tesis de Alejandro Peralta. El trabajo continúa sobre
la base Flask existente: ahora incluye el sistema interno destinado a Raspberry Pi,
inicialmente ejecutado en la computadora con sensores y actuadores simulados.
La pantalla inicial anterior se conserva en `/landing`.

**Implementado:** adquisición MQTT, SQLite, seis variables, panel con actualización
cada 2 segundos, históricos y CSV, alertas, PID de pH con lazo cerrado, OpenCV,
login y roles, auditoría, respaldo, firmware de simulación y pruebas.
No se han validado sensores, bombas, webcam física ni Raspberry Pi real.

## Arquitectura sencilla

```text
Simulador Python o ESP32/Wokwi → Mosquitto → Python (paho-mqtt)
                                             ↓
                              validación → SQLite → Flask/Jinja
                                             ↓           ↓
                                   alertas y PID     navegador
                                             ↓
                           MQTT → actuadores simulados → pH

Imágenes locales / webcam del servidor → OpenCV → SQLite + panel
```

Un único proceso `run.py` inicia Flask, el cliente MQTT y el ciclo de control. El
simulador es otro proceso y Mosquitto es el broker local. La factoría `create_app`
no inicia hilos: sirve para pruebas y comandos CLI. No ejecutar varios `run.py`
contra la misma instalación: cada unidad tiene un solo controlador.

## Wokwi gratuito y hardware propio

Ya hay perfiles independientes: `local` (5000), `wokwi` (5001) y `hardware`
(5002, solo monitoreo). Para preparar el circuito gratuito:

```bash
python scripts/prepare_wokwi.py
python run.py --profile wokwi
```

Los archivos para el editor se generan en `data/wokwi/`, sin cuentas ni imágenes.
El perfil gratuito usa un broker público con topics únicos para datos sintéticos.
La demo local conserva Mosquitto propio. Seguir la
[guía de Wokwi gratuito y transición a hardware](docs/WOKWI_GRATUITO.md).

## 1. Preparar Python

Recomendado Python 3.11/3.12; probado aquí con Python 3.9.6 en macOS ARM64.
Para Raspberry Pi, preferir Raspberry Pi OS **64 bits** por los paquetes OpenCV.

macOS/Linux, desde este directorio:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
cp .env.example .env
python -c "import secrets; print(secrets.token_hex(32))"
```

Windows PowerShell:

```powershell
py -3 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
python -c "import secrets; print(secrets.token_hex(32))"
```

Pegar la clave generada en `SECRET_KEY` de `.env`. No subir `.env` ni claves a Git.
Si queda vacía se genera una clave efímera y las sesiones se invalidan al reiniciar.
`requirements.txt` basta para ejecución; `requirements-dev.txt` agrega pytest.
Bootstrap y Chart.js se sirven desde `app/static/vendor`, sin CDN en ejecución.

## 2. Mosquitto local

- macOS: `brew install mosquitto`.
- Debian/Ubuntu/Raspberry Pi OS: `sudo apt install mosquitto mosquitto-clients`.
- Windows: instalar desde [Eclipse Mosquitto](https://mosquitto.org/download/).

En una terminal, desde la raíz del proyecto:

```bash
mosquitto -c deploy/mosquitto.conf
```

En Homebrew puede requerirse la ruta
`/opt/homebrew/opt/mosquitto/sbin/mosquitto`. En Windows, usar la ruta al ejecutable
instalado. La configuración de demo escucha **solo en 127.0.0.1:1883** y permite
clientes locales sin contraseña. Si ya existe un servicio escuchando en ese puerto,
utilizar ese broker configurado o cambiar tanto su listener como `MQTT_PORT`.

Para un ESP32 físico, configurar un listener en la IP LAN del equipo, poner
`allow_anonymous false`, crear usuarios con `mosquitto_passwd` y configurar
`password_file` y ACL por dispositivo. Completar `MQTT_USERNAME` y `MQTT_PASSWORD`
en `.env` y firmware. No publicar el broker en Internet. El listener de demo
incluido deliberadamente no acepta conexiones de otras máquinas.

## 3. Base y usuarios

La base se crea automáticamente sin borrar datos anteriores. También:

```bash
python -m flask --app app:create_app init-db
python -m flask --app app:create_app create-user --username admin --role ADMIN
python -m flask --app app:create_app create-user --username operador --role OPERADOR
```

Los comandos solicitan una contraseña de 12 a 128 caracteres sin mostrarla, con
confirmación. **No hay contraseña predeterminada ni cuentas creadas automáticamente.**
Las cuentas de pruebas existen solo en bases temporales de pytest.

ADMIN gestiona PID, perturbaciones, usuarios, rangos, auditoría, métricas y respaldo.
OPERADOR consulta panel, sensores, históricos, alertas y procesa imágenes.
Login usa sesiones de 8 horas, hash PBKDF2-SHA256 (1 millón de iteraciones),
validación CSRF y límite de intentos por usuario. La autorización se comprueba
además en la API y URLs directas. Logout es POST.

## 4. Ejecutar la demostración

Con Mosquitto iniciado y `SIMULATION_ENABLED=true`, en otra terminal:

```bash
source .venv/bin/activate
python run.py
```

En una tercera terminal:

```bash
source .venv/bin/activate
python simulator.py
```

Abrir **http://localhost:5000**, iniciar sesión y observar las seis variables.
En Windows, usar la activación PowerShell del paso 1 en cada terminal.

Para demostrar control:

1. Entrar a `/control` como ADMIN. El inicio siempre es manual.
2. Activar automático con el setpoint inicial 6.2.
3. Introducir perturbación de pH `+0.8`.
4. Observar alerta HIGH, PH_MINUS solicitado y reportado, descenso de pH,
   resolución de alerta y estabilización en la banda ±0.03.
5. Probar parada de emergencia. Rearmar vuelve a manual; no activa dosificación.
6. Con nivel de depósito <25 %, datos de pH/nivel antiguos o MQTT desconectado,
   la salida queda en cero. El receptor también apaga al caducar el comando.

Terminar cada proceso con Ctrl+C. El servidor de desarrollo se usa para el
prototipo local. El reloader está desactivado para no duplicar el consumidor PID.

## Configuración

| Variable | Función |
| --- | --- |
| SECRET_KEY | Firma de sesiones, estable y privada |
| DATABASE_PATH | SQLite; relativa a la raíz del proyecto o absoluta |
| HOST / PORT | Dirección web; por defecto 127.0.0.1:5000 |
| HYDRO_DEBUG | Depurador, false por defecto |
| LOG_LEVEL | INFO; DEBUG agrega cada lectura y ciclo PID |
| SIMULATION_ENABLED | Habilita simulador y perturbaciones; no lo inicia |
| MQTT_HOST / MQTT_PORT | Broker local |
| MQTT_USERNAME / MQTT_PASSWORD | Credenciales; obligatorias en perfil hardware |
| MQTT_TOPIC_PREFIX | Namespace de la instalación; aleatorio en Wokwi público |
| MQTT_TLS / MQTT_CA_FILE | TLS verificado y CA local del broker propio |
| HYDRO_PROFILE | local, wokwi o hardware (también --profile en run.py) |
| CONTROL_DEVICE_ID | Único dispositivo de control: simulator-01 o esp32-01 |
| CAMERA_INDEX | Webcam del servidor; 0 por defecto |

Los parámetros PID y los rangos operativos se guardan en SQLite, no en `.env`.
Las variables del entorno prevalecen sobre `.env`. Booleanos: true/false/1/0.

El simulador admite `--seed 42`, `--interval 1` y `--config ruta.json`. El JSON
contiene las seis claves de `DEFAULT_VARIABLES` en
`app/services/simulation_service.py`, cada una con `initial`, `min`, `max`, `noise`
y `unit`. El pH no retorna artificialmente al setpoint: cambia por dosificación y
ruido gradual. TDS es ppm aproximado; no se convierte a EC sin calibración.

## Pantallas y API

Pantallas: `/login`, `/dashboard`, `/sensors`, `/history`, `/alerts`, `/control`,
`/vision`, `/settings`, `/users`, `/audit`. `/landing` conserva la pantalla previa.

| Método | Ruta | Acceso |
| --- | --- | --- |
| GET | /api/health | Público: solo estado técnico |
| GET | /api/sensors/latest, /api/sensors/types | Autenticado |
| GET | /api/sensors/history/ph?start=...&end=...&limit=1000 | Autenticado |
| GET | /api/sensors/history/ph?format=csv&limit=10000 | Autenticado |
| GET | /api/alerts?status=active o all | Autenticado |
| GET | /api/control/status, /api/control/events | Autenticado |
| POST | /api/control/setpoint | ADMIN: {"setpoint":6.2} |
| POST | /api/control/config | ADMIN: todos los parámetros PID |
| POST | /api/control/mode | ADMIN: {"mode":"automatic"} o manual |
| POST | /api/control/manual | ADMIN: {"output":-15} |
| POST | /api/control/emergency, /api/control/reset | ADMIN: {} |
| POST | /api/simulation/disturbance | ADMIN: {"variable":"ph","delta":0.8} |
| GET | /api/vision, /api/vision/latest, /api/vision/files | Autenticado |
| POST | /api/vision/analyze | Autenticado: {"filename":"planta.jpg","roi":null} |
| POST | /api/vision/capture | Autenticado: webcam del servidor |
| POST | /api/settings/ranges | ADMIN: variable, minimum, maximum |
| GET/POST | /api/users | ADMIN: listar/crear |
| GET | /api/audit, /api/metrics | ADMIN |
| POST | /api/backup | ADMIN: descarga SQLite |

La API requiere la cookie de sesión. Las mutaciones requieren `X-CSRF-Token` del
meta `csrf-token` de la página autenticada; no es una API pública sin login.
Los filtros de fecha usan ISO 8601 con zona (ej. `2026-09-06T00:00:00Z`). Las fechas
se guardan en UTC y se muestran localmente en el panel. CSV usa UTC. Cada consulta
limita filas: dividir en intervalos más pequeños si el histórico supera 10000.

## Contrato MQTT

Topics `hidroponia/sensores/{variable}` con variable:
`ph`, `tds`, `temperatura_agua`, `temperatura_ambiente`, `humedad`, `nivel`.

```json
{
  "device_id": "simulator-01",
  "variable": "ph",
  "value": 6.34,
  "unit": "pH",
  "timestamp": "2026-09-06T18:30:00Z",
  "message_id": "identificador-unico-por-medicion",
  "source": "simulator"
}
```

Unidades exactas: pH, ppm, °C, °C, %, %. Fuentes: simulator, wokwi o esp32.
Sin message_id se deduplica por variable y timestamp del dispositivo. Se rechazan
valores no finitos, unidades incorrectas, payloads >4096 bytes, mensajes retenidos
y fechas fuera de la ventana de recepción (24 horas atrás, 5 s en futuro).
Las lecturas viejas pueden quedar en histórico pero no habilitan control.

Control: `hidroponia/control/ph`, con device_id, output firmado (-40..40), ttl
(máximo 3 segundos), timestamp y command_id. Los comandos usan QoS 0 y sin
retención para evitar dosificaciones retrasadas tras una reconexión. Los mensajes
`hidroponia/actuadores/ph_plus` y `ph_minus` publican la salida solicitada;
`hidroponia/estado/{device_id}` informa la salida aplicada por el simulador.
`nutrientes` y `agua` están registrados pero no automatizados; no hay PID de TDS.
El simulador Python publica lecturas QoS 1; PubSubClient en ESP32 publica QoS 0.

## PID y límites

`u = Kp·error + Ki·integral(error·dt) − Kd·Δmedición/dt`, con saturación y
anti-windup condicional. Derivar la medición evita el salto derivativo al cambiar
setpoint. La banda ±0.03 pH detiene la salida y reinicia la integral.

Positivo aumenta pH, negativo reduce pH. Por defecto: Kp=35, Ki=0.2, Kd=1,
salida máxima=40 %, muestreo=1 s, máximo continuo=45 s, dosis máxima=12 segundos
equivalentes al 100 % en una ventana de 60 s. El presupuesto considera el TTL del
próximo comando. No representa mililitros: falta calibrar caudal de una bomba real.
El presupuesto reciente se persiste para que reiniciar no lo borre.

Solo el `CONTROL_DEVICE_ID` habilita control, con pH y nivel medidos hace <5 s.
Hay pulso manual de hasta 3 s, modo automático, emergencia enclavada y apagado por
watchdog en el receptor. Al reiniciar queda manual; la emergencia persiste.
La sintonía es exclusivamente para la planta matemática, no para hardware real.

## OpenCV

Colocar JPG/PNG en `data/images/`. Para probar sin fotografías:

```bash
python scripts/create_demo_image.py
```

El patrón está explícitamente marcado como sintético. En `/vision`, seleccionar
imagen y ROI opcional `[x,y,ancho,alto]` en coordenadas originales. El pipeline
recorta, redimensiona a máximo 1280 px, convierte BGR→HSV, segmenta verde
(H=35..85, S≥40, V≥40), aplica apertura/cierre 3×3 y detecta contornos.
Guarda área de máscara en píxeles, cobertura, ROI, fecha, parámetros y resultado
en `data/processed/`. La captura usa la webcam del **servidor**, no la del navegador.

La comparación visual debe conservar iluminación, encuadre y ROI. El área es de
la imagen procesada, no cm²; el porcentaje no diagnostica enfermedades. El botón
de webcam requiere cámara disponible y permisos del sistema operativo.

## Datos, respaldo y evidencia

Tablas: users, sensor_types, devices, sensor_readings, alerts, system_parameters,
control_events, actuators, visual_analysis, audit_log, web_metrics, service_samples
y schema_migrations. Índices históricos, claves foráneas y WAL habilitados.
El esquema base se conserva y la versión 2 agrega el dominio sin borrar datos.

Desde Configuración, descargar respaldo usando la API de backup de SQLite, que
incluye datos comprometidos en WAL. Incluye hashes de usuarios: guardarlo de forma
privada. Para restaurar, detener todos los procesos y configurar DATABASE_PATH
hacia el archivo restaurado. El respaldo de SQLite no incluye fotografías: copiar
`data/images` y `data/processed` por separado.

Se miden recepción, tiempo del primer commit de lectura, eventos PID y latencias
web del backend. No confundir las muestras mientras el proceso vive con
**disponibilidad total**, ni la latencia del servidor con carga visual completa.
Ver [trazabilidad de la tesis](docs/REQUISITOS_TESIS.md) y
[validación registrada](docs/VALIDACION.md).

## ESP32 / Wokwi

En `firmware/esp32` se incluyen `.ino`, diagrama de seis potenciómetros y dos LEDs,
bibliotecas, `platformio.ini`, `wokwi.toml` y `hidroponia_config.example.h`. Copiar este último
a `hidroponia_config.h` si se necesitan ajustes privados. Configurar backend con
`CONTROL_DEVICE_ID=esp32-01`, detener simulador Python y reiniciar backend.

- pH→GPIO34, TDS→35, agua °C→32, ambiente °C→33, humedad→36, nivel→39.
- LEDs PH_PLUS→18 y PH_MINUS→19, cada uno con resistencia de 220 Ω.
- Los potenciómetros generan entradas; el pH además integra la acción del PID.
- WiFi/NTP deben sincronizarse antes de publicar. Todos los comandos caducan.

Firmware compilado localmente con éxito (RAM 14.2 %, flash 60.4 %).
Compilar con PlatformIO (`python -m pip install platformio==6.1.18`):

```bash
pio run -d firmware/esp32
```

En Wokwi web, crear ESP32, copiar el contenido del `.ino` a `sketch.ino` y agregar
`diagram.json`, `libraries.txt`, `hidroponia_config.example.h`. Para VS Code, usar el binario
generado con `wokwi.toml`.

**Conectividad gratuita:** ejecutar `scripts/prepare_wokwi.py` y usar los archivos
que genera en `data/wokwi/`. Ambos extremos se conectan al broker público de pruebas
HiveMQ, sin gateway privado. Cada instalación tiene un prefijo único; eso evita
mezclas accidentales, pero no brinda privacidad ni autentica mensajes. Solo datos
sintéticos y LEDs. No enviar credenciales ni conectar actuadores reales.

La conexión directa desde Wokwi al Mosquitto de tu PC sigue requiriendo el gateway
privado (opción paga); ya no es requisito de la demostración Wokwi gratuita.
Detalles, prueba de conexión y cambio de broker en
[docs/WOKWI_GRATUITO.md](docs/WOKWI_GRATUITO.md).

## Raspberry Pi: migración

1. Instalar Raspberry Pi OS 64 bits, Python/venv y Mosquitto. Sin sensores todavía,
   usar el mismo simulador y probar el recorrido local.
2. Copiar código a `/opt/hidroponia`, crear allí un venv nuevo e instalar requisitos.
   No copiar el venv de macOS/Windows.
3. Crear usuario de servicio `hidroponia`, dar permisos de escritura sobre `data/`,
   configurar `.env` y crear la cuenta ADMIN por CLI.
4. Verificar manualmente `python run.py`. Para acceso desde otro dispositivo de
   la LAN, configurar HOST=0.0.0.0 y restringir el acceso a esa LAN.
5. Opcional: adaptar `deploy/hidroponia.service` a las rutas/usuario reales,
   copiarlo a `/etc/systemd/system/`, ejecutar `sudo systemctl daemon-reload` y
   `sudo systemctl enable --now hidroponia`. Ver logs con
   `journalctl -u hidroponia -f`. Se ejecuta una sola instancia.
6. Luego conectar ESP32 a un broker LAN autenticado, definir CONTROL_DEVICE_ID,
   mantener inicialmente modo manual y sustituir potenciómetros por sensores
   calibrados. La cámara USB puede usar OpenCV; cámaras CSI pueden necesitar un
   adaptador de captura específico de Raspberry Pi OS.

El montaje físico requiere fuentes adecuadas, etapa de potencia/relés aislados,
protección frente al agua, calibración de sensores y límites de dosis medidos.
El firmware incluido solo maneja LEDs. La incorporación de bombas reales requiere
validación específica; no está habilitada por este prototipo.

## Pruebas

```bash
python -m pytest -q
python -m compileall -q app config.py run.py simulator.py
node --check app/static/js/system.js
python scripts/verify_integration.py
```

La integración levanta un broker y servidor en puertos locales temporales,
crea una base/cuenta temporal, ejecuta el simulador, prueba alerta→PID→corrección,
CSV, concurrencia breve, emergencia y nivel bajo, y detiene sus procesos.
No usa datos ni cuentas de la instalación habitual.

Opcional, con Google Chrome instalado y `pip install playwright==1.55.0`:
`python scripts/verify_integration.py --browser` verifica también la interfaz.
Los paquetes de herramientas no son necesarios para ejecutar el prototipo.

## Organización

- `app/models`: esquema y consultas parametrizadas.
- `app/services`: simulación, MQTT, alertas, PID, visión.
- `app/routes`: autenticación, pantallas, sensores, alertas, control, visión y administración.
- `app/templates`, `app/static`: interfaz Jinja, CSS/JS y librerías locales.
- `simulator.py`, `run.py`: procesos de demostración.
- `firmware/esp32`, `deploy`: simulación embebida y despliegue local.
- `tests`, `scripts`, `docs`: comprobaciones y evidencias.

Las fases se implementaron incrementalmente sobre la base inicial, verificando
almacenamiento, simulación, MQTT, consultas, alertas, PID, visión y autenticación.
La validación sobre hardware y la campaña experimental de la tesis siguen pendientes.

## Experimento ML opcional con HydroGrowNet

El entrenamiento reproducible, la evaluación por experimentos separados y sus
limitaciones están en [docs/ml/README.md](docs/ml/README.md). Es una regresión
exploratoria del día relativo del experimento a partir de imágenes segmentadas;
no es diagnóstico ni modifica el PID o la visión OpenCV del panel.

## Respaldo y configuración para compartir por Git

Usar [`.env.git.example`](.env.git.example) como plantilla sin credenciales y
seguir [la guía de restauración](backups/shared/README.md). Las exportaciones
compartibles contienen telemetría simulada sanitizada; las copias completas
privadas permanecen en `data/backups/`, fuera de Git.
