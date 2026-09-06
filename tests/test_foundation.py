import sqlite3
from pathlib import Path

import pytest

from app import create_app
from app.db import get_db, init_db
from config import BASE_DIR, env_bool, env_port


def test_first_start_creates_database(app):
    assert Path(app.config["DATABASE_PATH"]).is_file()
    with app.app_context():
        db = get_db()
        assert db.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert db.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert db.execute("SELECT version FROM schema_migrations").fetchone()[0] == 1


def test_restart_preserves_committed_data(app):
    with app.app_context():
        db = get_db()
        db.execute("CREATE TABLE persistence_probe (value TEXT NOT NULL)")
        with db:
            db.execute("INSERT INTO persistence_probe VALUES (?)", ("evidencia",))
        init_db()
    restarted = create_app({"TESTING": True, "DATABASE_PATH": app.config["DATABASE_PATH"]})
    with restarted.app_context():
        assert get_db().execute("SELECT value FROM persistence_probe").fetchone()[0] == "evidencia"
        assert get_db().execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == 2


def test_connection_lifecycle(app):
    with app.app_context():
        connection = get_db()
        assert get_db() is connection
    with pytest.raises(sqlite3.ProgrammingError):
        connection.execute("SELECT 1")


def test_dashboard(client):
    assert client.get("/").headers["Location"] == "/dashboard"
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert "Sin lecturas" in response.text
    assert client.get("/static/css/app.css").status_code == 200


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json["database"] == "ok"
    assert response.json["schema_version"] == 2
    assert response.json["services"]["mqtt"] == "disconnected"


def test_health_reports_database_failure(app, client):
    with app.app_context():
        with get_db() as db:
            db.execute("DROP TABLE schema_migrations")
    response = client.get("/api/health")
    assert response.status_code == 503
    assert response.json["database"] == "unavailable"
    assert "sqlite" not in response.text.lower()


def test_init_command_is_repeatable(app):
    runner = app.test_cli_runner()
    for _ in range(2):
        assert runner.invoke(args=["init-db"]).exit_code == 0


def test_unknown_api_route(client):
    assert client.get("/api/missing").status_code == 404
    assert client.get("/api/missing").is_json


def test_relative_database_path_ignores_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # Use a relative traversal resolving into pytest's temporary directory.
    import os
    path = tmp_path / "relative.sqlite3"
    app = create_app({"TESTING": True, "DATABASE_PATH": os.path.relpath(path, BASE_DIR)})
    assert app.config["DATABASE_PATH"] == str(path)
    assert path.exists()


def test_invalid_configuration(monkeypatch):
    monkeypatch.setenv("HYDRO_DEBUG", "typo")
    with pytest.raises(ValueError, match="HYDRO_DEBUG"):
        env_bool("HYDRO_DEBUG")
    monkeypatch.setenv("PORT", "70000")
    with pytest.raises(ValueError, match="PORT"):
        env_port("PORT", 5000)
