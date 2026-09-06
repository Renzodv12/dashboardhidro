import cv2
import numpy as np
import pytest
from app.services.vision_service import analyze


def test_green_coverage_and_roi(app,tmp_path):
    app.config['IMAGES_PATH']=str(tmp_path)
    app.config['PROCESSED_PATH']=str(tmp_path/'processed')
    image=np.zeros((100,100,3),np.uint8)
    image[:,:50]=(0,255,0)
    cv2.imwrite(str(tmp_path/'plant.png'),image)
    with app.app_context():
        result=analyze('plant.png')
        assert 49<=result['coverage']<=51
        assert (tmp_path/'processed'/result['processed_image']).exists()
        assert analyze('plant.png',[0,0,40,100])['coverage']==100
        with pytest.raises(ValueError): analyze('../plant.png')
        with pytest.raises(ValueError): analyze('plant.png',[99,0,50,50])
