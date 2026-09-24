"""Generate a small original motion sample, with deliberately uneven GIF delays."""
from pathlib import Path
import math
import numpy as np
from PIL import Image


def make_demo():
    y, x = np.mgrid[-1:1:240j, -1.333:1.333:320j]
    frames = []
    for index in range(36):
        angle = index * math.tau / 36
        cx, cy = .18 * math.cos(angle), .12 * math.sin(angle)
        xx, yy = x - cx, y - cy
        theta = np.arctan2(yy, xx)
        radius = np.hypot(xx, yy)
        ring = np.exp(-((radius - .55 - .08 * np.sin(theta * 3 + angle)) / .11) ** 2)
        orb = np.exp(-((xx + .38 * math.cos(angle)) ** 2 + (yy + .38 * math.sin(angle)) ** 2) / .02)
        glow = np.exp(-(radius / .8) ** 2)
        values = np.stack([18 + 180 * ring + 70 * orb + 15 * glow,
                           14 + 120 * ring + 160 * orb + 10 * glow,
                           25 + 220 * ring + 70 * orb + 20 * glow], axis=-1)
        frames.append(Image.fromarray(np.uint8(np.clip(values, 0, 255))))
    path = Path(__file__).parent / 'web' / 'demo.gif'
    frames[0].save(path, save_all=True, append_images=frames[1:],
                   duration=[60 if i % 3 else 100 for i in range(36)], loop=0, disposal=2)
    return path


if __name__ == '__main__':
    print(make_demo())
