"""
widgets.py

contains widget creation and management functions for the interface

(from Aerowave Orb Creator)
"""

from .common import *

# ======================================================================================
#  Aero glass drawing helpers (drop-down + pop-ups)
# ======================================================================================
def glass_panel(base, box, radius, st, shadow=True, ss=3):
    """Composite a frosted Aero-glass panel (shadow, blur-behind, tint, sheen, bevel) onto an RGB image."""
    W, H = base.size
    x0, y0, x1, y1 = [int(v) for v in box]
    w, h = x1 - x0, y1 - y0
    out = base.copy()

    if shadow:
        m = 16
        sx0, sy0, sx1, sy1 = max(0, x0 - m), max(0, y0 - m), min(W, x1 + m), min(H, y1 + m)
        reg = out.crop((sx0, sy0, sx1, sy1))
        sm = Image.new("L", reg.size, 0)
        ImageDraw.Draw(sm).rounded_rectangle([x0 - sx0, y0 - sy0 + 9, x1 - sx0, y1 - sy0 + 9], radius=radius, fill=st["shadow"])
        sm = sm.filter(ImageFilter.GaussianBlur(16))
        out.paste(Image.composite(Image.new("RGB", reg.size, (0, 0, 0)), reg, sm), (sx0, sy0))

    # blur-behind
    pad = 24
    bx0, by0, bx1, by1 = max(0, x0 - pad), max(0, y0 - pad), min(W, x1 + pad), min(H, y1 + pad)
    frost = base.crop((bx0, by0, bx1, by1)).filter(ImageFilter.GaussianBlur(st["blur"]))
    frost = frost.crop((x0 - bx0, y0 - by0, x0 - bx0 + w, y0 - by0 + h))

    # tint (a touch stronger toward the bottom)
    ta = Image.linear_gradient("L").resize((w, h))
    ta = ta.point(lambda p: int(255 * max(0.0, min(1.0, st["tint_a"] + (p / 255.0 - 0.5) * st["tint_grad"]))))
    glass = Image.composite(Image.new("RGB", (w, h), st["tint"]), frost, ta)

    # diagonal sheen + soft top light, drawn supersampled
    S = ss
    sheen = Image.new("L", (w * S, h * S), 0)
    sd = ImageDraw.Draw(sheen)
    sd.polygon([(0, 0), (int(w * S * 0.66), 0), (int(w * S * 0.22), h * S), (0, h * S)], fill=255)
    sheen = sheen.resize((w, h), Image.LANCZOS)
    fade = Image.linear_gradient("L").resize((w, h)).point(lambda p: int(255 - p * 0.80))
    sheen = ImageChops.multiply(sheen, fade).point(lambda p: int(p * st["gloss"]))
    glass = Image.composite(Image.new("RGB", (w, h), (255, 255, 255)), glass, sheen)
    top = Image.linear_gradient("L").resize((w, h)).point(lambda p: int(max(0, 255 - p * 2.4) * st["gloss"] * 0.55))
    glass = Image.composite(Image.new("RGB", (w, h), (255, 255, 255)), glass, top)

    # double bevel border
    decor = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
    dd = ImageDraw.Draw(decor)
    dd.rounded_rectangle([0, 0, w * S - 1, h * S - 1], radius=radius * S, outline=(0, 0, 0, st["border_dark"]), width=S)
    dd.rounded_rectangle([S, S, w * S - 1 - S, h * S - 1 - S], radius=max(1, radius - 1) * S,
                         outline=(255, 255, 255, st["border_light"]), width=S)
    decor = decor.resize((w, h), Image.LANCZOS)
    panel = glass.convert("RGBA")
    panel.alpha_composite(decor)

    mk = Image.new("L", (w * S, h * S), 0)
    ImageDraw.Draw(mk).rounded_rectangle([0, 0, w * S - 1, h * S - 1], radius=radius * S, fill=255)
    mk = mk.resize((w, h), Image.LANCZOS)
    out.paste(panel.convert("RGB"), (x0, y0), mk)
    return out


