import gzip
import sqlite3
from pathlib import Path
import pytest
from scripts.backup_for_git import snapshot, sanitize
from scripts.restore_shared_backup import restore


def test_snapshot_preserves_private_data_but_export_omits_it(app,client,tmp_path):
    source=Path(app.config['DATABASE_PATH'])
    with sqlite3.connect(source) as db:
        db.execute("INSERT INTO audit_log(timestamp,action,details) VALUES ('2026-01-01','private','PERSONAL-NOTE-DO-NOT-SHARE')")
    full=tmp_path/'private.sqlite3'
    snapshot(source,full)
    with sqlite3.connect(full) as db:
        assert db.execute('SELECT count(*) FROM users').fetchone()[0]==1
    sql,count=sanitize(full)
    assert b'PERSONAL-NOTE-DO-NOT-SHARE' not in sql
    assert b'pbkdf2:' not in sql
    with sqlite3.connect(':memory:') as restored:
        restored.executescript(sql.decode())
        assert restored.execute('SELECT count(*) FROM users').fetchone()[0]==0
        assert restored.execute('SELECT count(*) FROM audit_log').fetchone()[0]==0
        assert not restored.execute('PRAGMA foreign_key_check').fetchall()
    with pytest.raises(FileExistsError):
        snapshot(source,full)


@pytest.mark.parametrize('profile',['local','wokwi'])
def test_shared_backups_restore_without_overwriting(profile,tmp_path):
    target=tmp_path/(profile+'.sqlite3')
    restore(profile,target)
    with sqlite3.connect(target) as db:
        assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert db.execute('SELECT count(*) FROM sensor_readings').fetchone()[0]>0
        assert db.execute('SELECT count(*) FROM users').fetchone()[0]==0
        assert db.execute('SELECT count(*) FROM system_parameters').fetchone()[0]==0
        assert not db.execute('PRAGMA foreign_key_check').fetchall()
    original=target.read_bytes()
    with pytest.raises(FileExistsError):
        restore(profile,target)
    assert target.read_bytes()==original
