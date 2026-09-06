from pathlib import Path
from flask import Blueprint, current_app, g, jsonify, request, send_file, abort
from app.db import get_db
from app.services.vision_service import analyze, capture, image_path

bp=Blueprint('vision',__name__,url_prefix='/api/vision')

@bp.get('')
def results():
    return jsonify([dict(r) for r in get_db().execute('SELECT * FROM visual_analysis ORDER BY id DESC LIMIT 100')])

@bp.get('/latest')
def latest():
    row=get_db().execute('SELECT * FROM visual_analysis ORDER BY id DESC LIMIT 1').fetchone()
    return jsonify(dict(row) if row else None)

@bp.get('/files')
def files():
    root=Path(current_app.config['IMAGES_PATH'])
    return jsonify(sorted(p.name for p in root.iterdir() if p.is_file() and p.suffix.lower() in {'.png','.jpg','.jpeg'}))

@bp.post('/analyze')
def process():
    data=request.get_json()
    return jsonify(analyze(data.get('filename'),data.get('roi'),g.user['id']))

@bp.post('/capture')
def webcam():
    return jsonify(capture(g.user['id']))

@bp.get('/image/<filename>')
def image(filename):
    path=image_path(filename,True)
    if not path.exists():
        abort(404)
    return send_file(path)
