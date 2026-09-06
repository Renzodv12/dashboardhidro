import pytest

from app import create_app
from app.db import get_db
from app.routes.auth import create_user


@pytest.fixture
def app(tmp_path):
    return create_app({
        "TESTING": True,
        "SECRET_KEY": "test-only-key",
        "DATABASE_PATH": str(tmp_path / "nested" / "test.sqlite3"),
    })


@pytest.fixture
def client(app):
    with app.app_context():
        with get_db():
            user_id=create_user('admin','test-password-123','ADMIN')
    client=app.test_client()
    with client.session_transaction() as session:
        session['user_id']=user_id
        session['csrf_token']='test-csrf'
    return client
