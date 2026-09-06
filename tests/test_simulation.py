from app.services.simulation_service import Plant


def test_gradual_and_reproducible():
    a, b = Plant(), Plant()
    for _ in range(30):
        previous = a.values["ph"]
        assert a.step(1) == b.step(1)
        assert abs(a.values["ph"] - previous) < 0.01


def test_actuation_and_watchdog():
    plant = Plant()
    plant.disturbance("ph", .8)
    plant.command(-40, now=0)
    assert plant.step(1, now=1)["ph"] < 7
    plant.step(1, now=4)
    assert plant.output == 0
