# Wokwi gratuito y transición a hardware propio

## Tres perfiles independientes

| Perfil | Arranque | Broker | Base por defecto | Puerto web |
| --- | --- | --- | --- | --- |
| local | `python run.py` | Mosquitto propio local | hidroponia.sqlite3 | 5000 |
| wokwi | `python run.py --profile wokwi` | HiveMQ público de pruebas | hidroponia-wokwi.sqlite3 | 5001 |
| hardware | `python run.py --profile hardware` | Propio, con TLS y credenciales | hidroponia-hardware.sqlite3 | 5002 |

Cada perfil lee su archivo `.env`, `.env.wokwi` o `.env.hardware`.
Los procesos no modifican el entorno de los otros perfiles. No mezclar variables
DATABASE_PATH/MQTT_* exportadas en la terminal con perfiles diferentes: las
variables del entorno tienen prioridad. El panel muestra el perfil activo.

## Preparar el modo gratuito

Desde el proyecto, con el entorno virtual activado:

```bash
python scripts/prepare_wokwi.py
python run.py --profile wokwi
```

El primer comando crea:

- `.env.wokwi`: configuración local, clave de sesión y prefijo MQTT aleatorio.
- `data/wokwi/`: archivos listos para copiar al editor de Wokwi.
- `data/wokwi/wokwi-gratuito.zip`: paquete de esos mismos archivos.
- Una base Wokwi independiente con las cuentas locales existentes (solo se copian
  hashes dentro de tu computadora, nunca al ZIP). La contraseña de `demo.admin`
  sigue siendo la que ya elegiste/recibiste. Si no existe ninguna cuenta, crearla
  primero en el perfil local y repetir la preparación.

Repetir el comando conserva el prefijo y la clave existentes, actualiza el paquete
con el firmware actual e importa solamente cuentas que aún no existen. Cambiar la
contraseña de una cuenta ya importada no la sincroniza entre bases.

El paquete no contiene `.env`, contraseñas del panel, SQLite, fotografías ni datos
personales. Los archivos se generan a partir de una lista explícita. No subir el
repositorio completo a Wokwi.

## Abrir el circuito

1. Abrir <https://wokwi.com/projects/new/esp32> con Wokwi gratuito.
2. Copiar `data/wokwi/sketch.ino` al `sketch.ino` del editor.
3. Reemplazar el contenido de `diagram.json` con el archivo generado.
4. Agregar `hidroponia_config.h` y `hidroponia_config.example.h` al proyecto.
5. Instalar **PubSubClient 2.8** y **ArduinoJson 7.4.2** desde Library Manager,
   o usar el `libraries.txt` generado si el editor permite agregarlo.
6. Iniciar la simulación. Usa WiFi `Wokwi-GUEST` y el gateway público, sin activar
   el privado. Esperar sincronización NTP y el mensaje `MQTT conectado` en Serial.
7. Abrir <http://localhost:5001>, ingresar y revisar las seis lecturas.

El ZIP sirve para transportar los archivos; estos pasos no presuponen que Wokwi
permita importar un ZIP directamente. Guardar el proyecto en tu cuenta es opcional
para ejecutar la prueba; facilita recuperarlo después.

No iniciar `simulator.py` para alimentar este perfil: el productor es el ESP32 de
Wokwi. Se puede mantener la demo Python local en 5000 porque los topics y SQLite
son independientes.

## Comprobar el lazo

- Identificar pot0=pH, pot1=TDS, pot2=temperatura del agua, pot3=temperatura
  ambiente, pot4=humedad y pot5=nivel. Los LEDs indican PH_PLUS y PH_MINUS.
- Mantener nivel >25 %, activar automático en `/control` e introducir pH +0.8.
- El firmware recibe la perturbación desde el panel, modifica su modelo de pH,
  publica nuevas lecturas y aplica los comandos PID a LEDs y modelo matemático.
- Comprobar alerta HIGH, descenso de pH, salida OFF y resolución de alerta.
- Probar parada de emergencia y detener Wokwi: el panel debe marcar lecturas
  antiguas y el backend dejar de dosificar al pasar el plazo de frescura.
- El receptor limita cada comando a 3 s y la actuación continua a 45 s. Wokwi
  puede correr más lento que el reloj real: si hay demoras o desfase NTP, el
  interbloqueo debe mantenerse; no ampliar los límites para ocultar el problema.

## Comprobar la conectividad antes de abrir Wokwi

```bash
python scripts/verify_public_mqtt.py
```

Envía solamente seis valores sintéticos en un prefijo temporal independiente,
verifica almacenamiento SQLite y recepción de un comando OFF, y cierra los
clientes. **No ejecuta el firmware:** prueba la conectividad PC↔broker público.

La compilación gratuita puede quedar en cola. El 7 de septiembre Wokwi mostró
`Build Servers Busy`; al reintentar el **8 de septiembre de 2026**, el circuito
compiló en Wokwi y se verificaron las seis variables del ESP32 virtual en SQLite.
No se usó el simulador Python para esta comprobación. Si aparece ese mensaje,
reintentar más tarde.

## Generar datos de prueba desde el circuito virtual

Con el backend Wokwi iniciado, ejecutar:

```bash
.venv/bin/python scripts/verify_wokwi_browser.py --visible --minutes 30
```

