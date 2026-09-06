from app.models.repository import store_reading, utcnow


def test_latest_history_and_csv(app, client):
    assert len(client.get("/api/sensors/latest").json) == 6
    with app.app_context():
        store_reading(dict(device_id="simulator-01", variable="ph", value=6.2, unit="pH", timestamp=utcnow()))
    assert client.get("/api/sensors/latest").json[0]["value"] == 6.2
    assert client.get("/api/sensors/history/ph").json[0]["unit"] == "pH"
    response = client.get("/api/sensors/history/ph?format=csv")
    assert response.mimetype == "text/csv"
    assert "transport_ms" in response.text
    assert client.get("/api/sensors/history/ph?limit=-1").status_code == 400
    assert client.get("/api/sensors/history/ph?start=bad").status_code == 400
