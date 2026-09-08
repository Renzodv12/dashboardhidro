"""Muestra reproducible de HydroGrowNet v3 mediante HTTP Range, sin extraer ZIPs completos."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import io
import json
from pathlib import Path
import random
import re
import struct
import subprocess
import zipfile
import zlib

ROOT = Path(__file__).resolve().parents[1]
API = 'https://data.mendeley.com/public-api/datasets/g6cm3v3wdp/files?folder_id=root&version=3'


def fetch(url, start=None, end=None):
    command = ['curl', '-fLsS', '--max-time', '90', '--retry', '2',
               '-H', 'Accept: application/vnd.mendeley-public-dataset.1+json']
    if start is not None:
        command += ['--range', f'{start}-{end}', '--max-filesize', str(max(4096, end-start+1))]
    result = subprocess.run(command + ['--write-out', '%{http_code}', url], check=True, capture_output=True)
    data, status = result.stdout[:-3], result.stdout[-3:]
    if start is not None and (status != b'206' or len(data) != end-start+1):
        raise ValueError('El servidor no entregó el rango solicitado')
    return data


class RemoteZip(io.RawIOBase):
    def __init__(self, url, size):
        self.url, self.size, self.position = url, size, 0

    def seekable(self):
        return True

    def tell(self):
        return self.position

    def seek(self, offset, whence=0):
        self.position = offset + (self.position if whence == 1 else self.size if whence == 2 else 0)
        return self.position

    def read(self, size=-1):
        end = self.size if size < 0 else min(self.size, self.position+size)
        ranges = [(p, min(end-1, p+262143)) for p in range(self.position, end, 262144)]
        with ThreadPoolExecutor(max_workers=8) as pool:
            result = b''.join(pool.map(lambda r: fetch(self.url, *r), ranges))
        self.position = end
        return result


def extract_member(url, info):
    if info.file_size > 20_000_000 or info.compress_size > 20_000_000:
        raise ValueError('Miembro demasiado grande')
    header = fetch(url, info.header_offset, info.header_offset+29)
    if header[:4] != b'PK\x03\x04':
        raise ValueError('Cabecera ZIP inválida')
    name_size, extra_size = struct.unpack_from('<HH', header, 26)
    start = info.header_offset+30+name_size+extra_size
    compressed = fetch(url, start, start+info.compress_size-1)
    if info.compress_type == zipfile.ZIP_DEFLATED:
        data = zlib.decompress(compressed, -15)
    elif info.compress_type == zipfile.ZIP_STORED:
        data = compressed
    else:
        raise ValueError('Compresión no soportada')
    if len(data) != info.file_size or zlib.crc32(data) & 0xffffffff != info.CRC:
        raise ValueError('Integridad CRC inválida')
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--per-day', type=int, default=12)
    args = parser.parse_args()
    if not 1 <= args.per_day <= 100:
        parser.error('--per-day: 1..100')
    folder = ROOT/'data/ml/hydrogrow'
    folder.mkdir(parents=True, exist_ok=True)
    metadata = json.loads(fetch(API))
    (folder/'source-files.json').write_text(json.dumps(metadata, indent=2))
    records = []
    inventory = {}
    for source in metadata:
        if not source['filename'].endswith('.zip'):
            continue
        month = source['filename'][:-4]
        url = source['content_details']['download_url']
        print(f'{month}: leyendo índice remoto', flush=True)
        cache = folder/f'{month}-index.json'
        if cache.exists():
            infos = []
            for values in json.loads(cache.read_text()):
                info = zipfile.ZipInfo(values['filename'])
                for key, value in values.items():
                    setattr(info, key, value)
                infos.append(info)
        else:
            with zipfile.ZipFile(RemoteZip(url, source['size'])) as archive:
                infos = archive.infolist()
            keys = ['filename', 'header_offset', 'compress_size', 'file_size', 'compress_type', 'CRC']
            cache.write_text(json.dumps([{k: getattr(i, k) for k in keys} for i in infos]))
        groups = {}
        others = []
        for info in infos:
            parts = Path(info.filename).parts
            if info.filename.lower().endswith('.png') and len(parts) >= 2:
                day = next((p for p in parts[:-1] if re.fullmatch(r'\d{4}-\d{2}-\d{2}', p)), None)
                if day is None:
                    raise ValueError('Fecha ausente en '+info.filename)
                groups.setdefault(day, []).append(info)
            elif not info.is_dir():
                others.append(info.filename)
        inventory[month] = {'images_by_day': {k: len(v) for k, v in sorted(groups.items())}, 'other_files': others}
        print(f'{month}: {sum(map(len, groups.values()))} imágenes, {len(groups)} días, otros: {others[:10]}', flush=True)
        selected = []
        for day, group in sorted(groups.items()):
            rng = random.Random(f'hydrogrow-v3-42-{month}-{day}')
            selected.extend(rng.sample(sorted(group, key=lambda i:i.filename), min(args.per_day, len(group))))
        def download(info):
            # Nombres locales derivados del hash: nunca extraer rutas recibidas del ZIP.
            identifier = hashlib.sha256((month+'/'+info.filename).encode()).hexdigest()
            path = folder/'images'/f'{identifier}.png'
            path.parent.mkdir(exist_ok=True)
            if path.exists():
                data = path.read_bytes()
                if len(data) != info.file_size or zlib.crc32(data) & 0xffffffff != info.CRC:
                    raise ValueError('Muestra local corrupta')
            else:
                data = extract_member(url, info)
                path.write_bytes(data)
            return {'experiment': month, 'date': next(p for p in Path(info.filename).parts[:-1] if re.fullmatch(r'\d{4}-\d{2}-\d{2}', p)), 'member': info.filename,
                    'path': str(path.relative_to(ROOT)), 'sha256': hashlib.sha256(data).hexdigest(), 'crc32': info.CRC}
        with ThreadPoolExecutor(max_workers=8) as pool:
            for n, record in enumerate(pool.map(download, selected), 1):
                records.append(record)
                if n % 60 == 0:
                    print(f'{month}: {n}/{len(selected)} muestras', flush=True)
        (folder/'manifest.json').write_text(json.dumps(records, indent=2))
        (folder/'inventory.json').write_text(json.dumps(inventory, indent=2))
    print(f'Muestra completa: {len(records)} imágenes', flush=True)


if __name__ == '__main__':
    main()
