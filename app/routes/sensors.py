import csv
import io

from flask import Blueprint, Response, jsonify, request

from app.models.repository import history, latest, types

bp = Blueprint("sensors", __name__, url_prefix="/api/sensors")


@bp.get("/latest")
def current():
    return jsonify(latest())


@bp.get("/types")
def sensor_types():
    return jsonify(types())


@bp.get("/history/<variable>")
def historical(variable):
    rows = history(variable, request.args.get("start"), request.args.get("end"), int(request.args.get("limit", 1000)))
    if request.args.get("format") != "csv":
        return jsonify(rows)
    buffer = io.StringIO()
    fields = ["id", "variable", "value", "unit", "measured_at", "received_at", "stored_at", "device_id", "source", "transport_ms", "storage_ms"]
    writer = csv.DictWriter(buffer, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return Response(buffer.getvalue(), mimetype="text/csv", headers={"Content-Disposition": f'attachment; filename="{variable}.csv"'})
