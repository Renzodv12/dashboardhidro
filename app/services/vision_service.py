"""Segmentación HSV determinista; cobertura por píxeles, sin diagnóstico."""
import json
import os
import uuid
from pathlib import Path

os.environ.setdefault('OPENCV_IO_MAX_IMAGE_PIXELS','20000000')
import cv2
import numpy as np
from flask import current_app

from app.db import get_db
from app.models.repository import audit, utcnow


def image_path(filename, processed=False):
    if not isinstance(filename,str) or not filename or Path(filename).name!=filename:
        raise ValueError('Nombre de archivo inválido')
    root=Path(current_app.config['PROCESSED_PATH' if processed else 'IMAGES_PATH']).resolve()
    path=(root/filename).resolve()
    if path.parent!=root or path.suffix.lower() not in {'.jpg','.jpeg','.png'}:
        raise ValueError('Se requiere una imagen JPG o PNG dentro del directorio configurado')
    return path


def analyze(filename, roi=None, user_id=None):
    path=image_path(filename)
    if not path.is_file() or path.stat().st_size>20*1024*1024:
        raise ValueError('Imagen inexistente o mayor a 20 MB')
    try:
        image=cv2.imread(str(path))
    except cv2.error:
        raise ValueError('Imagen inválida o demasiado grande') from None
    if image is None:
        raise ValueError('No se pudo decodificar la imagen')
    height,width=image.shape[:2]
    if roi is not None:
        if not isinstance(roi,list) or len(roi)!=4 or any(type(v) is not int for v in roi):
            raise ValueError('ROI debe contener cuatro enteros [x,y,ancho,alto]')
        x,y,w,h=roi
        if x<0 or y<0 or w<=0 or h<=0 or x+w>width or y+h>height:
            raise ValueError('ROI fuera de la imagen')
        image=image[y:y+h,x:x+w]
    else:
        roi=[0,0,width,height]
    scale=min(1.,1280/max(image.shape[:2]))
    image=cv2.resize(image,None,fx=scale,fy=scale,interpolation=cv2.INTER_AREA) if scale<1 else image
    hsv=cv2.cvtColor(image,cv2.COLOR_BGR2HSV)
    mask=cv2.inRange(hsv,np.array([35,40,40],dtype=np.uint8),np.array([85,255,255],dtype=np.uint8))
    kernel=np.ones((3,3),np.uint8)
    mask=cv2.morphologyEx(mask,cv2.MORPH_OPEN,kernel)
    mask=cv2.morphologyEx(mask,cv2.MORPH_CLOSE,kernel)
    contours,_=cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    overlay=image.copy()
    cv2.drawContours(overlay,contours,-1,(0,0,255),2)
    area=int(cv2.countNonZero(mask))
    coverage=area/mask.size*100
    processed=f'{uuid.uuid4().hex}.jpg'
    output=image_path(processed,True)
    output.parent.mkdir(parents=True,exist_ok=True)
    if not cv2.imwrite(str(output),overlay):
        raise RuntimeError('No se pudo guardar la imagen procesada')
    observations=f'HSV H=35..85 S>=40 V>=40; escala={scale:.4f}; área en píxeles procesados; contornos={len(contours)}. No es diagnóstico agronómico.'
    with get_db() as db:
        cursor=db.execute('INSERT INTO visual_analysis(filename,timestamp,green_area,coverage,processed_image,observations,roi_json) VALUES (?,?,?,?,?,?,?)',
                          (filename,utcnow(),area,coverage,processed,observations,json.dumps(roi)))
        audit('vision.analyze',filename,user_id)
    current_app.logger.info('OpenCV: %s cobertura %.2f%%',filename,coverage)
    return dict(get_db().execute('SELECT * FROM visual_analysis WHERE id=?',(cursor.lastrowid,)).fetchone())


def capture(user_id=None):
    camera=cv2.VideoCapture(current_app.config['CAMERA_INDEX'])
    try:
        ok,frame=camera.read()
        if not ok:
            raise ValueError('Webcam no disponible en el servidor')
        filename=f'camera-{uuid.uuid4().hex}.jpg'
        path=image_path(filename)
        path.parent.mkdir(parents=True,exist_ok=True)
        if not cv2.imwrite(str(path),frame):
            raise RuntimeError('No se pudo guardar la captura')
    finally:
        camera.release()
    return analyze(filename,user_id=user_id)
