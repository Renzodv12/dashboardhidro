BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS users (
 id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE,
 password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('ADMIN','OPERADOR')),
 active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
 created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sensor_types (
 id INTEGER PRIMARY KEY, variable TEXT NOT NULL UNIQUE, label TEXT NOT NULL,
 unit TEXT NOT NULL, physical_min REAL NOT NULL, physical_max REAL NOT NULL,
 minimum REAL NOT NULL, maximum REAL NOT NULL,
 CHECK(physical_min <= minimum AND minimum < maximum AND maximum <= physical_max)
);
CREATE TABLE IF NOT EXISTS devices (
 id TEXT PRIMARY KEY, source TEXT NOT NULL, last_seen TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sensor_readings (
 id INTEGER PRIMARY KEY, sensor_type_id INTEGER NOT NULL REFERENCES sensor_types(id),
 device_id TEXT NOT NULL REFERENCES devices(id), message_id TEXT NOT NULL,
 value REAL NOT NULL, measured_at TEXT NOT NULL, received_at TEXT NOT NULL,
 stored_at TEXT NOT NULL, transport_ms REAL NOT NULL, storage_ms REAL NOT NULL DEFAULT 0,
 UNIQUE(device_id, message_id)
);
CREATE INDEX IF NOT EXISTS readings_history ON sensor_readings(sensor_type_id, measured_at, id);
CREATE TABLE IF NOT EXISTS alerts (
 id INTEGER PRIMARY KEY, sensor_type_id INTEGER REFERENCES sensor_types(id),
 device_id TEXT REFERENCES devices(id), reading_id INTEGER REFERENCES sensor_readings(id),
 condition TEXT NOT NULL, severity TEXT NOT NULL CHECK(severity IN ('INFO','WARNING','CRITICAL')),
 message TEXT NOT NULL, opened_at TEXT NOT NULL, resolved_at TEXT, acknowledged_at TEXT,
 response_ms REAL
);
CREATE UNIQUE INDEX IF NOT EXISTS alerts_open ON alerts(sensor_type_id,device_id,condition)
 WHERE resolved_at IS NULL;
CREATE TABLE IF NOT EXISTS system_parameters (
 key TEXT PRIMARY KEY, value_json TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS actuators (
 id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, device_id TEXT,
 requested_output REAL NOT NULL DEFAULT 0, reported_output REAL NOT NULL DEFAULT 0,
 updated_at TEXT, reported_at TEXT
);
CREATE TABLE IF NOT EXISTS control_events (
 id INTEGER PRIMARY KEY, timestamp TEXT NOT NULL, reading_id INTEGER REFERENCES sensor_readings(id),
 mode TEXT NOT NULL, setpoint REAL NOT NULL, measured REAL, error REAL,
 output REAL NOT NULL, action TEXT NOT NULL, reason TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS visual_analysis (
 id INTEGER PRIMARY KEY, filename TEXT NOT NULL, timestamp TEXT NOT NULL,
 green_area INTEGER NOT NULL, coverage REAL NOT NULL CHECK(coverage BETWEEN 0 AND 100),
 processed_image TEXT NOT NULL, observations TEXT NOT NULL, roi_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_log (
 id INTEGER PRIMARY KEY, timestamp TEXT NOT NULL, user_id INTEGER REFERENCES users(id),
 action TEXT NOT NULL, details TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS web_metrics (
 id INTEGER PRIMARY KEY, timestamp TEXT NOT NULL, path TEXT NOT NULL,
 status INTEGER NOT NULL, duration_ms REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS service_samples (
 id INTEGER PRIMARY KEY, timestamp TEXT NOT NULL, mqtt_connected INTEGER NOT NULL,
 sensor_fresh INTEGER NOT NULL
);
INSERT OR IGNORE INTO sensor_types VALUES
 (1,'ph','pH','pH',0,14,5.5,6.5),
 (2,'tds','Nutrientes / TDS','ppm',0,5000,500,1200),
 (3,'temperatura_agua','Temperatura del agua','°C',0,60,18,26),
 (4,'temperatura_ambiente','Temperatura ambiente','°C',-10,60,18,32),
 (5,'humedad','Humedad ambiente','%',0,100,40,80),
 (6,'nivel','Nivel del depósito','%',0,100,25,100);
INSERT OR IGNORE INTO actuators (name) VALUES ('ph_plus'),('ph_minus'),('nutrientes'),('agua');
INSERT OR IGNORE INTO schema_migrations (version,description) VALUES (2,'Modelo hidropónico y evidencias');
COMMIT;
