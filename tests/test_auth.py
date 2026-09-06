import sqlite3
from app.db import get_db
from app.routes.auth import create_user


def test_login_logout_and_hash(app):
    with app.app_context():
        with get_db(): create_user('operator','long-password-123','OPERADOR')
        stored=get_db().execute('SELECT password_hash FROM users').fetchone()[0]
        assert stored!='long-password-123'
        assert stored.startswith('pbkdf2:sha256:1000000$')
    client=app.test_client()
    assert client.get('/dashboard').status_code==302
    assert client.get('/api/sensors/latest').status_code==401
    client.get('/login')
    with client.session_transaction() as session: token=session['csrf_token']
    assert client.post('/login',data={'username':'operator','password':'wrong','csrf_token':token}).status_code==401
    assert client.post('/login',data={'username':'operator','password':'long-password-123','csrf_token':token}).status_code==302
    assert client.get('/dashboard').status_code==200
    for path in ['/control','/settings','/users','/audit','/api/users','/api/audit','/api/metrics']:
        assert client.get(path).status_code==403
    assert client.post('/api/control/manual',json={'output':40}).status_code==403
    with client.session_transaction() as session: token=session['csrf_token']
    assert client.post('/logout',data={'csrf_token':token}).status_code==302
    assert client.get('/api/sensors/latest').status_code==401


def test_csrf_and_invalid_json(client):
    assert client.post('/api/settings/ranges',json={}).status_code==400
    assert client.post('/api/settings/ranges',json=[],headers={'X-CSRF-Token':'test-csrf'}).status_code==400


def test_backup_can_be_opened(client,tmp_path):
    response=client.post('/api/backup',headers={'X-CSRF-Token':'test-csrf'})
    assert response.status_code==200
    path=tmp_path/'backup.sqlite3'
    path.write_bytes(response.data)
    connection=sqlite3.connect(path)
    try:
        assert connection.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert connection.execute('SELECT username FROM users').fetchone()[0]=='admin'
    finally: connection.close()


def test_admin_routes_and_audit(client):
    for path in ['/dashboard','/sensors','/history','/alerts','/control','/vision','/settings','/users','/audit']:
        assert client.get(path).status_code==200
    response=client.post('/api/settings/ranges',json={'variable':'ph','minimum':5.6,'maximum':6.6},headers={'X-CSRF-Token':'test-csrf'})
    assert response.status_code==200
    assert client.get('/api/audit').json[0]['action']=='settings.ranges'
