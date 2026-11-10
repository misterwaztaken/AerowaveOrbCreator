"""
helpers.py

contains small helper functions used throughout AOC
(from Aerowave Orb Creator)
"""

from .common import *

# ======================================================================================
#  Small helpers
# ======================================================================================
def clamp01(x):
    return 0.0 if x < 0.0 else (1.0 if x > 1.0 else x)


def smooth(x):
    x = clamp01(x)
    return x * x * (3.0 - 2.0 * x)


def ease_out_quart(x):
    x = clamp01(x)
    return 1.0 - (1.0 - x) ** 4


def get_font(size, bold=False):
    names = (["seguisb.ttf", "segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf"]
             if bold else ["segoeui.ttf", "arial.ttf", "DejaVuSans.ttf", "LiberationSans-Regular.ttf"])
    for n in names:
        try:
            return ImageFont.truetype(n, size)
        except Exception:
            continue
    return ImageFont.load_default()


def hex_to_rgb(h):
    return int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)
