from tkinter import *
from tkinter import ttk
from tkinter import filedialog
import cv2
import os
import sys
from PIL import Image, ImageFont, ImageDraw, ImageTk
import numpy as np
import ffmpeg
from ast import literal_eval
from copy import deepcopy

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(project_root)
sys.path.append(project_root)
sys.path.append(os.path.join(project_root, 'scripts'))
with open(os.path.join(project_root, 'scripts', 'Ascii Converter.py'), encoding='utf-8') as f:
    exec(f.read(), globals())