def make_dim(snapshot, st):
    """Blurred, darkened copy of a screenshot (backdrop behind modal pop-ups)."""
    small = snapshot.resize((max(1, snapshot.width // 3), max(1, snapshot.height // 3)), Image.BILINEAR)
    small = small.filter(ImageFilter.GaussianBlur(2))
    blurred = small.resize(snapshot.size, Image.BILINEAR)
    return ImageEnhance.Brightness(blurred).enhance(st["dim"])


def badge_orb(size, color, glyph):
    """Small glossy status orb with a check mark ('ok') or exclamation mark ('err')."""
    S = 4
    N = size * S
    base = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    mask = Image.new("L", (N, N), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, N - 1, N - 1], fill=255)
    grad = Image.radial_gradient("L").resize((N, N), Image.BILINEAR)         # 0 centre -> 255 edge
    dark = tuple(int(c * 0.62) for c in color)
    light = tuple(min(255, int(c + (255 - c) * 0.35)) for c in color)
    orb = Image.composite(Image.new("RGB", (N, N), dark), Image.new("RGB", (N, N), light), grad.point(lambda p: min(255, int(p * 1.15))))
    base.paste(orb, (0, 0), mask)
    hl = Image.new("L", (N, N), 0)
    ImageDraw.Draw(hl).ellipse([N * 0.14, N * 0.05, N * 0.86, N * 0.52], fill=255)
    hl = ImageChops.multiply(hl, Image.linear_gradient("L").resize((N, N)).point(lambda p: 255 - p)).point(lambda p: int(p * 0.62))
    hl = ImageChops.multiply(hl, mask)
    base = Image.composite(Image.new("RGBA", (N, N), (255, 255, 255, 255)), base, hl)
    d = ImageDraw.Draw(base)
    lw = max(2, int(N * 0.115))
    if glyph == "ok":
        pts = [(N * 0.27, N * 0.52), (N * 0.43, N * 0.68), (N * 0.74, N * 0.33)]
        d.line(pts, fill=(255, 255, 255, 255), width=lw, joint="curve")
        for p in (pts[0], pts[-1]):
            d.ellipse([p[0] - lw / 2, p[1] - lw / 2, p[0] + lw / 2, p[1] + lw / 2], fill=(255, 255, 255, 255))
    else:
        d.line([(N * 0.5, N * 0.24), (N * 0.5, N * 0.60)], fill=(255, 255, 255, 255), width=lw)
        r = lw * 0.62
        d.ellipse([N * 0.5 - r, N * 0.76 - r, N * 0.5 + r, N * 0.76 + r], fill=(255, 255, 255, 255))
    ring = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    ImageDraw.Draw(ring).ellipse([0, 0, N - 1, N - 1], outline=(255, 255, 255, 190), width=max(2, S))
    base.alpha_composite(ring)
    return base.resize((size, size), Image.LANCZOS)


def wrap_text(draw, text, font, max_w):
    words, lines, cur = text.split(), [], ""
    for wd in words:
        trial = (cur + " " + wd).strip()
        if draw.textlength(trial, font=font) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    return lines


def ellipsize(draw, text, font, max_w):
    if draw.textlength(text, font=font) <= max_w:
        return text
    stem, ext = os.path.splitext(text)
    while stem and draw.textlength(stem + "…" + ext, font=font) > max_w:
        stem = stem[:-1]
    return stem + "…" + ext


def make_icon(kind, size=18):
    """Tiny file-browser icons drawn with PIL: 'folder', 'drive' or 'png'."""
    S = 4
    N = size * S
    im = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    lw = max(1, S // 2)
    if kind == "folder":
        d.rounded_rectangle([N * .06, N * .20, N * .44, N * .44], radius=N * .06, fill=(226, 160, 38, 255))
        d.rounded_rectangle([N * .06, N * .30, N * .94, N * .84], radius=N * .08, fill=(255, 200, 72, 255), outline=(196, 132, 20, 255), width=lw)
        d.rounded_rectangle([N * .10, N * .34, N * .90, N * .50], radius=N * .06, fill=(255, 226, 134, 255))
    elif kind == "drive":
        d.rounded_rectangle([N * .06, N * .30, N * .94, N * .74], radius=N * .10, fill=(176, 182, 194, 255), outline=(110, 116, 128, 255), width=lw)
        d.rectangle([N * .14, N * .52, N * .58, N * .60], fill=(120, 126, 138, 255))
        d.ellipse([N * .74, N * .46, N * .84, N * .58], fill=(70, 200, 90, 255))
    else:
        d.rounded_rectangle([N * .18, N * .06, N * .82, N * .94], radius=N * .08, fill=(255, 255, 255, 255), outline=(150, 156, 168, 255), width=lw)
        d.ellipse([N * .30, N * .28, N * .70, N * .68], fill=(255, 110, 20, 255))
        d.ellipse([N * .38, N * .34, N * .56, N * .46], fill=(255, 224, 196, 255))
    return im.resize((size, size), Image.LANCZOS)


def human_size(n):
    n = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return ("%d %s" % (n, unit)) if unit == "B" else ("%.1f %s" % (n, unit))
        n /= 1024.0
    return "%.1f TB" % n


def hsv_wheel(D, v):
    """RGBA colour wheel: hue = angle, saturation = radius (white centre), brightness = v. Anti-aliased edge."""
    R = D / 2.0
    if HAVE_NUMPY:
        ys, xs = np.mgrid[0:D, 0:D].astype(np.float32)
        dx, dy = xs + 0.5 - R, ys + 0.5 - R
        r = np.sqrt(dx * dx + dy * dy)
        sat = np.clip(r / R, 0.0, 1.0)
        hue = (np.arctan2(-dy, dx) / (2 * np.pi)) % 1.0
        h6 = hue * 6.0
        i = np.floor(h6).astype(np.int32) % 6
        f = h6 - np.floor(h6)
        V = np.full_like(sat, v)
        p, q, t = v * (1 - sat), v * (1 - f * sat), v * (1 - (1 - f) * sat)
        rr = np.choose(i, [V, q, p, p, t, V])
        gg = np.choose(i, [t, V, V, q, p, p])
        bb = np.choose(i, [p, p, t, V, V, q])
        a = np.clip(R - r + 0.5, 0.0, 1.0)
        return Image.fromarray((np.stack([rr, gg, bb, a], -1) * 255.0 + 0.5).astype(np.uint8), "RGBA")
    n = 100                                                       # no numpy: coarse grid + smooth resize
    small = Image.new("RGB", (n, n))
    px = small.load()
    for y in range(n):
        for x in range(n):
            dx, dy = x + 0.5 - n / 2.0, y + 0.5 - n / 2.0
            r = min(1.0, math.hypot(dx, dy) / (n / 2.0))
            h = (math.atan2(-dy, dx) / (2 * math.pi)) % 1.0
            px[x, y] = tuple(int(c * 255) for c in colorsys.hsv_to_rgb(h, r, v))
    img = small.resize((D, D), Image.BICUBIC).convert("RGBA")
    mask = Image.new("L", (D * 3, D * 3), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, D * 3 - 1, D * 3 - 1], fill=255)
    img.putalpha(mask.resize((D, D), Image.LANCZOS))
    return img


def wheel_ring(D, pad):
    """Bevelled rim drawn around the colour wheel (RGBA, size D + 2*pad)."""
    S = 3
    N = (D + 2 * pad) * S
    im = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c, R = N / 2.0, D / 2.0 * S
    d.ellipse([c - R - S * 2, c - R - S * 2, c + R + S * 2, c + R + S * 2], outline=(0, 0, 0, 150), width=S * 2)
    d.ellipse([c - R + S, c - R + S, c + R - S, c + R - S], outline=(255, 255, 255, 190), width=S)
    return im.resize((D + 2 * pad, D + 2 * pad), Image.LANCZOS)


def swatch_image(rgb, w, h, radius):
    """Glossy rounded colour swatch (RGBA)."""
    S = 3
    base = Image.new("RGBA", (w, h), tuple(rgb) + (255,))
    gl = Image.linear_gradient("L").resize((w, h)).point(lambda p: int(max(0, 255 - p * 2.0) * 0.34))
    white = Image.new("RGBA", (w, h), (255, 255, 255, 0))
    white.putalpha(gl)
    base = Image.alpha_composite(base, white)
    border = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
    bd = ImageDraw.Draw(border)
    bd.rounded_rectangle([0, 0, w * S - 1, h * S - 1], radius=radius * S, outline=(0, 0, 0, 150), width=S)
    bd.rounded_rectangle([S, S, w * S - 1 - S, h * S - 1 - S], radius=max(1, radius - 1) * S, outline=(255, 255, 255, 120), width=S)
    base.alpha_composite(border.resize((w, h), Image.LANCZOS))
    mask = Image.new("L", (w * S, h * S), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w * S - 1, h * S - 1], radius=radius * S, fill=255)
    base.putalpha(mask.resize((w, h), Image.LANCZOS))
    return base


def empty_slot_image(w, h, radius, col):
    S = 3
    im = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle([0, 0, w * S - 1, h * S - 1], radius=radius * S, fill=tuple(col) + (26,), outline=tuple(col) + (90,), width=S)
    return im.resize((w, h), Image.LANCZOS)


def brightness_bar(w, h, rgb):
    """Rounded black -> colour gradient bar (RGBA) for the brightness slider."""
    S = 3
    mask = Image.new("L", (w, h), 0)
    grad = Image.linear_gradient("L").rotate(90).resize((w, h))                   # 0 on the left -> 255 on the right
    bar = Image.composite(Image.new("RGB", (w, h), tuple(rgb)), Image.new("RGB", (w, h), (0, 0, 0)), grad).convert("RGBA")
    big = Image.new("L", (w * S, h * S), 0)
    ImageDraw.Draw(big).rounded_rectangle([0, 0, w * S - 1, h * S - 1], radius=(h // 2) * S, fill=255)
    bar.putalpha(big.resize((w, h), Image.LANCZOS))
    rim = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
    rd = ImageDraw.Draw(rim)
    rd.rounded_rectangle([0, 0, w * S - 1, h * S - 1], radius=(h // 2) * S, outline=(0, 0, 0, 150), width=S)
    rd.rounded_rectangle([S, S, w * S - 1 - S, h * S - 1 - S], radius=max(1, h // 2 - 1) * S, outline=(255, 255, 255, 110), width=S)
    bar.alpha_composite(rim.resize((w, h), Image.LANCZOS))
    return bar


def create_gradient_rect(width, height, color_top, color_bottom, radius, outline_color=None, mid_color=None, flipped=False):
    if flipped:
        color_top, color_bottom = color_bottom, color_top

    base = Image.new('RGBA', (width, height), (0,0,0,0))
    if width <= 0 or height <= 0: return base
    grad = Image.new('RGBA', (1, height))
    
    for y in range(height):
        if mid_color:
            if y < height / 2:
                prog = y / (height / 2)
                c1, c2 = color_top, mid_color
            else:
                prog = (y - height / 2) / (height / 2)
                c1, c2 = mid_color, color_bottom
        else:
            prog = y / height
            c1, c2 = color_top, color_bottom
            
        r = int(c1[0] + (c2[0] - c1[0]) * prog)
        g = int(c1[1] + (c2[1] - c1[1]) * prog)
        b = int(c1[2] + (c2[2] - c1[2]) * prog)
        grad.putpixel((0, y), (r, g, b, 255))
        
    grad = grad.resize((width, height))
    
    mask = Image.new('L', (width, height), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle([0, 0, width-1, height-1], radius=radius, fill=255)
    
    grad.putalpha(mask)
    
    if outline_color:
        out_img = Image.new('RGBA', (width, height), (0,0,0,0))
        out_draw = ImageDraw.Draw(out_img)
        out_draw.rounded_rectangle([0, 0, width-1, height-1], radius=radius, outline=outline_color, width=1)
        grad = Image.alpha_composite(grad, out_img)
        
    return grad

def dorfic_swoosh(w, hr, ss=2):
    """DORFic-kit style bundle of fine orange/amber strands sweeping up from the lower left (RGBA)."""
    W, H = w * ss, hr * ss
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    xs = list(range(0, W + 1, 4))

    def curve(sv):
        pts = []
        for x in xs:
            u = x / float(W)
            a0 = 0.68 - 0.50 * ((lambda a: a * a * (3 - 2 * a))(min(1.0, u * 1.05))) ** 1.15 + 0.04 * math.sin(u * 7.5 + 0.6)
            wd = 0.40 * (1.0 - u) ** 1.3 + 0.035
            pts.append((x, (a0 + sv * wd) * H))
        return pts

    top, bot = curve(0.0), curve(1.0)
    d.polygon(top + bot[::-1], fill=(255, 130, 30, 30))         # faint glossy body between the outer strands
    N = 34
    for k in range(N):
        sv = k / float(N - 1)
        if k % 7 == 3:
            col = (176, 182, 192)                                 # cool grey "infrastructure" strand (at this point I'm just showin' off lol)
        elif sv < 0.5:
            f = sv / 0.5
            col = (255, int(102 + (160 - 102) * f), int(0 + 40 * f))
        else:
            f = (sv - 0.5) / 0.5
            col = (255, int(160 + (212 - 160) * f), int(40 + 60 * f))
        d.line(curve(sv), fill=col + (205 if k % 7 != 3 else 150,), width=ss)
    d.line(top, fill=(255, 102, 0, 245), width=ss * 3)           # bold signature orange edge
    d.line(bot, fill=(255, 176, 60, 220), width=ss * 2)
    img = img.resize((w, hr), Image.LANCZOS)
    fade = Image.linear_gradient("L").rotate(90).resize((w, hr))   # fade out toward the right edge
    ramp = fade.point(lambda p: 255 if p < 190 else max(0, 255 - (p - 190) * 4))
    img.putalpha(ImageChops.multiply(img.getchannel("A"), ramp))
    return img


class GradientPanel(tk.Canvas):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, highlightthickness=0, bd=0, **kwargs)
        self.color_top = "#000000"
        self.color_bot = "#000000"
        self.decor = None
        self.decor_top = 0
        self._decor_cache = {}
        self.bind("<Configure>", self._on_resize)
        self.grad_img = None
        
    def set_colors(self, top, bot, decor=None):
        self.color_top = top
        self.color_bot = bot
        self.decor = decor
        self._draw_gradient()

    def set_decor_top(self, y):
        """Top of the empty area under the widgets (decorations are drawn only there)."""
        y = int(y)
        if abs(y - self.decor_top) >= 6:
            self.decor_top = y
            if self.decor:
                self._draw_gradient()
        
    def _on_resize(self, event):
        self._draw_gradient()

    def _with_decor(self, img, w, h):
        try:
            top = self.decor_top + 16
            hr = h - top - 8
            if self.decor != "dorfic" or self.decor_top <= 0 or hr < 110:
                return img
            key = (w, hr)
            if key not in self._decor_cache:
                self._decor_cache.clear()
                self._decor_cache[key] = dorfic_swoosh(w, hr)
            out = img.convert("RGBA")
            out.alpha_composite(self._decor_cache[key], (0, top))
            return out.convert("RGB")
        except Exception:
            return img
        
    def _draw_gradient(self):
        w, h = self.winfo_width(), self.winfo_height()
        if w < 2 or h < 2: return
        
        img = Image.new('RGB', (1, h))
        r1, g1, b1 = int(self.color_top[1:3], 16), int(self.color_top[3:5], 16), int(self.color_top[5:7], 16)
        r2, g2, b2 = int(self.color_bot[1:3], 16), int(self.color_bot[3:5], 16), int(self.color_bot[5:7], 16)
        
        for y in range(h):
            prog = y / h
            img.putpixel((0, y), (int(r1 + (r2 - r1) * prog), int(g1 + (g2 - g1) * prog), int(b1 + (b2 - b1) * prog)))
            
        img = img.resize((w, h))
        if self.decor:
            img = self._with_decor(img, w, h)
        self.grad_img = ImageTk.PhotoImage(img)
        self.delete("grad")
        self.create_image(0, 0, anchor=tk.NW, image=self.grad_img, tags="grad")
        self.tag_lower("grad")

class GlassCard(tk.Canvas):
    # persistent frosted glass region: composites glass_panel over a copy of the
    # window gradient at this card's position, regular widgets pack on top
    def __init__(self, parent, radius=18, **kwargs):
        super().__init__(parent, highlightthickness=0, bd=0, **kwargs)
        self.radius = radius
        self.ui_top = "#2b2b2b"
        self.ui_bot = "#2b2b2b"
        self.glass = None
        self.flat_bg = "#2b2b2b"
        self.row_colors = []                        # vertical colour profile of the drawn glass
        self.photo = None
        self._job = None
        self._last = None                         # geometry + theme key of the last drawn frame
        self.on_flat_bg = None                     # callback(flat_bg) fired after every redraw
        self.bind("<Configure>", self._on_configure)

    def set_theme(self, t, st):
        # t: THEMES entry carrying the window gradient, st: GLASS entry for the frost
        self.ui_top = t["ui_top"]
        self.ui_bot = t["ui_bot"]
        self.glass = st
        self._redraw()

    def refresh(self):
        self._redraw()

    def color_at(self, frac):
        # glass colour at a vertical position of this card (0 top, 1 bottom)
        if not self.row_colors:
            return self.flat_bg
        i = int(min(0.999, max(0.0, frac)) * len(self.row_colors))
        return "#%02x%02x%02x" % self.row_colors[i]

    def _on_configure(self, e):
        if self._job is not None:
            try:
                self.after_cancel(self._job)
            except Exception:
                pass
        self._job = self.after(30, self._redraw)   # debounce resize bursts to a single redraw

    def _window_row(self):
        # this card's top row inside the toplevel window plus the window height
        try:
            root = self.winfo_toplevel()
            return max(0, self.winfo_rooty() - root.winfo_rooty()), max(1, root.winfo_height())
        except tk.TclError:
            return 0, max(1, self.winfo_height())

    def _redraw(self):
        self._job = None
        w, h = self.winfo_width(), self.winfo_height()
        m = 14                                     # margin around the glass that carries the drop shadow
        if self.glass is None or w < 2 * m + 4 or h < 2 * m + 4:
            return
        ry, rh = self._window_row()
        key = (w, h, ry, rh, self.ui_top, self.ui_bot, id(self.glass))
        if key == self._last:
            return                                 # same size, position and theme: keep the last frame
        self._last = key
        c1 = [int(self.ui_top[i:i + 2], 16) for i in (1, 3, 5)]
        c2 = [int(self.ui_bot[i:i + 2], 16) for i in (1, 3, 5)]
        col = Image.new("RGB", (1, h))
        for y in range(h):                         # window gradient rows covered by this card
            k = min(1.0, max(0.0, (ry + y) / float(rh))) if rh > 0 else 0.0
            col.putpixel((0, y), tuple(int(c1[i] + (c2[i] - c1[i]) * k) for i in range(3)))
        backdrop = col.resize((w, h))
        panel = glass_panel(backdrop, (m, m, w - m, h - m), self.radius, self.glass)
        self.photo = ImageTk.PhotoImage(panel)
        self.delete("glass")
        self.create_image(0, 0, anchor=tk.NW, image=self.photo, tags="glass")
        self.tag_lower("glass")

        # vertical colour profile of the composited glass, hosted widgets pick their row
        nb = 16
        self.row_colors = []
        ix0, ix1 = m + 8, w - m - 8
        band = (h - 2 * m) / float(nb)
        for i in range(nb):
            y0 = int(m + i * band)
            y1 = max(y0 + 1, int(m + (i + 1) * band))
            if ix1 <= ix0 or y1 > panel.height:
                break
            self.row_colors.append(panel.crop((ix0, y0, ix1, y1)).resize((1, 1)).getpixel((0, 0)))
        if self.row_colors:
            self.flat_bg = "#%02x%02x%02x" % self.row_colors[len(self.row_colors) // 2]
        if self.on_flat_bg:
            try:
                self.on_flat_bg(self.flat_bg)
            except Exception:
                pass

class OrbLayer:
    def __init__(self, name, layer_type, visible=True):
        self.name = name
        self.type = layer_type
        self.visible = visible
        self.x = 250
        self.y = 250
        self.scale = 1.0
        self.scale_x = 1.0  
        self.scale_y = 1.0  
        self.color = (33, 150, 243)
        self.custom_grad_color = None
        self.glow_opacity = 220
        self.grad_y_scale = 1.0
        self.grad_y_offset = 0
        
