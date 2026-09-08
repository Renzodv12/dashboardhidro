"""Figura reproducible de predicciones del experimento reservado."""
import csv
import os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'data/ml/.matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
folder=ROOT/'docs/ml'
with (folder/'predictions.csv').open() as f:
    rows=[r for r in csv.DictReader(f) if r['split']=='test']
y=np.array([float(r['target_day']) for r in rows])
p=np.array([float(r['predicted_day']) for r in rows])
b=np.array([float(r['baseline_day']) for r in rows])
fig,axes=plt.subplots(1,2,figsize=(11,4.5),layout='constrained')
axes[0].scatter(y,p,color='#28735b',alpha=.35,s=16,label='Imágenes de Month3')
axes[0].plot([y.min(),y.max()],[y.min(),y.max()],color='#64736d',linestyle='--',label='Predicción exacta')
axes[0].set(xlabel='Día relativo observado',ylabel='Día relativo estimado',title='Prueba en experimento no usado al entrenar')
axes[0].legend(frameon=False,fontsize=8)
days=np.unique(y)
axes[1].plot(days,[np.abs(p[y==d]-d).mean() for d in days],marker='o',color='#28735b',label='Modelo Ridge')
axes[1].plot(days,[np.abs(b[y==d]-d).mean() for d in days],linestyle='--',color='#a88448',label='Referencia: mediana de entrenamiento')
axes[1].set(xlabel='Día relativo observado',ylabel='Error absoluto medio (días)',title='Error por día de captura')
axes[1].legend(frameon=False,fontsize=8)
for ax in axes:
    ax.spines[['top','right']].set_visible(False)
    ax.grid(alpha=.15)
fig.suptitle('HydroGrowNet v3 · evaluación exploratoria, no diagnóstico',fontsize=12)
fig.savefig(folder/'evaluation.png',dpi=160)
plt.close(fig)
