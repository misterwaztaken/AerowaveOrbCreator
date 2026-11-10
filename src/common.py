"""
common.py

this script is responsible for handling all library imports,
app constants, theme dictionaries, the config save/load logic,
asset lookup, and the Sound class for "fire-and-forget" WAV playback 

(from Aerowave Orb Creator)
"""

import os
import sys
import json
import math
import time
import wave
import colorsys
import subprocess
import tkinter as tk
from tkinter import ttk, colorchooser, filedialog, messagebox
from PIL import Image, ImageDraw, ImageFilter, ImageTk, ImageChops, ImageFont, ImageEnhance

try:
    from PIL import ImageGrab
except Exception:                                   # pragma: no cover
    ImageGrab = None

try:
    import numpy as np
    HAVE_NUMPY = True
except Exception:                                   # pragma: no cover
    np = None
    HAVE_NUMPY = False

try:
    import winsound
except ImportError:                                 # not on Windows
    winsound = None

APP_NAME = "Aerowave Orb Creator"
CONFIG_NAME = "config.aero"

THEMES = {
    "Dark": {
        "ui_top": "#2b2b2b", "ui_bot": "#2b2b2b",
        "layer_top": "#3a3a3a", "layer_bot": "#3a3a3a",
        "btn_top": (74, 74, 74), "btn_bot": (58, 58, 58), "btn_mid": None, "btn_outline": None,
        "btn_fg": "white", "radius": 5, "fg": "white", 
        "layer_bg": "#4a4a4a", "layer_sel": "#5a7fa0", "panel_bg": "#2b2b2b"
    },
    "Aqua": {
        "ui_top": "#c8e0e0", "ui_bot": "#28a4c0",
        "layer_top": "#28a4c0", "layer_bot": "#c8e0e0",
        "btn_top": (240, 252, 248), "btn_bot": (64, 156, 176), "btn_mid": (120, 200, 216), "btn_outline": (8, 96, 120),
        "btn_fg": "black", "radius": 15, "fg": "black", 
        "layer_bg": "#79CBE8", "layer_sel": "#D2F0F9", "panel_bg": None
    },
    "Eco": {
        "ui_top": "#c5d7bd", "ui_bot": "#73a663",
        "layer_top": "#73a663", "layer_bot": "#c5d7bd",
        "btn_top": (158, 207, 141), "btn_bot": (76, 125, 59), "btn_mid": None, "btn_outline": (36, 125, 0),
        "btn_fg": "white", "radius": 8, "fg": "black", 
        "layer_bg": "#90B971", "layer_sel": "#407323", "panel_bg": None
    },
    # DORFic = Daylight, Orange, Red, Futurism, Graphic: white/grey surfaces with vivid orange accents (Special Thanks to Richard Likes Computers for information help on the aesthetic colours and design)
    "DORFic": {
        "ui_top": "#F7F8FA", "ui_bot": "#BCC1C9",
        "layer_top": "#FF7A1A", "layer_bot": "#FFB468",
        "btn_top": (255, 178, 96), "btn_bot": (214, 82, 0), "btn_mid": (255, 124, 28), "btn_outline": (150, 56, 0),
        "btn_fg": "white", "radius": 9, "fg": "#23262B",
        "layer_bg": "#F2F3F6", "layer_sel": "#FF6600", "layer_fg": "#2A2D33", "layer_sel_fg": "white",
        "panel_bg": None, "decor": "dorfic"
    }
}

# Order + artwork used by the UI Selector drop-down
THEME_ORDER = ["Dark", "Eco", "Aqua", "DORFic"]
THEME_ORBS = {"Dark": "darkbutton.png", "Eco": "ecobutton.png", "Aqua": "aquabutton.png", "DORFic": "dorficbutton.png"}

