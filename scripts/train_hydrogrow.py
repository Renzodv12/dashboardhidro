"""Entrena y evalúa una línea base reproducible con experimentos separados."""
import csv
import hashlib
import json
from pathlib import Path
import platform
import sys
from datetime import datetime, timezone
import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ml.hydrogrow import FEATURES, assign_splits, features, fit, predict, metrics


def main():
    folder = ROOT/'data/ml/hydrogrow'
    output = ROOT/'docs/ml'
    output.mkdir(exist_ok=True)
    raw = json.loads((folder/'manifest.json').read_text())
    rows, rejected = [], []
    for row in assign_splits(raw):
        path = ROOT/row['path']
        if hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']:
            raise ValueError('Hash de imagen inválido: '+row['path'])
        try:
            vector = features(cv2.imread(str(path)))
        except ValueError as error:
            rejected.append({'member': row['member'], 'experiment': row['experiment'], 'reason': str(error)})
            continue
        rows.append(dict(row, vector=vector.tolist()))
    sets = {split:[r for r in rows if r['split']==split] for split in ['train','validation','test']}
    if any(len(group)<20 for group in sets.values()):
        raise ValueError('Se requieren al menos 20 muestras en cada experimento')
    def arrays(split):
        return np.array([r['vector'] for r in sets[split]]), np.array([r['target_day'] for r in sets[split]])
    xtrain, ytrain = arrays('train')
    xval, yval = arrays('validation')
    candidates = []
    for alpha in [0.1, 1., 10., 100., 1000.]:
        model = fit(xtrain, ytrain, alpha)
        candidates.append((metrics(yval, predict(model, xval))['mae_days'], alpha, model))
    _, _, model = min(candidates, key=lambda item:item[0])
    # Test se evalúa una sola vez, después de elegir alpha con validation.
    report = {'created_at': datetime.now(timezone.utc).isoformat(),
              'dataset': 'https://doi.org/10.17632/g6cm3v3wdp.3', 'seed': 42,
              'task': model['target'], 'model': 'ridge regression, standardized image features',
              'selected_alpha': model['alpha'],
              'validation_candidates': [{'alpha':a,'mae_days':m} for m,a,_ in candidates],
              'raw_samples':len(raw), 'exact_duplicates_removed':len(raw)-len(assign_splits(raw)),
              'rejected_images': rejected, 'features': FEATURES,
              'versions': {'python':platform.python_version(),'numpy':np.__version__,'opencv':cv2.__version__},
              'splits': {}, 'deployment': 'experimental_offline_only'}
    predictions = []
    for split, group in sets.items():
        x,y = arrays(split)
        values = predict(model, x)
        baseline = np.full(len(y), np.median(ytrain))
        report['splits'][split] = {'experiment': group[0]['experiment'], 'images':len(y),
            'dates':len(set(r['date'] for r in group)), 'target_range_days':[int(y.min()),int(y.max())],
            'model':metrics(y,values), 'baseline_train_median':metrics(y,baseline)}
        for row, value, base in zip(group, values, baseline):
            predictions.append({k:row[k] for k in ['experiment','split','date','member','sha256','target_day']})
            predictions[-1].update(predicted_day=float(value), baseline_day=float(base))
    report['test_beats_baseline'] = report['splits']['test']['model']['mae_days'] < report['splits']['test']['baseline_train_median']['mae_days']
    (output/'metrics.json').write_text(json.dumps(report,indent=2)+'\n')
    (folder/'model.json').write_text(json.dumps(model,indent=2)+'\n')
    # Artefactos pequeños y auditables se versionan; no se usa pickle ni código serializado.
    (output/'model.json').write_text(json.dumps(model,indent=2)+'\n')
    (output/'sample-manifest.json').write_text(json.dumps(raw,indent=2)+'\n')
    (output/'inventory.json').write_text((folder/'inventory.json').read_text())
    with (output/'predictions.csv').open('w') as f:
        writer=csv.DictWriter(f,fieldnames=list(predictions[0]),lineterminator='\n');writer.writeheader();writer.writerows(predictions)
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()
