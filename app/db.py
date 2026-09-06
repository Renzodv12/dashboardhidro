"""Una conexión SQLite por contexto; inicialización idempotente y no destructiva."""

import sqlite3
from pathlib import Path

import click
from flask import current_app, g
from flask.cli import with_appcontext


def get_db():
    if "db" not in g:
        connection = sqlite3.connect(current_app.config["DATABASE_PATH"], timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        g.db = connection
    return g.db


def close_db(error=None):
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


def init_db():
    path = Path(current_app.config["DATABASE_PATH"])
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = get_db()
    connection.execute("PRAGMA journal_mode = WAL")
    schema = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
    with connection:
        connection.executescript(schema)
    domain = Path(__file__).parent / "models" / "domain.sql"
    connection.executescript(domain.read_text(encoding="utf-8"))


@click.command("init-db")
@with_appcontext
def init_db_command():
    """Crea el esquema pendiente sin borrar datos existentes."""
    init_db()
    click.echo("Base de datos inicializada; datos existentes conservados.")


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
    with app.app_context():
        init_db()
