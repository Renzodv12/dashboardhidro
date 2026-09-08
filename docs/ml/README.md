# Experimento ML: HydroGrowNet v3

Este módulo es una ampliación **experimental y opcional** del alcance original
OpenCV de la tesis. No modifica Flask, la segmentación existente ni el PID.

Resultados ejecutados: [RESULTADOS.md](RESULTADOS.md).

## Qué aprende

Regresión Ridge para estimar el **día relativo desde la primera fecha disponible
del experimento** a partir de una imagen ya segmentada con fondo negro.
La etiqueta se deriva de la carpeta de fecha del dataset. No es una anotación de
edad real de la planta, biomasa, rendimiento, salud o velocidad de crecimiento.
No hay predicción de crecimiento futuro. No se utilizan fechas, nombres de archivo,
experimento ni lecturas de sensores como entradas del modelo.

Las 25 entradas incluyen proporción de primer plano y de píxeles verdes,
dimensiones relativas de su caja envolvente, ocupación de esa caja y estadísticas
de color HSV. No se usa la posición de la planta en la imagen. La segmentación
previa pertenece a los autores; este modelo no reemplaza ni entrena YOLO.

## Procedencia y licencia

Shalash, Omar; Hassan, Nayira; Metwalli, Ahmed; Elhefny, Alia (2025),
**HydroGrowNet of Batavia Dataset**, Mendeley Data, versión 3.
DOI: https://doi.org/10.17632/g6cm3v3wdp.3
Licencia del dataset: **CC BY 4.0**, https://creativecommons.org/licenses/by/4.0/.
Publicación indicada por los autores: https://doi.org/10.2139/ssrn.5079228.

Los datos proceden de lechuga Batavia en NFT. La tesis propone DWC: no se ha
validado transferencia a ese sistema ni a una cámara propia. La página describe
sensores e imágenes, pero la inspección de los archivos y `inventory.json`
determina qué material se usa realmente; este experimento usa solamente PNG.
Las métricas y el modelo son resultados derivados, no resultados de los autores.

## Reproducir

Desde la raíz del proyecto, con Python 3.9 o posterior y curl:

```bash
.venv/bin/python -m pip install -r requirements-ml.txt
.venv/bin/python scripts/download_hydrogrow.py --per-day 12
.venv/bin/python scripts/train_hydrogrow.py
.venv/bin/python scripts/plot_hydrogrow.py
.venv/bin/python -m pytest tests/test_hydrogrow.py -q
```

La descarga usa HTTP Range: lee índices y miembros seleccionados, no los ZIP
completos. Selecciona hasta 12 imágenes por fecha con semilla determinista;
valida tamaño y CRC de cada PNG y registra SHA-256. Se puede reanudar ejecutando
el mismo comando: reutiliza imágenes locales con CRC válido. Los hashes completos
de los ZIP del proveedor se conservan en `data/ml/hydrogrow/source-files.json`,
pero **no se verifican los ZIP completos** al descargar por rangos. Los índices
se cachean localmente. Los datos descargados están excluidos de Git.

## Evaluación sin mezclar experimentos

- Month1: entrenamiento y cálculo exclusivo de normalización.
- Month2: validación para elegir alpha entre 0.1, 1, 10, 100 y 1000.
- Month3: prueba reservada, evaluada después de seleccionar alpha.

Se eliminan duplicados exactos SHA-256 antes de entrenar, conservando la primera
ocurrencia en orden de experimento. No se usa una partición aleatoria de imágenes
entre entrenamiento y prueba. Dentro de cada mes puede haber tomas correlacionadas;
la muestra pequeña y los tres únicos experimentos limitan la generalización.
No hay identificación persistente de planta verificada: separar meses no demuestra
por sí solo independencia biológica. Las fechas son días disponibles, no se
presupone que cada mes contenga 30 días consecutivos.

Referencia: predecir siempre la mediana de las etiquetas de entrenamiento.
Se informan MAE y RMSE en días y R². R² negativo indica peor ajuste que la media
del conjunto evaluado. No se recortan predicciones a 0..30 para ocultar errores.
La métrica de prueba no se utiliza para retocar parámetros en esta entrega.

## Evidencias y uso

- `metrics.json`: tamaños, rechazos, duplicados, parámetros y métricas.
- `sample-manifest.json`: rutas originales, fechas y hashes de la muestra.
- `inventory.json`: conteos reales del contenido de los tres ZIP.
- `predictions.csv`: etiqueta, predicción y referencia por imagen.
- `model.json`: coeficientes y normalización legibles; no usa pickle.
- `evaluation.png`: predicciones y error por día en el tercer experimento.

Para ejecutar una predicción local sobre una imagen de la muestra:

```bash
.venv/bin/python scripts/predict_hydrogrow.py data/ml/hydrogrow/images/ARCHIVO.png
```

Reemplazar ARCHIVO por una ruta del manifiesto. No aplicar directamente a fotos
sin segmentar de una webcam: el fondo cambiaría las características. La salida
es exploratoria, **no diagnóstico agronómico**, no certifica edad ni madurez y no
se conecta a actuadores. Antes de integrarlo al panel habría que definir un objetivo
agronómico medido y validarlo con capturas propias y anotaciones independientes.
