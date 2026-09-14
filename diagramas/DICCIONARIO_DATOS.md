# Diccionario de datos

Este documento describe las tablas y columnas del modelo SQLite usado por el
sistema hidroponico. La fuente tecnica del esquema esta en `app/schema.sql` y
`app/models/domain.sql`.

## Convenciones

- `PK`: clave primaria.
- `FK`: clave foranea.
- `UQ`: valor unico.
- Las fechas se almacenan como texto en formato ISO/UTC para facilitar lectura,
  ordenamiento y exportacion.
- Los campos `*_json` guardan estructuras JSON serializadas.

## schema_migrations

Registra las migraciones aplicadas a la base de datos.

Ejemplo de uso: permite saber que ya se aplico la version `2`, correspondiente
al modelo hidroponico y sus evidencias, y evita repetir cambios estructurales.

| Columna | Tipo | Restricciones | Descripcion |
| --- | --- | --- | --- |
| `version` | INTEGER | PK | Numero de version de la migracion aplicada. |
| `description` | TEXT | NOT NULL | Descripcion corta de la migracion. |
| `applied_at` | TEXT | NOT NULL, default UTC | Fecha y hora en que se registro la migracion. |

## users

Guarda las cuentas locales del sistema y su rol de acceso.

Ejemplo de uso: almacena un usuario administrador que puede configurar el PID y
un operador que solo consulta monitoreo, historicos, alertas y vision.

| Columna | Tipo | Restricciones | Descripcion |
| --- | --- | --- | --- |
| `id` | INTEGER | PK | Identificador interno del usuario. |
| `username` | TEXT | NOT NULL, UQ | Nombre de usuario para iniciar sesion. |
| `password_hash` | TEXT | NOT NULL | Hash de la contrasena; no almacena texto plano. |
| `role` | TEXT | NOT NULL, `ADMIN` u `OPERADOR` | Rol usado para permisos de pantallas y API. |
| `active` | INTEGER | NOT NULL, default `1`, valores `0` o `1` | Indica si la cuenta puede iniciar sesion. |
| `created_at` | TEXT | NOT NULL | Fecha de creacion de la cuenta. |

## sensor_types

Define las variables medidas y sus rangos fisicos y operativos.

Ejemplo de uso: define que el pH trabaja entre `5.5` y `6.5`; si una lectura
queda fuera de ese rango, el sistema puede generar una alerta.

| Columna | Tipo | Restricciones | Descripcion |
| --- | --- | --- | --- |
| `id` | INTEGER | PK | Identificador del tipo de sensor. |
| `variable` | TEXT | NOT NULL, UQ | Codigo interno de la variable, por ejemplo `ph` o `tds`. |
| `label` | TEXT | NOT NULL | Nombre visible de la variable en la interfaz. |
| `unit` | TEXT | NOT NULL | Unidad de medida mostrada al usuario. |
| `physical_min` | REAL | NOT NULL | Valor minimo fisicamente aceptable. |
| `physical_max` | REAL | NOT NULL | Valor maximo fisicamente aceptable. |
| `minimum` | REAL | NOT NULL | Umbral operativo minimo recomendado. |
| `maximum` | REAL | NOT NULL | Umbral operativo maximo recomendado. |

Restriccion: `physical_min <= minimum < maximum <= physical_max`.

Valores iniciales:

| id | variable | label | unit | rango operativo |
| --- | --- | --- | --- | --- |
| 1 | `ph` | pH | pH | 5.5 a 6.5 |
| 2 | `tds` | Nutrientes / TDS | ppm | 500 a 1200 |
| 3 | `temperatura_agua` | Temperatura del agua | C | 18 a 26 |
| 4 | `temperatura_ambiente` | Temperatura ambiente | C | 18 a 32 |
| 5 | `humedad` | Humedad ambiente | % | 40 a 80 |
| 6 | `nivel` | Nivel del deposito | % | 25 a 100 |

## devices

Identifica el origen de las lecturas recibidas por MQTT o simulacion.

Ejemplo de uso: diferencia si las lecturas vienen del simulador local, de Wokwi
o de un futuro ESP32 fisico conectado al prototipo.

| Columna | Tipo | Restricciones | Descripcion |
| --- | --- | --- | --- |
| `id` | TEXT | PK | Identificador del dispositivo o simulador. |
| `source` | TEXT | NOT NULL | Origen de los datos, por ejemplo `simulator`, `wokwi` o `hardware`. |
| `last_seen` | TEXT | NOT NULL | Ultima fecha en que el dispositivo envio datos. |

## sensor_readings

Almacena cada medicion recibida desde un dispositivo.

Ejemplo de uso: guarda que el dispositivo `wokwi-demo-1` envio una lectura de
pH `6.12`, junto con la hora medida, recibida y almacenada.

