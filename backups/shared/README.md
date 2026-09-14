# Respaldos compartibles por Git

Estos archivos son **exportaciones sanitizadas**, no copias completas de la base
operativa. `manifest.json` registra fecha UTC, cantidad de lecturas y SHA-256.
Los respaldos completos privados se guardan en `data/backups/` (ignorado por Git).

Se preservan el esquema, los rangos de sensores y las lecturas cuyo origen sea
`simulator` o `wokwi`, incluyendo valores y fechas. Se reemplazan identificadores
de dispositivo y mensaje. No se copian usuarios, hashes de contraseñas, auditoría,
resultados de imágenes, parámetros libres, alertas, eventos de control ni métricas
web. Los actuadores se inicializan en cero. Las imágenes del dataset ML se descargan
por separado según `docs/ml/README.md`.

La exportación se construye en una base nueva: los datos privados no quedan en
páginas libres de SQLite ni dentro del SQL comprimido. No usar estas copias para
recuperación completa: para eso está el respaldo privado.

## Otra computadora: perfil local

Desde un clon nuevo, con Python y las dependencias instaladas:

```bash
cp -n .env.git.example .env
python scripts/restore_shared_backup.py --profile local --output data/hidroponia.sqlite3
python -c 'import secrets; print(secrets.token_hex(32))'
```

Guardar el valor generado en `SECRET_KEY` de `.env` **solo localmente**. El ejemplo
versionado deja las credenciales vacías; no copiar claves de otra instalación.
Crear una cuenta (la contraseña se solicita sin mostrarla) e iniciar el sistema:

```bash
python -m flask --app app:create_app create-user --username admin --role ADMIN
python run.py
```

Mosquitto debe estar disponible en localhost:1883 para recibir nuevas lecturas.
Los registros restaurados se consultan en Históricos con sus fechas originales;
no se convierten en lecturas actuales y no sirven para activar el PID.

## Perfil Wokwi

Después de crear el usuario del perfil local, restaurar **antes** de ejecutar
la preparación, porque esta última crea la base si no existe:

```bash
python scripts/restore_shared_backup.py --profile wokwi --output data/hidroponia-wokwi.sqlite3
python scripts/prepare_wokwi.py
python run.py --profile wokwi
```

La preparación genera `.env.wokwi` con una clave y un prefijo MQTT nuevos, y copia
localmente la cuenta recién creada. Los históricos tienen dispositivos anónimos;
las nuevas lecturas del circuito usarán el dispositivo configurado para esa máquina.
No copiar `.env.wokwi` ni el prefijo público de otra instalación a Git.

## Si ya existe una base

El restaurador **rechaza sobrescribir archivos existentes**. Restaurar en otra ruta,
por ejemplo `data/restaurada.sqlite3`, y configurar `DATABASE_PATH` en el `.env`
local apropiado. Conservar la base original y detener el backend antes de cambiar
su configuración.

## Renovar respaldos

```bash
python scripts/backup_for_git.py
```

Lee las bases estándar `data/hidroponia.sqlite3` y `data/hidroponia-wokwi.sqlite3`.
Crea snapshots consistentes mediante SQLite Backup API, incluso con WAL activo,
y valida integridad y claves foráneas de la exportación y de su restauración.
No lee otras rutas personalizadas de DATABASE_PATH ni respalda hardware real.
Cada ejecución conserva un respaldo privado nuevo y actualiza los compartibles.
Revisar y comitear únicamente `.env.git.example`, los scripts y `backups/shared/`.