# Frosted "Aero glass" look of the drop-down and the pop-ups, per UI theme
GLASS = {
    "Dark": dict(tint=(16, 18, 22), tint_a=0.62, tint_grad=0.22, blur=10, gloss=0.16, shadow=165,
                 border_dark=190, border_light=110, text=(255, 255, 255), sub=(190, 198, 212),
                 accent=(96, 165, 240), dim=0.52, pill=(255, 255, 255),
                 entry_bg="#1E2024", entry_fg="#F2F2F2", edge="#585D66", list_bg="#1B1D21", list_alt="#22252A",
                 list_fg="#E8E8E8", list_sel="#3F73B0", list_sel_fg="#FFFFFF", list_head="#2B2E34"),
    "Aqua": dict(tint=(170, 228, 240), tint_a=0.50, tint_grad=0.16, blur=10, gloss=0.34, shadow=120,
                 border_dark=130, border_light=210, text=(6, 48, 66), sub=(22, 86, 106),
                 accent=(0, 165, 215), dim=0.70, pill=(255, 255, 255),
                 entry_bg="#F2FBFD", entry_fg="#06303F", edge="#3FA0BC", list_bg="#EEF9FC", list_alt="#E0F3F8",
                 list_fg="#06303F", list_sel="#0A8FB5", list_sel_fg="#FFFFFF", list_head="#BEE3EC"),
    "Eco": dict(tint=(150, 205, 130), tint_a=0.52, tint_grad=0.16, blur=10, gloss=0.30, shadow=130,
                border_dark=140, border_light=200, text=(14, 52, 10), sub=(36, 86, 26),
                accent=(46, 165, 24), dim=0.68, pill=(255, 255, 255),
                entry_bg="#F4FAF0", entry_fg="#14320E", edge="#5E9A45", list_bg="#F1F8EC", list_alt="#E6F1DE",
                list_fg="#14320E", list_sel="#407323", list_sel_fg="#FFFFFF", list_head="#C5DBB9"),
    "DORFic": dict(tint=(244, 246, 250), tint_a=0.60, tint_grad=0.14, blur=10, gloss=0.42, shadow=120,
                   border_dark=125, border_light=235, text=(34, 37, 43), sub=(112, 118, 130),
                   accent=(255, 102, 0), dim=0.72, pill=(255, 255, 255),
                   entry_bg="#FFFFFF", entry_fg="#22252B", edge="#B0B5BE", list_bg="#FAFAFC", list_alt="#F0F1F4",
                   list_fg="#22252B", list_sel="#FF6600", list_sel_fg="#FFFFFF", list_head="#E3E5EA"),
}


# ======================================================================================
#  Files, config, sound
# ======================================================================================
def app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def asset_path(name):
    """Find a bundled file next to the program, in ./assets, or inside a PyInstaller bundle."""
    folders = [app_dir(), os.path.join(app_dir(), "assets")]
    if getattr(sys, "_MEIPASS", None):
        folders += [sys._MEIPASS, os.path.join(sys._MEIPASS, "assets")]
    folders.append(os.getcwd())
    for f in folders:
        p = os.path.join(f, name)
        if os.path.isfile(p):
            return p
    return None


def _config_locations():
    locs = [os.path.join(app_dir(), CONFIG_NAME)]
    locs.append(os.path.join(os.path.expanduser("~"), ".aerowave_orb_creator", CONFIG_NAME))
    return locs


def load_config():
    for p in _config_locations():
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except Exception:
            continue
    return {}


def save_config(cfg):
    for p in _config_locations():
        try:
            os.makedirs(os.path.dirname(p), exist_ok=True)
            tmp = p + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2)
            os.replace(tmp, p)
            return True
        except Exception:
            continue
    return False


class Sound:
    """Fire-and-forget WAV playback (winsound on Windows, afplay / aplay elsewhere)."""

    @staticmethod
    def play(path):
        if not path or not os.path.isfile(path):
            return False
        try:
            if winsound is not None:
                winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
                return True
            if sys.platform == "darwin":
                subprocess.Popen(["afplay", path])
                return True
            for cmd in (["paplay"], ["aplay", "-q"], ["play", "-q"]):
                try:
                    subprocess.Popen(cmd + [path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    return True
                except Exception:
                    continue
        except Exception:
            pass
        return False

    @staticmethod
    def duration(path):
        try:
            with wave.open(path, "rb") as w:
                return w.getnframes() / float(w.getframerate())
        except Exception:
            return 0.0