| Columna | Tipo | Restricciones | Descripcion |
| --- | --- | --- | --- |
| `id` | INTEGER | PK | Identificador interno de la lectura. |
| `sensor_type_id` | INTEGER | NOT NULL, FK a `sensor_types.id` | Variable medida. |
| `device_id` | TEXT | NOT NULL, FK a `devices.id` | Dispositivo que emitio la lectura. |
| `message_id` | TEXT | NOT NULL | Identificador del mensaje recibido; evita duplicados por dispositivo. |
| `value` | REAL | NOT NULL | Valor numerico de la medicion. |
| `measured_at` | TEXT | NOT NULL | Fecha en que el sensor midio el valor. |
| `received_at` | TEXT | NOT NULL | Fecha en que la aplicacion recibio el mensaje. |
| `stored_at` | TEXT | NOT NULL | Fecha en que la lectura quedo almacenada. |
| `transport_ms` | REAL | NOT NULL | Latencia estimada entre medicion y recepcion, en milisegundos. |
| `storage_ms` | REAL | NOT NULL, default `0` | Tiempo estimado de almacenamiento, en milisegundos. |

Restriccion unica: `UNIQUE(device_id, message_id)`.

Indice: `readings_history(sensor_type_id, measured_at, id)` para historicos por
variable y fecha.

## alerts

Registra alertas abiertas o historicas cuando una lectura queda fuera de rango.

Ejemplo de uso: si el nivel del deposito baja de `25%`, se registra una alerta
activa para que el operador pueda verla en el dashboard.

| Columna | Tipo | Restricciones | Descripcion |
| --- | --- | --- | --- |
| `id` | INTEGER | PK | Identificador interno de la alerta. |
| `sensor_type_id` | INTEGER | FK a `sensor_types.id` | Variable asociada a la alerta. |
| `device_id` | TEXT | FK a `devices.id` | Dispositivo asociado a la alerta. |
| `reading_id` | INTEGER | FK a `sensor_readings.id` | Lectura que disparo o actualizo la alerta. |
| `condition` | TEXT | NOT NULL | Condicion detectada, por ejemplo valor bajo o alto. |
| `severity` | TEXT | NOT NULL, `INFO`, `WARNING` o `CRITICAL` | Nivel de severidad. |
| `message` | TEXT | NOT NULL | Mensaje mostrado al usuario. |
| `opened_at` | TEXT | NOT NULL | Fecha de apertura de la alerta. |
| `resolved_at` | TEXT | Nullable | Fecha en que la alerta se resolvio. |
| `acknowledged_at` | TEXT | Nullable | Fecha en que un operador reconocio la alerta. |
| `response_ms` | REAL | Nullable | Tiempo de respuesta estimado para la alerta. |

Indice unico parcial: `alerts_open(sensor_type_id, device_id, condition)` cuando
`resolved_at IS NULL`, para evitar duplicar alertas activas iguales.

## system_parameters

Guarda configuracion dinamica del sistema.

Ejemplo de uso: conserva valores ajustables del controlador PID o limites
operativos sin modificar el codigo fuente de la aplicacion.

| Columna | Tipo | Restricciones | Descripcion |
| --- | --- | --- | --- |
| `key` | TEXT | PK | Nombre de la configuracion. |
| `value_json` | TEXT | NOT NULL | Valor serializado en JSON. |
| `updated_at` | TEXT | NOT NULL | Fecha de la ultima actualizacion. |

Uso esperado: parametros PID, limites operativos y configuracion editable.

## actuators

Representa actuadores logicos controlados por el sistema.

Ejemplo de uso: registra la salida solicitada al actuador `ph_minus` cuando el
controlador necesita corregir un pH alto.

| Columna | Tipo | Restricciones | Descripcion |
| --- | --- | --- | --- |
| `id` | INTEGER | PK | Identificador interno del actuador. |
| `name` | TEXT | NOT NULL, UQ | Nombre logico del actuador. |
| `device_id` | TEXT | Nullable | Dispositivo asociado operativamente. No tiene FK declarada en el esquema actual. |
| `requested_output` | REAL | NOT NULL, default `0` | Salida solicitada por el controlador. |
| `reported_output` | REAL | NOT NULL, default `0` | Salida reportada por el dispositivo. |
| `updated_at` | TEXT | Nullable | Fecha de la ultima orden solicitada. |
| `reported_at` | TEXT | Nullable | Fecha del ultimo reporte del dispositivo. |

Valores iniciales: `ph_plus`, `ph_minus`, `nutrientes`, `agua`.

## control_events

Registra decisiones del controlador PID o acciones manuales de control.

Ejemplo de uso: deja evidencia de que, ante una lectura de pH, el controlador
calculo una salida y genero una accion correctiva con su motivo.

