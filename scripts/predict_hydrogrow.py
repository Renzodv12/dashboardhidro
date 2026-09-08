"""Inferencia exploratoria SOLO sobre PNG ya segmentado con fondo negro como HydroGrowNet."""
import argparse
import json
from pathlib import Path
import sys
import cv2
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from ml.hydrogrow import features, predict
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('image',type=Path)
args=parser.parse_args()
model=json.loads((ROOT/'docs/ml/model.json').read_text())
value=float(predict(model,features(cv2.imread(str(args.image)))))
print(json.dumps({'estimated_relative_experiment_day':value,
                  'warning':'Experimental: no estima edad real, salud, peso ni crecimiento futuro; no controla actuadores.'},ensure_ascii=False,indent=2))
