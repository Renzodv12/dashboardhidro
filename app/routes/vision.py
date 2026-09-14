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


@bp.get('/ml/report')
def ml_report():
    """Evidencia del experimento guardado, independiente de las capturas del usuario."""
    import json
    path=Path(current_app.root_path).parent/'docs/ml/metrics.json'
    if not path.is_file():
        return jsonify(error='Todavía no hay resultados de entrenamiento disponibles'),404
    return jsonify(json.loads(path.read_text()))


@bp.get('/ml/evidence/<name>')
def ml_evidence(name):
    allowed={'evaluation.png','predictions.csv','RESULTADOS.md'}
    if name not in allowed:
        abort(404)
    path=Path(current_app.root_path).parent/'docs/ml'/name
    if not path.is_file():
        abort(404)
    return send_file(path,as_attachment=name!='evaluation.png',download_name=name)


def _ml_samples():
    import csv
    import json
    root=Path(current_app.root_path).parent
    try:
        manifest=json.loads((root/'docs/ml/sample-manifest.json').read_text())
        with (root/'docs/ml/predictions.csv').open() as stream:
            predictions={(r['experiment'],r['member'],r['sha256']):r for r in csv.DictReader(stream)}
    except FileNotFoundError:
        abort(404,description='Muestra del entrenamiento no disponible')
    samples=[]
    for row in manifest:
        prediction=predictions.get((row['experiment'],row['member'],row['sha256']))
        if prediction is None:
            continue
        # El identificador se calcula; nunca se sirve una ruta enviada por el cliente.
        import hashlib
        identifier=hashlib.sha256((row['experiment']+'/'+row['member']).encode()).hexdigest()
        target=float(prediction['target_day'])
        predicted=float(prediction['predicted_day'])
        samples.append(dict(id=identifier,sha256=row['sha256'],experiment=row['experiment'],
            date=row['date'],filename=Path(row['member']).name,split=prediction['split'],
            target_day=target,predicted_day=predicted,error_days=abs(predicted-target),
            available=(root/'data/ml/hydrogrow/images'/f'{identifier}.png').is_file()))
    return sorted(samples,key=lambda s:(s['experiment'],s['date'],s['filename']))


@bp.get('/ml/samples')
def ml_samples():
    split=request.args.get('split','test')
    if split not in {'train','validation','test'}:
        abort(400,description='Conjunto inválido')
    try:
        page=int(request.args.get('page','1'))
    except ValueError:
        abort(400,description='Página inválida')
    rows=[row for row in _ml_samples() if row['split']==split]
    pages=max(1,(len(rows)+11)//12)
    if not 1<=page<=pages:
        abort(400,description='Página fuera de rango')
    return jsonify(items=rows[(page-1)*12:page*12],page=page,pages=pages,total=len(rows))


@bp.get('/ml/sample/<identifier>')
def ml_sample_image(identifier):
    import hashlib
    import re
    if not re.fullmatch('[a-f0-9]{64}',identifier):
        abort(404)
    sample=next((s for s in _ml_samples() if s['id']==identifier),None)
    if sample is None or not sample['available']:
        abort(404,description='Imagen del dataset no disponible en esta instalación')
    path=Path(current_app.root_path).parent/'data/ml/hydrogrow/images'/f'{identifier}.png'
    if hashlib.sha256(path.read_bytes()).hexdigest()!=sample['sha256']:
        abort(409,description='La imagen no coincide con la muestra utilizada al entrenar')
    return send_file(path,mimetype='image/png')
