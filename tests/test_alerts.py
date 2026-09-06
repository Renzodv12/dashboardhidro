from app.models.repository import store_reading, utcnow
from app.services.alert_service import evaluate, list_alerts

def test_alert_dedup_and_recovery(app):
    with app.app_context():
        for i,value in enumerate([7,7.1,6.2]):
            r=store_reading(dict(device_id='simulator-01',variable='ph',value=value,unit='pH',timestamp=utcnow(),message_id=str(i)))
            evaluate(r)
            assert len(list_alerts()) == (0 if i==2 else 1)
        assert len(list_alerts(False))==1
        assert list_alerts(False)[0]['resolved_at'] is not None
