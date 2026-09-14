"""Restaura un respaldo compartible en un archivo nuevo; nunca sobrescribe bases."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3
ROOT=Path(__file__).resolve().parents[1]


def restore(profile,destination):
    folder=ROOT/'backups/shared'
    report=json.loads((folder/'manifest.json').read_text())
    entry=next(r for r in report['backups'] if r['profile']==profile)
    archive=folder/f'{profile}.sql.gz'
    data=archive.read_bytes()
    if hashlib.sha256(data).hexdigest()!=entry['sha256']:
        raise ValueError('Hash del respaldo inválido')
    destination=Path(destination)
    destination.parent.mkdir(parents=True,exist_ok=True)
    with destination.open('xb'):
        pass
    try:
        with sqlite3.connect(destination) as db:
            db.executescript(gzip.decompress(data).decode())
            assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
            assert not db.execute('PRAGMA foreign_key_check').fetchall()
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    print(f'Restaurado: {destination}. Sin usuarios: crear una cuenta local antes de ingresar.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile',choices=['local','wokwi'],default='local')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    restore(args.profile,args.output)
