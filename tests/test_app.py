import os
import tempfile

from app import app, _database_uri


def test_health():
    app.config['TESTING']=True
    response=app.test_client().get('/health')
    assert response.status_code==200
    assert response.get_json()['status']=='ok'


def test_dashboard():
    app.config['TESTING']=True
    assert app.test_client().get('/').status_code==200


def test_vercel_uses_writable_sqlite_path(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.delenv("DATABASE_URL", raising=False)

    database_path = os.path.join(tempfile.gettempdir(), "peopleops.db").replace(os.sep, "/")
    assert _database_uri() == f"sqlite:///{database_path}"


def test_database_url_overrides_default(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///custom.db")

    assert _database_uri() == "sqlite:///custom.db"