| Columna | Tipo | Restricciones | Descripcion |
| --- | --- | --- | --- |
| `id` | INTEGER | PK | Identificador interno del evento. |
| `timestamp` | TEXT | NOT NULL | Fecha del evento de control. |
| `reading_id` | INTEGER | FK a `sensor_readings.id` | Lectura usada como referencia para la decision. |
| `mode` | TEXT | NOT NULL | Modo de control, por ejemplo automatico o manual. |
| `setpoint` | REAL | NOT NULL | Valor objetivo usado por el controlador. |
| `measured` | REAL | Nullable | Valor medido considerado por el controlador. |
| `error` | REAL | Nullable | Diferencia entre objetivo y valor medido. |
| `output` | REAL | NOT NULL | Salida calculada o solicitada. |
| `action` | TEXT | NOT NULL | Accion registrada. |
| `reason` | TEXT | NOT NULL | Motivo de la decision. |

## visual_analysis

Guarda resultados de analisis de imagen por OpenCV.

Ejemplo de uso: almacena el porcentaje de cobertura verde detectado en una
imagen de prueba para comparar visualmente el crecimiento de las plantas.

| Columna | Tipo | Restricciones | Descripcion |
| --- | --- | --- | --- |
| `id` | INTEGER | PK | Identificador interno del analisis. |
| `filename` | TEXT | NOT NULL | Nombre de la imagen original o capturada. |
| `timestamp` | TEXT | NOT NULL | Fecha del analisis. |
| `green_area` | INTEGER | NOT NULL | Cantidad de pixeles verdes detectados. |
| `coverage` | REAL | NOT NULL, entre `0` y `100` | Porcentaje de cobertura vegetal detectada. |
| `processed_image` | TEXT | NOT NULL | Ruta o nombre de la imagen procesada. |
| `observations` | TEXT | NOT NULL | Observaciones generadas por el proceso de vision. |
| `roi_json` | TEXT | NOT NULL | Region de interes utilizada, serializada en JSON. |

## audit_log

Registra acciones relevantes ejecutadas por usuarios.

Ejemplo de uso: registra que un administrador creo un usuario o cambio un
parametro del sistema, dejando trazabilidad para revision posterior.

| Columna | Tipo | Restricciones | Descripcion |
| --- | --- | --- | --- |
| `id` | INTEGER | PK | Identificador interno del registro. |
| `timestamp` | TEXT | NOT NULL | Fecha de la accion. |
| `user_id` | INTEGER | FK a `users.id` | Usuario que realizo la accion. |
| `action` | TEXT | NOT NULL | Nombre o tipo de accion. |
| `details` | TEXT | NOT NULL | Detalle textual de la accion. |

## web_metrics

Almacena mediciones tecnicas de solicitudes web.

Ejemplo de uso: guarda cuanto tardo en responder `/dashboard` para revisar si
la interfaz cumple los tiempos esperados de uso.

| Columna | Tipo | Restricciones | Descripcion |
| --- | --- | --- | --- |
| `id` | INTEGER | PK | Identificador interno de la muestra. |
| `timestamp` | TEXT | NOT NULL | Fecha de la medicion. |
| `path` | TEXT | NOT NULL | Ruta HTTP solicitada. |
| `status` | INTEGER | NOT NULL | Codigo de respuesta HTTP. |
| `duration_ms` | REAL | NOT NULL | Duracion de la solicitud en milisegundos. |

## service_samples

Guarda muestras periodicas del estado operativo del servicio.

Ejemplo de uso: registra si MQTT estaba conectado y si los sensores tenian datos
recientes durante una prueba del prototipo.

| Columna | Tipo | Restricciones | Descripcion |
| --- | --- | --- | --- |
| `id` | INTEGER | PK | Identificador interno de la muestra. |
| `timestamp` | TEXT | NOT NULL | Fecha de la muestra. |
| `mqtt_connected` | INTEGER | NOT NULL | Estado de conexion MQTT, normalmente `0` o `1`. |
| `sensor_fresh` | INTEGER | NOT NULL | Indica si las lecturas recientes estan frescas, normalmente `0` o `1`. |

## Relaciones principales

| Relacion | Cardinalidad | Uso |
| --- | --- | --- |
| `sensor_types` a `sensor_readings` | 1 a N | Una variable puede tener muchas lecturas. |
| `devices` a `sensor_readings` | 1 a N | Un dispositivo puede emitir muchas lecturas. |
| `sensor_readings` a `alerts` | 1 a N | Una lectura puede disparar o actualizar alertas. |
| `sensor_types` a `alerts` | 1 a N | Las alertas se clasifican por variable. |
| `devices` a `alerts` | 1 a N | Las alertas se asocian al origen de datos. |
| `sensor_readings` a `control_events` | 1 a N | El controlador puede registrar eventos basados en una lectura. |
| `users` a `audit_log` | 1 a N | Un usuario puede generar muchas entradas de auditoria. |

## Notas para la tesis

El modelo prioriza trazabilidad: cada lectura conserva origen, tiempos de
recepcion y almacenamiento; cada alerta conserva su estado; y cada accion de
control queda registrada como evento. Las tablas de vision, metricas y muestras
de servicio funcionan como evidencias tecnicas para validar el comportamiento
del prototipo.
