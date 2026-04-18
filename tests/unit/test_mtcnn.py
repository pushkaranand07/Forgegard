import cv2
import numpy as np
import urllib.request
import torch
import sys
import os

# Set up Django context path to allow importing ml_core
sys.path.insert(0, os.path.abspath('..'))
from ml_core.video_model.vmd import get_face_extractor

url = 'https://upload.wikimedia.org/wikipedia/commons/thumb/a/a0/Pierre-Person.jpg/220px-Pierre-Person.jpg'
req = urllib.request.urlopen(url)
arr = np.asarray(bytearray(req.read()), dtype=np.uint8)
img = cv2.imdecode(arr, -1) # BGR
rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

extractor = get_face_extractor('cpu')
face = extractor.extract_face(rgb_img)

if face is not None:
    print('FACE DETECTED SUCCESSFULLY!')
    print('Shape:', face.shape)
else:
    print('NO FACE DETECTED!')
