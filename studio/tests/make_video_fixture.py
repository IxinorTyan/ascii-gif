"""Local video fixture for browser import checks, derived from our original GIF demo."""
from pathlib import Path
import cv2
import numpy as np
from PIL import Image

studio = Path(__file__).resolve().parents[1]
output = studio / '.test-artifacts'
output.mkdir(exist_ok=True)
path = output / 'sample.avi'
writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*'MJPG'), 20, (320, 240))
if not writer.isOpened():
    raise RuntimeError('VideoWriter unavailable')
try:
    with Image.open(studio / 'web/demo.gif') as gif:
        for index in range(gif.n_frames):
            gif.seek(index)
            writer.write(cv2.cvtColor(np.asarray(gif.convert('RGB')), cv2.COLOR_RGB2BGR))
finally:
    writer.release()
print(path)
