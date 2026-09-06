from flask import Blueprint, jsonify, request
from app.services.alert_service import list_alerts
bp = Blueprint('alerts', __name__, url_prefix='/api/alerts')

@bp.get('')
def alerts():
    status=request.args.get('status','active')
    if status not in {'active','all'}:
        raise ValueError('Estado inválido')
    return jsonify(list_alerts(status=='active'))
