from app.db import get_db


def test_ml_evidence_requires_login(app):
    client=app.test_client()
    for path in ['/api/vision/ml/report','/api/vision/ml/evidence/evaluation.png']:
        assert client.get(path).status_code==401


def test_operator_can_read_saved_experiment(client,app):
    with app.app_context():
        with get_db() as db:
            db.execute("UPDATE users SET role='OPERADOR' WHERE username='admin'")
    response=client.get('/api/vision/ml/report')
    assert response.status_code==200
    assert response.json['raw_samples']==612
    assert response.json['splits']['test']['images']==192
    assert b'id="ml-tests"' in client.get('/vision').data
    image=client.get('/api/vision/ml/evidence/evaluation.png')
    assert image.status_code==200 and image.mimetype=='image/png'
    csv=client.get('/api/vision/ml/evidence/predictions.csv')
    assert csv.status_code==200
    assert 'attachment' in csv.headers['Content-Disposition']


def test_only_reviewable_evidence_is_served(client):
    for name in ['model.json','source.json','.env','unknown.txt']:
        assert client.get('/api/vision/ml/evidence/'+name).status_code==404


def test_sample_pagination_and_split_validation(client):
    first=client.get('/api/vision/ml/samples').json
    second=client.get('/api/vision/ml/samples?page=2').json
    assert first['total']==192 and first['pages']==16
    assert len(first['items'])==12
    assert all(s['split']=='test' for s in first['items'])
    assert not {s['id'] for s in first['items']} & {s['id'] for s in second['items']}
    assert client.get('/api/vision/ml/samples?split=train').json['total']==204
    assert client.get('/api/vision/ml/samples?split=validation').json['total']==216
    for query in ['split=unknown','page=0','page=17','page=abc']:
        assert client.get('/api/vision/ml/samples?'+query).status_code==400


def test_sample_images_are_allowlisted_and_hash_verified(client,app,tmp_path,monkeypatch):
    import hashlib
    from app.routes import vision
    data=b'known image content'
    identifier='a'*64
    monkeypatch.setattr(app,'root_path',str(tmp_path/'app'))
    folder=tmp_path/'data/ml/hydrogrow/images'
    folder.mkdir(parents=True)
    image=folder/f'{identifier}.png'
    image.write_bytes(data)
    monkeypatch.setattr(vision,'_ml_samples',lambda:[dict(id=identifier,available=True,sha256=hashlib.sha256(data).hexdigest())])
    assert client.get('/api/vision/ml/sample/'+identifier).data==data
    image.write_bytes(b'changed')
    assert client.get('/api/vision/ml/sample/'+identifier).status_code==409
    assert client.get('/api/vision/ml/sample/'+'b'*64).status_code==404
    assert client.get('/api/vision/ml/sample/invalid').status_code==404


def test_gallery_requires_login(app):
    client=app.test_client()
    assert client.get('/api/vision/ml/samples').status_code==401
    assert client.get('/api/vision/ml/sample/'+'a'*64).status_code==401
