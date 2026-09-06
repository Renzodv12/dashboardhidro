import time
from types import SimpleNamespace
from app.db import get_db
from app.models.repository import parameter, set_parameter
from app.services.pid_service import PID, DEFAULT, ControlService
from app.services.simulation_service import Plant


def test_closed_loop_and_antiwindup():
    plant=Plant(); plant.disturbance('ph',.8); pid=PID()
    for i in range(90):
        output=pid.compute(plant.values['ph'],1,DEFAULT)
        assert -40<=output<=40
        plant.command(output,now=i)
        plant.step(1,now=i+1)
    assert abs(plant.values['ph']-DEFAULT['setpoint'])<.05
    for _ in range(100):
        pid.compute(14,1,DEFAULT)
    assert abs(pid.integral)<5


def test_emergency_survives_restart(app):
    mqtt=SimpleNamespace(app=app,connected=False,publish=lambda *a:None)
    with app.app_context():
        ctrl=ControlService(mqtt)
        ctrl.operate('emergency',{},None)
        assert ControlService(mqtt).status()['mode']=='emergency'
        ctrl.operate('reset',{},None)
        assert ctrl.status()['mode']=='manual'


def test_stale_data_cannot_dose(app):
    mqtt=SimpleNamespace(app=app,connected=True,publish=lambda *a:None)
    with app.app_context():
        ctrl=ControlService(mqtt)
        with get_db(): set_parameter('control_mode','automatic')
        ctrl.last_tick=time.monotonic()-2
        ctrl.tick()
        assert ctrl.output==0 and not ctrl.fresh


def test_dose_budget_survives_rearm(app):
    mqtt=SimpleNamespace(app=app,connected=True,publish=lambda *a:None)
    with app.app_context():
        ctrl=ControlService(mqtt)
        with get_db(): set_parameter('dose_history',[[time.time(),12.]])
        ctrl.operate('reset',{},None)
        ctrl.operate('mode',{'mode':'automatic'},None)
        ctrl.last_tick=time.monotonic()-2
        ctrl.tick()
        assert ctrl.output==0
        assert parameter('control_mode','manual')=='emergency'


def test_wrong_device_never_enables_control(app):
    from app.models.repository import store_reading, utcnow
    mqtt=SimpleNamespace(app=app,connected=True,publish=lambda *a:None)
    with app.app_context():
        ctrl=ControlService(mqtt)
        for variable,value,unit in [('ph',7.,'pH'),('nivel',78.,'%')]:
            store_reading(dict(device_id='other-device',variable=variable,value=value,unit=unit,timestamp=utcnow()))
        ctrl.operate('mode',{'mode':'automatic'},None)
        ctrl.last_tick=time.monotonic()-2
        ctrl.tick()
        assert not ctrl.fresh and ctrl.output==0