Requiere Chrome y Playwright instalados. Abre una sesión temporal del editor,
carga el circuito y sus bibliotecas y espera hasta 180 segundos por las seis
variables del dispositivo configurado. Después mantiene el circuito abierto
30 minutos. Se puede detener antes con Ctrl+C; no guarda el proyecto en una
cuenta Wokwi. Sin `--minutes`, solo verifica la llegada inicial y cierra Chrome.

Abrir http://localhost:5001/dashboard con la cuenta local importada. En Históricos
se conservan las lecturas al cerrar el circuito; las tarjetas pasarán a indicar
que no hay lectura reciente. Los gráficos se actualizan cada 10 segundos.

Lecturas iniciales observadas el 8 de septiembre (valores simulados):

| Potenciómetro | Variable | Lectura inicial |
| --- | --- | --- |
| pot0 | pH | 6,150183 |
| pot1 | TDS | 851,5507 ppm |
| pot2 | Temperatura del agua | 22,39365 °C |
| pot3 | Temperatura ambiente | 27,18803 °C |
| pot4 | Humedad | 65,01832 % |
| pot5 | Nivel | 77,99756 % |

Para generar curvas, mover un potenciómetro y observar su lectura. Con los
potenciómetros quietos y sin control, las señales son prácticamente constantes:
no se añade ruido artificial. Para probar bajo nivel, bajar pot5 hasta menos del
25 %; devolverlo luego a su posición inicial. Para probar el PID, seguir
“Comprobar el lazo”. La recepción inicial de seis variables no demuestra por sí
sola que todas las pruebas de actuación del lazo se hayan completado en Wokwi.

Si falla, comprobar acceso saliente TCP 1883 en la red/VPN/firewall. También puede
fallar el servicio público. No abrir puertos entrantes en el router.

Alternativa explícita:

```bash
python scripts/verify_public_mqtt.py --broker test.mosquitto.org
python scripts/prepare_wokwi.py --broker test.mosquitto.org
```

Después de cambiar broker, reiniciar el backend Wokwi y copiar de nuevo el header
al editor. Volver a HiveMQ con `--broker broker.hivemq.com`. No hay cambios de
broker automáticos: ambos extremos deben usar el mismo.

## Alcance de la conexión pública

HiveMQ ofrece un broker público para pruebas temporales sin registro, y Mosquitto
ofrece otro servicio similar. No son una infraestructura propia ni una dependencia
necesaria del producto final. Se usan porque el gateway gratuito de Wokwi llega a
Internet, pero no al Mosquitto de tu red local.

El prefijo aleatorio `hidroponia/demo/<32 caracteres>` reduce colisiones entre
ensayos; **no es autenticación ni privacidad**. Cualquiera con acceso al broker
puede leer o publicar en esos topics. Por eso solo se envían valores sintéticos y
el firmware incluido solo acciona LEDs. Nunca conectar bombas reales a este modo.
El gateway público de Wokwi monitorea tráfico; no incluir credenciales personales.

El backend Wokwi descarta lecturas de otros device_id y fuentes distintas de
`wokwi`. Esto evita mezclas accidentales, pero no autentica a un adversario capaz
de copiar esos campos. Los client IDs MQTT también son independientes por proceso.

Referencias verificadas el 7 de septiembre de 2026:
- [Red y gateway público de Wokwi](https://docs.wokwi.com/guides/esp32-wifi).
- [Broker público gratuito de HiveMQ](https://www.hivemq.com/mqtt/public-mqtt-broker/).
- [Condiciones de test.mosquitto.org](https://test.mosquitto.org/).

## Base para sensores y equipos propios

Copiar `.env.hardware.example` a `.env.hardware`. Configurar broker Mosquitto
propio, puerto TLS, CA de confianza, usuario, contraseña, prefijo de la unidad y
CONTROL_DEVICE_ID. Generar SECRET_KEY propia. No copiar credenciales privadas al
proyecto público de Wokwi. El arranque hardware exige TLS y credenciales, prohíbe
los brokers públicos conocidos y desactiva las perturbaciones.

**El perfil hardware es solo monitoreo.** No se puede habilitar dosificación
cambiando un parámetro de pantalla ni una variable del entorno. Falta implementar
el driver de potencia y calibrarlo antes de añadir una habilitación explícita.
No interpretar el botón de emergencia del panel como un paro eléctrico certificado.

El contrato de sensores sigue siendo:

```json
{"device_id":"esp32-01","source":"esp32","variable":"ph","value":6.2,"unit":"pH","timestamp":"2026-09-07T12:00:00Z","message_id":"unico-por-lectura"}
```

Sustituir `readSimulatedSensor()` del firmware por adaptadores calibrados para
cada sensor, conservar unidades y timestamps UTC y cambiar source a `esp32`.
Separar lectura, conversión/calibración y publicación: no modificar Flask para
cada modelo de sensor. `leds()` y la integración matemática son exclusivamente
simulación; un driver real necesitará temporización no bloqueante, caudal medido,
interbloqueos locales y paro físico independiente de WiFi.

La Raspberry Pi ejecutará el mismo backend y SQLite con el perfil hardware. La
implementación física pendiente incluye certificados del broker, ACL por cliente,
sincronización horaria, calibración y pruebas de fallos. Ver el ejemplo comentado
`deploy/mosquitto-hardware.conf.example`. Usar Raspberry Pi OS 64 bits y adaptar
`deploy/hidroponia.service` para añadir `--profile hardware` al ExecStart.
