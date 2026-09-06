"""Genera un patrón sintético para probar HSV; no es una foto ni evidencia de cultivo."""
from pathlib import Path
import cv2
import numpy as np
root=Path(__file__).resolve().parents[1]
image=np.full((480,640,3),45,dtype=np.uint8)
for center,angle in [((240,190),-35),((380,190),35),((220,310),-60),((400,310),60)]:
    cv2.ellipse(image,center,(100,45),angle,0,360,(40,160,65),-1)
cv2.line(image,(320,390),(320,120),(30,100,40),12)
cv2.putText(image,'PATRON SINTETICO - NO CULTIVO REAL',(25,455),cv2.FONT_HERSHEY_SIMPLEX,.65,(230,230,230),1)
path=root/'data/images/demo-sintetica.png'
path.parent.mkdir(parents=True,exist_ok=True)
if not cv2.imwrite(str(path),image): raise RuntimeError('No se pudo guardar el patrón')
print(path)
