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
