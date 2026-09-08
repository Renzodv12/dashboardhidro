import json
import numpy as np
import pytest
from ml.hydrogrow import FEATURES, assign_splits, features, fit, metrics, predict


def test_experiments_stay_separate_and_duplicates_are_removed():
    rows = [dict(experiment=e,date=d,member=f'{d}/{i}.png',sha256=h)
            for i,(e,d,h) in enumerate([
                ('Month1','2024-03-09','a'), ('Month1','2024-03-12','b'),
                ('Month2','2024-04-16','c'), ('Month2','2024-04-18','a'),
                ('Month3','2024-05-01','d')])]
    result = assign_splits(rows)
    assert len(result) == 4
    assert [r['target_day'] for r in result] == [0,3,0,0]
    assert {r['experiment']:r['split'] for r in result} == {'Month1':'train','Month2':'validation','Month3':'test'}
    hashes = [{r['sha256'] for r in result if r['split']==s} for s in ['train','validation','test']]
    assert not hashes[0] & hashes[1] and not hashes[0] & hashes[2] and not hashes[1] & hashes[2]


def test_unknown_experiment_rejected():
    with pytest.raises(ValueError,match='Experimento'):
        assign_splits([dict(experiment='unknown',date='2024-01-01')])


def test_features_ignore_plant_position_and_measure_area():
    left = np.zeros((100,100,3),dtype=np.uint8)
    right = left.copy()
    left[10:30,10:30] = [20,150,20]
    right[60:80,60:80] = [20,150,20]
    values = features(left)
    assert len(values) == len(FEATURES)
    assert values[0] == pytest.approx(.04)
    assert values[1] == pytest.approx(.04)
    np.testing.assert_allclose(values,features(right))


def test_empty_image_rejected():
    with pytest.raises(ValueError):
        features(np.zeros((100,100,3),dtype=np.uint8))
    with pytest.raises(ValueError):
        features(None)


def test_ridge_learns_signal_and_json_roundtrip():
    rng = np.random.default_rng(42)
    x = rng.normal(size=(200,len(FEATURES)))
    x[:,-1] = 1  # También debe admitir una característica constante.
    y = 4*x[:,0]-2*x[:,1]+10
    model = fit(x[:150],y[:150],.1)
    restored = json.loads(json.dumps(model))
    assert metrics(y[150:],predict(restored,x[150:]))['mae_days'] < .02
    np.testing.assert_allclose(model['mean'],x[:150].mean(axis=0))


def test_metrics_and_invalid_training():
    assert metrics([1,2,3],[1,2,3]) == dict(mae_days=0,rmse_days=0,r2=1)
    with pytest.raises(ValueError):
        fit([[float('nan')]], [1], 1)


def test_remote_zip_range_extraction_and_integrity(monkeypatch):
    import io
    import zipfile
    from scripts import download_hydrogrow as download
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('Data/2024-03-09/sample.png',b'example pixels'*100)
    content = buffer.getvalue()
    monkeypatch.setattr(download,'fetch',lambda url,start,end:content[start:end+1])
    with zipfile.ZipFile(download.RemoteZip('https://example.test/archive',len(content))) as archive:
        info = archive.infolist()[0]
    assert download.extract_member('https://example.test/archive',info) == b'example pixels'*100
    info.CRC += 1
    with pytest.raises(ValueError,match='CRC'):
        download.extract_member('https://example.test/archive',info)
