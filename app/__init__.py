"""Factoría Flask: importar este módulo no inicia servidores ni conexiones."""

from pathlib import Path

from flask import Flask, jsonify, request

from config import BASE_DIR, load_config
from app import db


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(load_config())
    if test_config:
        app.config.update(test_config)

    path = Path(app.config["DATABASE_PATH"]).expanduser()
    if not path.is_absolute():
        path = BASE_DIR / path
    app.config["DATABASE_PATH"] = str(path.resolve())
    app.logger.setLevel(app.config["LOG_LEVEL"])
    db.init_app(app)

    from app.routes.dashboard import bp as dashboard_bp
    from app.routes.api import bp as api_bp
    from app.routes.sensors import bp as sensors_bp
    from app.routes.alerts import bp as alerts_bp
    from app.routes.control import bp as control_bp
    from app.routes.vision import bp as vision_bp
    from app.routes.settings import bp as settings_bp
    from app.routes import auth

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(sensors_bp)
    app.register_blueprint(alerts_bp)
    app.register_blueprint(control_bp)
    app.register_blueprint(vision_bp)
    app.register_blueprint(settings_bp)
    auth.init_app(app)

    from werkzeug.exceptions import HTTPException

    @app.errorhandler(HTTPException)
    def http_error(error):
        if request.path.startswith('/api/'):
            return jsonify(error=error.description), error.code
        return error

    @app.errorhandler(RuntimeError)
    def unavailable(error):
        return jsonify(error=str(error)), 503

    @app.errorhandler(ValueError)
    def invalid_input(error):
        return jsonify(error=str(error)), 400

    @app.errorhandler(404)
    def not_found(error):
        if request.path.startswith("/api/"):
            return jsonify(error="Recurso no encontrado"), 404
        return "Página no encontrada", 404

    @app.errorhandler(500)
    def server_error(error):
        if request.path.startswith("/api/"):
            return jsonify(error="Error interno del sistema"), 500
        return "Error interno del sistema", 500

    app.logger.info("Backend iniciado; esquema SQLite preparado")
    return app
