"""
intro.py

contains the AeroIntro class for handling the introduction sequence
AND the AeroOutro class for handling the outro

(from Aerowave Orb Creator)
"""

from .common import *
from .helpers import *
from .aurora import *

# ======================================================================================
#  Intro: aurora fades in -> logo glides in with the jingle -> dissolves into the editor
# ======================================================================================
class AeroIntro:
    BG_FADE = 1.5          # seconds for the aurora to fade in from black
    LOGO_START = 1.0       # logo + jingle begin here
    SLIDE_DUR = 2.3        # seconds each logo piece takes to glide into place
    STAGGER = 0.16         # delay between orb -> "Aerowave" -> "Orb Creator"
    FADE_OUT = 1.0         # dissolve into the editor
    AURORA_FPS = 24        # aurora update rate (logo motion updates every tick)
    SLIDE_FRAC = 0.036     # slide distance as a fraction of screen width aka just a smidge
    WIDTHS = (512, 416, 320)   # internal width of the SOFT aurora layer, best first (detail is always native resolution)
    RENDER_BUDGET_MS = 30.0         # whole-aurora budget per frame

    # Reference layout of the full logo on a 1920x1080 canvas (measured from Aerowave_Orb_Creator.png)
    REF_W, REF_H = 1920, 1080
    ORB_SIZE, ORB_POS = 931, (47, 56)
    AEROWAVE_POS = (522, 523)
    ORBCREATOR_POS = (584, 681)

    def __init__(self, root):
        self.root = root
        self.sw, self.sh = root.winfo_screenwidth(), root.winfo_screenheight()
        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.geometry(f"{self.sw}x{self.sh}+0+0")
        self.win.configure(bg="black")
        try:
            self.win.attributes("-topmost", True)
        except tk.TclError:
            pass
        self.canvas = tk.Canvas(self.win, width=self.sw, height=self.sh, bg="black", highlightthickness=0, bd=0)
        self.canvas.pack()
        self.win.update()
        try:
            self.win.lift()
            self.win.focus_force()
        except tk.TclError:
            pass
        self.running = False
        self.on_done = None
        self._bg = None
        self._bg_t = 0.0
        self._prepare()

    # -------------------------------------------------------------------------
    def _make_aurora(self, quality):
        w = self.WIDTHS[quality]
        if HAVE_NUMPY:
            return AuroraHD(self.sw, self.sh, w)
        return StaticBackdrop(w, max(8, int(round(w * self.sh / self.sw))))

    def _load_layer(self, filename, pos, size=None, crop_to_alpha=False):
        path = asset_path(filename)
        if not path:
            return None
        s = min(self.sw / self.REF_W, self.sh / self.REF_H)
        ox = (self.sw - self.REF_W * s) / 2.0
        oy = (self.sh - self.REF_H * s) / 2.0
        img = Image.open(path).convert("RGBA")
        if size is not None:                              # orb: scale the whole 1080px square, then trim
            target = max(1, int(round(size * s)))
            img = img.resize((target, target), Image.LANCZOS)
            x, y = pos[0] * s + ox, pos[1] * s + oy
        else:
            if abs(s - 1.0) > 1e-6:
                img = img.resize((max(1, int(round(img.width * s))), max(1, int(round(img.height * s)))), Image.LANCZOS)
            x, y = pos[0] * s + ox, pos[1] * s + oy
        x, y = int(round(x)), int(round(y))
        if crop_to_alpha:
            bb = img.getchannel("A").point(lambda p: 255 if p > 0 else 0).getbbox()
            if bb:
                img = img.crop(bb)
                x, y = x + bb[0], y + bb[1]
        pad = 2                                           # transparent margin so sub-pixel shifts never clip
        padded = Image.new("RGBA", (img.width + pad * 2, img.height + pad * 2), (0, 0, 0, 0))
        padded.paste(img, (pad, pad))
        return padded.convert("RGBa"), x - pad, y - pad

    def _calibrate(self):
        """Pick the sharpest aurora size this PC can compute within the frame budget (done during the black screen)."""
        if not HAVE_NUMPY:
            return 0
        for q in range(len(self.WIDTHS)):
            a = self._make_aurora(q)
            a.render(0.5)
            t0 = time.perf_counter()
            for k in range(3):
                a.render(1.0 + k * 0.1)
            ms = (time.perf_counter() - t0) * 1000.0 / 3.0
            if ms <= self.RENDER_BUDGET_MS or q == len(self.WIDTHS) - 1:
                return q
        return len(self.WIDTHS) - 1

    def _prepare(self):
        self.quality = self._calibrate()
        self.aurora = self._make_aurora(self.quality)
        self.slide_px = max(8, int(self.sw * self.SLIDE_FRAC))
        self.layers = []
        specs = [
            ("image/orangeorb.png", self.ORB_POS, self.ORB_SIZE, True, -1, 0.0),
            ("image/aerowave.png", self.AEROWAVE_POS, None, False, +1, self.STAGGER),
            ("image/orbcreator.png", self.ORBCREATOR_POS, None, False, +1, self.STAGGER * 2),
        ]
        for fn, pos, size, crop, direction, delay in specs:       # draw order: orb behind, text in front
            res = self._load_layer(fn, pos, size, crop)
            if res:
                img, x, y = res
                self.layers.append(dict(img=img, x=x, y=y, dir=direction, delay=delay))
        self.jingle = asset_path("sfx/orbcreatorjingle.wav")
        dur = Sound.duration(self.jingle) if self.jingle else 0.0
        logo_done = self.LOGO_START + self.STAGGER * 2 + self.SLIDE_DUR
        audio_end = self.LOGO_START + dur
        self.t_fade0 = max(logo_done, audio_end) + 0.12
        self.photo = ImageTk.PhotoImage(Image.new("RGB", (self.sw, self.sh), (0, 0, 0)))
        self.canvas.create_image(0, 0, anchor="nw", image=self.photo)

    # -------------------------------------------------------------------------
    def start(self, on_done=None):
        self.on_done = on_done
        self.running = True
        self.sound_started = False
        self.ema = None
        self.last_q_change = 0.0
        self.t0 = time.perf_counter()
        self._tick()

    def _compose(self, t):
        # The aurora drifts slowly, so it only needs ~24 updates/s; the logo glide still updates every tick.
        if self._bg is None or (t - self._bg_t) >= 1.0 / self.AURORA_FPS:
            gain = smooth(t / self.BG_FADE)
            r0 = time.perf_counter()
            low = self.aurora.render(t, gain)
            self.render_ms = (time.perf_counter() - r0) * 1000.0
            self._bg = low if low.size == (self.sw, self.sh) else low.resize((self.sw, self.sh), Image.BICUBIC)
            self._bg_t = t
        frame = self._bg.copy()
        for L in self.layers:
            p = (t - self.LOGO_START - L["delay"]) / self.SLIDE_DUR
            if p <= 0.0:
                continue
            p = clamp01(p)
            slide = (1.0 - ease_out_quart(p)) * self.slide_px * L["dir"]
            opacity = smooth(p / 0.55)
            px = L["x"] + slide
            ix = math.floor(px)
            fx = px - ix
            im = L["img"]
            if fx > 0.004:                                  # sub-pixel glide (premultiplied, so no halos)
                im = im.transform(im.size, Image.AFFINE, (1, 0, -fx, 0, 1, 0), Image.BILINEAR)
            im = im.convert("RGBA")
            if opacity < 0.999:
                im.putalpha(im.getchannel("A").point(lambda v, o=opacity: int(v * o + 0.5)))
            frame.paste(im, (ix, L["y"]), im)
        return frame

    def _tick(self):
        if not self.running:
            return
        started = time.perf_counter()
        t = started - self.t0
        if not self.sound_started and t >= self.LOGO_START:
            self.sound_started = True
            Sound.play(self.jingle)
        try:
            self.photo.paste(self._compose(t))
        except Exception:
            pass

        if t >= self.t_fade0:
            k = clamp01((t - self.t_fade0) / self.FADE_OUT)
            try:
                self.win.attributes("-alpha", max(0.0, 1.0 - smooth(k)))
            except tk.TclError:
                k = 1.0                                      # no window alpha on this platform: just cut
            if k >= 1.0:
                self._finish()
                return

        ft = getattr(self, "render_ms", 0.0)                  # judge only the aurora math (not the screen paste)
        self.ema = ft if self.ema is None else self.ema * 0.9 + ft * 0.1
        if HAVE_NUMPY and self.ema > self.RENDER_BUDGET_MS * 1.8 and self.quality < len(self.WIDTHS) - 1 and (t - self.last_q_change) > 1.0:
            self.quality += 1
            self.last_q_change = t
            self.aurora = self._make_aurora(self.quality)
            self._bg = None
            self.ema = None
        delay = max(1, int(16 - (time.perf_counter() - started) * 1000))
        self.root.after(delay, self._tick)

    def _finish(self):
        self.running = False
        try:
            self.win.destroy()
        except tk.TclError:
            pass
        if self.on_done:
            self.on_done()


