import pytest
from app.models.repository import store_reading, utcnow, history, latest


def message(**changes):
    return dict(device_id="simulator-01", variable="ph", value=6.2, unit="pH",
                timestamp=utcnow(), source="simulator", **changes)


def test_storage_deduplication(app):
    with app.app_context():
        payload = message(message_id="one")
        assert store_reading(payload)["storage_ms"] >= 0
        assert store_reading(payload) is None
        assert len(history("ph")) == 1
        assert latest()[0]["value"] == 6.2


@pytest.mark.parametrize("field,value", [("value",float("nan")),("value",True),("value",15),
    ("unit","ppm"),("device_id","../../"),("timestamp","2026-09-06T12:00:00")])
def test_invalid_reading(app, field, value):
    with app.app_context():
        payload = message()
        payload[field] = value
        with pytest.raises(ValueError):
            store_reading(payload)
