"""Regresión exploratoria del día relativo del experimento, no edad ni diagnóstico."""
from datetime import date
import cv2
import numpy as np

FEATURES = ['foreground_fraction', 'green_fraction', 'bbox_width', 'bbox_height',
            'bbox_fill', 'h_mean', 'h_std', 's_mean', 's_std', 'v_mean', 'v_std',
            'v_q25', 'v_q75'] + [f'hue_bin_{i}' for i in range(12)]
SPLITS = {'Month1': 'train', 'Month2': 'validation', 'Month3': 'test'}


def features(image):
    if image is None or image.ndim != 3 or image.shape[2] != 3:
        raise ValueError('Se requiere imagen BGR válida')
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    mask = image.max(axis=2) > 10  # Fondo negro de las imágenes ya segmentadas por el autor.
    count = int(mask.sum())
    if count < 20:
        raise ValueError('Imagen sin suficiente primer plano')
    y, x = np.where(mask)
    height, width = mask.shape
    w, h = x.max()-x.min()+1, y.max()-y.min()+1
    pixels = hsv[mask].astype(float) / [180., 255., 255.]
    green = ((hsv[:,:,0] >= 35) & (hsv[:,:,0] <= 85) & (hsv[:,:,1] >= 40) & (hsv[:,:,2] >= 40) & mask).sum()
    values = [count/mask.size, green/mask.size, w/width, h/height, count/(w*h)]
    for c in range(3):
        values.extend([pixels[:,c].mean(), pixels[:,c].std()])
    values.extend(np.quantile(pixels[:,2], [.25, .75]))
    hist, _ = np.histogram(hsv[:,:,0][mask], bins=12, range=(0,180))
    values.extend(hist/count)
    return np.asarray(values, dtype=float)


def assign_splits(records):
    """El mes entero queda en un único split; duplicados exactos conservan el primero."""
    origins = {}
    for row in records:
        exp = row['experiment']
        if exp not in SPLITS:
            raise ValueError('Experimento desconocido')
        day = date.fromisoformat(row['date'])
        origins[exp] = min(origins.get(exp, day), day)
    result, seen = [], set()
    for row in sorted(records, key=lambda r:(r['experiment'], r['date'], r['member'])):
        if row['sha256'] in seen:
            continue
        seen.add(row['sha256'])
        result.append(dict(row, split=SPLITS[row['experiment']],
                           target_day=(date.fromisoformat(row['date'])-origins[row['experiment']]).days))
    return result


def fit(x, y, alpha):
    x, y = np.asarray(x, float), np.asarray(y, float)
    if not np.isfinite(x).all() or not np.isfinite(y).all() or alpha <= 0:
        raise ValueError('Datos o regularización inválidos')
    mean, scale = x.mean(axis=0), x.std(axis=0)
    scale[scale < 1e-12] = 1
    z = (x-mean)/scale
    intercept = float(y.mean())
    gram = np.einsum('ni,nj->ij', z, z)
    rhs = np.einsum('ni,n->i', z, y-intercept)
    weights = np.linalg.solve(gram+alpha*np.eye(z.shape[1]), rhs)
    return {'mean': mean.tolist(), 'scale': scale.tolist(), 'weights': weights.tolist(),
            'intercept': intercept, 'alpha': alpha, 'features': FEATURES,
            'target': 'days_since_first_recorded_date_in_experiment', 'experimental_only': True}


def predict(model, x):
    if model['features'] != FEATURES:
        raise ValueError('Versión de características incompatible')
    z = (np.asarray(x)-model['mean'])/model['scale']
    return np.einsum('...i,i->...', z, np.asarray(model['weights']))+model['intercept']


def metrics(y, prediction):
    y, prediction = np.asarray(y), np.asarray(prediction)
    error = prediction-y
    denom = np.sum((y-y.mean())**2)
    return {'mae_days': float(np.abs(error).mean()), 'rmse_days': float(np.sqrt((error**2).mean())),
            'r2': float(1-np.sum(error**2)/denom) if denom > 0 else None}
