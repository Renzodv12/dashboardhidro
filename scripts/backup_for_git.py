"""Respaldo completo privado y exportación sanitizada de telemetría simulada para Git."""
import gzip
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

ROOT=Path(__file__).resolve().parents[1]


def snapshot(source,target):
    target.parent.mkdir(parents=True,exist_ok=True)
    # Crear con permisos privados desde el principio y no sobrescribir.
    with target.open('xb'):
        target.chmod(0o600)
    with sqlite3.connect(source.resolve().as_uri()+'?mode=ro',uri=True) as src:
        with sqlite3.connect(target) as dst:
            src.backup(dst)
            assert dst.execute('PRAGMA integrity_check').fetchone()[0]=='ok'


def sanitize(source,root=ROOT):
    """Base nueva: evita conservar información borrada en páginas libres de SQLite."""
    dst=sqlite3.connect(':memory:')
    dst.executescript((root/'app/schema.sql').read_text())
    dst.executescript((root/'app/models/domain.sql').read_text())
    dst.execute('PRAGMA foreign_keys=ON')
    src=sqlite3.connect(source)
    src.row_factory=sqlite3.Row
    try:
        with dst:
            # Etiquetas/esquema del repositorio; únicamente rangos numéricos desde origen.
            for row in src.execute('SELECT variable,minimum,maximum FROM sensor_types'):
                dst.execute('UPDATE sensor_types SET minimum=?,maximum=? WHERE variable=?',
                            (row['minimum'],row['maximum'],row['variable']))
            device_map={}
            for index,row in enumerate(src.execute("SELECT id,source FROM devices WHERE source IN ('simulator','wokwi') ORDER BY id"),1):
                name=f"{row['source']}-demo-{index}"
                device_map[row['id']]=name
                dst.execute('INSERT INTO devices VALUES (?,?,?)',(name,row['source'],'1970-01-01T00:00:00+00:00'))
            sensor_ids=dict(dst.execute('SELECT variable,id FROM sensor_types'))
            count=0
            for row in src.execute('SELECT r.*,s.variable FROM sensor_readings r JOIN sensor_types s ON s.id=r.sensor_type_id ORDER BY r.id'):
                if row['device_id'] not in device_map or row['variable'] not in sensor_ids:
                    continue
                if not all(math.isfinite(row[k]) for k in ['value','transport_ms','storage_ms']):
                    raise ValueError('Valor numérico inválido')
                stamps=[datetime.fromisoformat(row[k]).isoformat() for k in ['measured_at','received_at','stored_at']]
                count+=1
                dst.execute('INSERT INTO sensor_readings VALUES (?,?,?,?,?,?,?,?,?,?)',
                    (count,sensor_ids[row['variable']],device_map[row['device_id']],f'demo-{count}',row['value'],*stamps,row['transport_ms'],row['storage_ms']))
            dst.execute('UPDATE devices SET last_seen=COALESCE((SELECT MAX(received_at) FROM sensor_readings WHERE device_id=devices.id),last_seen)')
        assert dst.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert not dst.execute('PRAGMA foreign_key_check').fetchall()
        for table in ['users','audit_log','visual_analysis','system_parameters','alerts','control_events','web_metrics','service_samples']:
            assert dst.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]==0
        return ('\n'.join(dst.iterdump())+'\n').encode(),count
    finally:
        src.close()
        dst.close()


def main():
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    private=ROOT/'data/backups'/stamp
    shared=ROOT/'backups/shared'
    shared.mkdir(parents=True,exist_ok=True)
    report={'created_at_utc':stamp,'kind':'sanitized_simulated_telemetry','backups':[]}
    for profile,name in [('local','hidroponia.sqlite3'),('wokwi','hidroponia-wokwi.sqlite3')]:
        source=ROOT/'data'/name
        if not source.is_file():
            continue
        full=private/name
        snapshot(source,full)
        sql,count=sanitize(full)
        archive=shared/f'{profile}.sql.gz'
        archive.write_bytes(gzip.compress(sql,mtime=0))
        # Restauración de control, sin modificar ninguna base en uso.
        with sqlite3.connect(':memory:') as restored:
            restored.executescript(sql.decode())
            assert restored.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
            assert not restored.execute('PRAGMA foreign_key_check').fetchall()
        report['backups'].append({'profile':profile,'file':archive.name,'readings':count,
            'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'bytes':archive.stat().st_size})
        print(f'{profile}: respaldo privado {full.relative_to(ROOT)}; compartible {archive.relative_to(ROOT)} ({count} lecturas)')
    if not report['backups']:
        raise ValueError('No se encontraron bases de datos para respaldar')
    (shared/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':
    main()