class AeroOutro:
    """Exit animation: dissolves over the editor into the blue streak background with "See you later!",
    plays exitjingle.wav, then fades to black and quits."""
    FADE_IN = 1.0          # dissolve from the editor into the outro
    SOUND_AT = 0.15        # jingle starts as the dissolve begins
    HOLD_PAD = 0.20        # pause after the jingle finishes
    FADE_BLACK = 1.3       # fade to black
    AURORA_FPS = 24
    SOFT_WIDTH = 416
    TEXT_FRAC = 0.42       # text width as a fraction of the screen width

    def __init__(self, root, on_done):
        self.root, self.on_done = root, on_done
        self.sw, self.sh = root.winfo_screenwidth(), root.winfo_screenheight()
        self.win = tk.Toplevel(root)
        self.win.withdraw()
        self.win.overrideredirect(True)
        self.win.geometry(f"{self.sw}x{self.sh}+0+0")
        self.win.configure(bg="black")
        self.has_alpha = True
        try:
            self.win.attributes("-alpha", 0.0)
            self.win.attributes("-topmost", True)
        except tk.TclError:
            self.has_alpha = False
        self.canvas = tk.Canvas(self.win, width=self.sw, height=self.sh, bg="black", highlightthickness=0, bd=0)
        self.canvas.pack()
        if HAVE_NUMPY:
            self.bg = BlueHD(self.sw, self.sh, self.SOFT_WIDTH)
        else:
            self.bg = StaticBackdrop(self.SOFT_WIDTH, max(8, int(round(self.SOFT_WIDTH * self.sh / self.sw))),
                                     colors=((78, 104, 222), (24, 100, 224), (3, 16, 108), (8, 44, 168)))
        self._prepare_text()
        self.jingle = asset_path("sfx/exitjingle.wav")
        dur = Sound.duration(self.jingle) if self.jingle else 0.0
        self.t_black0 = max(self.SOUND_AT + dur + self.HOLD_PAD, self.FADE_IN + 0.3)
        self.photo = ImageTk.PhotoImage(Image.new("RGB", (self.sw, self.sh), (0, 0, 0)))
        self.canvas.create_image(0, 0, anchor="nw", image=self.photo)
        self._bg_frame, self._bg_t, self._bg_gain = None, 0.0, -1.0
        self.sound_started = False
        self.running = False
        self.photo.paste(self._compose(0.0))              # first frame is ready before the window becomes visible
        self.win.deiconify()
        self.win.update()
        try:
            self.win.lift()
            self.win.focus_force()
        except tk.TclError:
            pass

    def _prepare_text(self):
        self.text_layer, self.text_pos = None, (0, 0)
        p = asset_path("image/exittext.png")
        if not p:
            return
        try:
            src = Image.open(p).convert("RGBA")
            alpha = src.getchannel("A")
            tw = max(8, int(self.sw * self.TEXT_FRAC))
            th = max(2, int(round(src.height * tw / src.width)))
            alpha = alpha.resize((tw, th), Image.LANCZOS)
            pad = int(tw * 0.06)
            canvas_a = Image.new("L", (tw + pad * 2, th + pad * 2), 0)
            canvas_a.paste(alpha, (pad, pad))
            white = Image.new("RGBA", canvas_a.size, (255, 255, 255, 0))
            white.putalpha(canvas_a)                                              # same lettering, recoloured white
            glow = Image.new("RGBA", canvas_a.size, (120, 200, 255, 0))
            glow.putalpha(canvas_a.filter(ImageFilter.GaussianBlur(max(3, tw * 0.012))).point(lambda v: min(255, int(v * 1.6))))
            self.text_layer = Image.alpha_composite(glow, white)
            self.text_pos = ((self.sw - self.text_layer.width) // 2, int(self.sh * 0.5 - self.text_layer.height / 2))
        except Exception:
            self.text_layer = None

    def _black_gain(self, t):
        return 1.0 if t <= self.t_black0 else 1.0 - smooth((t - self.t_black0) / self.FADE_BLACK)

    def _compose(self, t):
        g = self._black_gain(t)
        if self._bg_frame is None or (t - self._bg_t) >= 1.0 / self.AURORA_FPS or abs(g - self._bg_gain) > 0.02:
            low = self.bg.render(t, g)
            self._bg_frame = low if low.size == (self.sw, self.sh) else low.resize((self.sw, self.sh), Image.BICUBIC)
            self._bg_t, self._bg_gain = t, g
        frame = self._bg_frame.copy()
        if self.text_layer is not None:
            lay = self.text_layer
            if g < 0.999:
                lay = lay.copy()
                lay.putalpha(lay.getchannel("A").point(lambda v, k=g: int(v * k + 0.5)))
            frame.paste(lay, self.text_pos, lay)
        return frame

    def start(self):
        self.running = True
        self.t0 = time.perf_counter()
        self._tick()

    def _tick(self):
        if not self.running:
            return
        started = time.perf_counter()
        t = started - self.t0
        if not self.sound_started and t >= self.SOUND_AT:
            self.sound_started = True
            Sound.play(self.jingle)
        try:
            self.photo.paste(self._compose(t))
        except Exception:
            pass
        if self.has_alpha and t <= self.FADE_IN + 0.1:
            try:
                self.win.attributes("-alpha", smooth(t / self.FADE_IN))
            except tk.TclError:
                self.has_alpha = False
        if t >= self.t_black0 + self.FADE_BLACK + 0.1:
            self.running = False
            self.on_done()
            return
        self.root.after(max(1, int(16 - (time.perf_counter() - started) * 1000)), self._tick)


