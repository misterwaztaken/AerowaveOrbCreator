"""
aurora.py
 


(from Aerowave Orb Creator)
"""

from .common import *

# ======================================================================================
#  Live aurora background (all math: ribbons, shafts, caustics, flare, bubbles, i farted)
# ======================================================================================
def _sstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def left_geometry(u, t):
    """Top edge and width of the left sweeping green/yellow sheet (u = 0..1 across the screen)."""
    wob = 0.012 * np.sin(5.0 * u + 0.7 * t) + 0.007 * np.sin(11.0 * u - 1.1 * t + 1.3)
    top = 0.30 + 0.56 * np.clip(u / 0.64, 0, 1) ** 1.75 + wob * (1 - u)
    width = 0.06 + 0.50 * (1.0 - np.clip(u / 0.80, 0, 1)) ** 1.4
    return top, width


def right_geometry(v, t):
    """Edge position and width of the thin blue/cyan ribbon on the right (v = 0..1 down the screen)."""
    wob2 = 0.010 * np.sin(4.0 * v - 0.8 * t) + 0.006 * np.sin(9.0 * v + 0.9 * t)
    gx = 1.04 - 0.30 * np.clip(v / 0.98, 0, 1) ** 1.9 + wob2
    wr = 0.020 + 0.075 * _sstep(0.1, 0.95, v)
    return gx, wr


class Aurora:
    """SOFT layer of the aurora (water gradient, light shafts, caustics, glows, bloom).
    Rendered with numpy at a low internal resolution because everything here is naturally blurry.
    The razor-sharp parts (fibre strands, edges, flare streaks, bubbles) are drawn at native resolution
    by AuroraDetail."""

    def __init__(self, w=480, h=270):
        F = np.float32
        self.F = F
        self.w, self.h = int(w), int(h)
        w, h = self.w, self.h
        self.aspect = w / h
        self.u1 = ((np.arange(w) + 0.5) / w).astype(F)
        self.v1 = ((np.arange(h) + 0.5) / h).astype(F)

        # base gradient: green/yellow on the left, blue on the right
        sv = np.array([0.0, 0.40, 0.62, 0.88, 1.0])
        L = np.array([(9, 99, 74), (17, 133, 62), (111, 154, 65), (209, 206, 49), (225, 225, 60)]) / 255.0
        R = np.array([(13, 93, 104), (27, 124, 156), (35, 149, 186), (69, 189, 224), (80, 205, 235)]) / 255.0
        v1 = self.v1.astype(np.float64)
        Lc = np.stack([np.interp(v1, sv, L[:, k]) for k in range(3)], -1).astype(F)
        Rc = np.stack([np.interp(v1, sv, R[:, k]) for k in range(3)], -1).astype(F)
        wl = ((1.0 - self.u1) ** 1.7).astype(F)
        base = Rc[:, None, :] * (1 - wl[None, :, None]) + Lc[:, None, :] * wl[None, :, None]
        belly = np.exp(-((self.u1 - 0.5) / 0.28) ** 2)[None, :, None] * np.array([-0.02, 0.05, 0.0], F)
        self.base = (base + belly).astype(F)

        # low-res caustic grid
        self.hs = int(h * 0.88)
        self.cw, self.ch = max(8, w // 3), max(8, self.hs // 3)
        cu = (np.arange(self.cw) + 0.5) / self.cw
        cv = (np.arange(self.ch) + 0.5) / self.ch * 0.88
        self.cx = np.repeat((cu[None, :] * self.aspect * 2 * math.pi * 0.55).astype(F), self.ch, 0)
        self.cy = np.repeat((cv[:, None] * 2 * math.pi * 0.55).astype(F), self.cw, 1)
        vs = self.v1[:self.hs, None]
        self.cmask = ((1.0 - _sstep(0.35, 0.95, vs)) * (0.35 + 0.65 * _sstep(0.0, 0.5, vs))).astype(F) * np.ones((1, w), F)

        # static 1-D helpers
        u = self.u1
        self.left_w = left_geometry(u, 0.0)[1].astype(F)
        self.left_soft_amp = _sstep(3.0, 6.0, self.left_w * h * 2 * math.pi / 53.0).astype(F)
        self.left_edge_fade = (1.0 - _sstep(0.50, 0.70, u)).astype(F)
        self.left_in_fade = (1.0 - _sstep(0.55, 0.85, u)).astype(F)
        self.floor_prof = _sstep(0.845, 1.0, self.v1).astype(F)

        self.shafts = [   # x, width, strength, phase, slope
            (0.10, 0.060, 0.55, 0.3, 0.05), (0.265, 0.004, 1.10, 1.1, 0.03), (0.285, 0.050, 0.55, 2.0, 0.04),
            (0.42, 0.035, 0.50, 3.1, 0.06), (0.55, 0.075, 0.45, 4.0, 0.10), (0.68, 0.030, 0.40, 5.3, 0.08),
            (0.80, 0.055, 0.45, 0.8, 0.05), (0.93, 0.040, 0.35, 2.7, 0.02),
        ]
        self.c_white = np.array([1.0, 1.0, 0.97], F)
        self.c_green = np.array([0.55, 0.95, 0.32], F)
        self.c_cyan = np.array([0.35, 0.88, 1.0], F)
        # (rgb x layer) mixing matrix with the tone-map constant folded in, and the pre-scaled base colour planes
        self._mix = (np.stack([self.c_white, self.c_green, self.c_cyan], axis=1) * F(-1.55)).astype(F)
        self._base_neg = np.ascontiguousarray((self.base * F(-1.55)).transpose(2, 0, 1)).astype(F)
        self._layers = np.zeros((3, h, w), F)

    # ----------------------------------------------------------------------------
    def _caustics(self, t):
        px, py = self.cx - 250.0, self.cy - 250.0
        ix, iy = px, py
        c = np.ones_like(px)
        inten = 0.006
        for n in range(4):
            tt = t * (1.0 - 3.5 / (n + 1.0))
            ix, iy = px + np.cos(tt - ix) + np.sin(tt + iy), py + np.sin(tt - iy) + np.cos(tt + ix)
            dx = px / (np.sin(ix + tt) / inten + 1e-6)
            dy = py / (np.cos(iy + tt) / inten + 1e-6)
            c += 1.0 / np.sqrt(dx * dx + dy * dy + 1e-9)
        c = c * 0.25
        c = np.abs(1.17 - np.abs(c) ** 1.4)
        c = np.minimum(c ** 8, 1.5)
        im = Image.fromarray(c.astype(self.F), "F").resize((self.w, self.hs), Image.BILINEAR)
        return np.asarray(im, dtype=self.F)

    def _shafts(self, t):
        w, hs = self.w, self.hs
        v = self.v1[:hs, None]
        out = np.zeros((hs, w), self.F)
        for (x, wd, st, ph, sl) in self.shafts:
            wd2 = wd * (1.0 + 0.25 * math.sin(0.31 * t + ph))
            cx0 = x + 0.018 * math.sin(0.23 * t + ph)
            lo = int(max(0, (cx0 - abs(sl) * 0.6 - wd2 * 3.2) * w))
            hi = int(min(w, (cx0 + abs(sl) * 0.6 + wd2 * 3.2) * w) + 1)
            if hi <= lo:
                continue
            uu = self.u1[None, lo:hi]
            cx = cx0 + sl * (v - 0.4)
            g = np.exp(-(((uu - cx) / wd2) ** 2))
            fl = 0.65 + 0.35 * np.sin(v * 9.0 + ph - 0.55 * t) * np.sin(v * 3.1 - 0.27 * t + ph * 2)
            out[:, lo:hi] += g * fl * (st * (0.75 + 0.25 * math.sin(0.4 * t + ph * 1.7)))
        out *= (1.0 - _sstep(0.30, 0.85, self.v1[:hs]))[:, None] * 0.55
        return out

    def _left_sheet(self, t, G, Wl):
        w, h = self.w, self.h
        c1, r0 = int(w * 0.86), int(h * 0.24)
        u = self.u1[None, :c1]
        v = self.v1[r0:, None]
        top = left_geometry(u, t)[0]
        q = (v - top) / self.left_w[None, :c1]
        inside = _sstep(-0.02, 0.06, q) * (1.0 - _sstep(0.55, 1.15, q)) * self.left_in_fade[None, :c1]
        amp = self.left_soft_amp[None, :c1]
        s2 = (0.5 + 0.5 * np.cos(q * 53.0 - 0.6 * t + 1.7)) ** 3
        qc = np.clip(q, 0, 1)
        G[r0:, :c1] += inside * (0.22 + 0.30 * s2 * amp) * (0.45 + 0.95 * qc)
        edge = np.exp(-((q / 0.022) ** 2)) * self.left_edge_fade[None, :c1]
        G[r0:, :c1] += edge * 1.1
        Wl[r0:, :c1] += edge * 0.25

    def _right_ribbon(self, t, C, Wl):
        w = self.w
        c0 = int(w * 0.50)
        u = self.u1[None, c0:]
        v = self.v1[:, None]
        gx, wr = right_geometry(v, t)
        qr = (gx - u) / wr
        gate = _sstep(0.0, 0.25, v)
        inr = _sstep(-0.05, 0.1, qr) * (1.0 - _sstep(0.7, 1.3, qr)) * gate
        amp = _sstep(3.2, 6.5, wr * w * 2 * math.pi / 17.0)
        sr2 = (0.5 + 0.5 * np.cos(qr * 17.0 + 0.7 * t)) ** 3
        C[:, c0:] += inr * (0.14 + 0.30 * sr2 * amp)
        edge = np.exp(-((qr / 0.05) ** 2)) * gate
        C[:, c0:] += edge * 0.85
        Wl[:, c0:] += edge * 0.35

    def _horizon(self, t, Wl, C):
        h = self.h
        r0 = int(h * 0.66)
        u = self.u1[None, :]
        v = self.v1[r0:, None]
        hy = 0.865 + 0.010 * np.sin(6.2 * u + 0.5 * t)
        xm1 = 0.35 + 0.65 * np.exp(-(((u - 0.52) / 0.50) ** 2))
        xm2 = 0.25 + 0.75 * np.exp(-(((u - 0.55) / 0.40) ** 2))
        band = np.exp(-(((v - hy) / 0.020) ** 2)) * xm1
        wide = np.exp(-(((v - hy) / 0.075) ** 2)) * xm2
        Wl[r0:] += band * (1.2 * (0.85 + 0.15 * math.sin(0.9 * t)))
        C[r0:] += wide * 0.55
        Wl[r0:] += self.floor_prof[r0:, None] * 0.20
        bx = 0.54 + 0.02 * math.sin(0.35 * t)
        d2 = ((u - bx) * self.aspect) ** 2 + ((v - 0.875) * 1.9) ** 2
        Wl[r0:] += np.exp(-d2 / 0.012) * (0.9 + 0.1 * math.sin(1.3 * t))
        C[r0:] += np.exp(-d2 / 0.08) * 0.35

    def render(self, t, gain=1.0):
        """Returns a small PIL RGB image of the soft aurora at time t (seconds)."""
        F = self.F
        w, h, hs = self.w, self.h, self.hs
        L = self._layers                       # (3, h, w): white, green, cyan light layers
        L.fill(0.0)
        Wl, G, C = L[0], L[1], L[2]
        C[:hs] += self._shafts(t) * 0.80
        C[:hs] += self._caustics(t * 0.55) * self.cmask * 0.20
        self._left_sheet(t, G, Wl)
        self._right_ribbon(t, C, Wl)
        self._horizon(t, Wl, C)
        # light layers -> RGB in one matrix product, then filmic tone map 1 - exp(-1.55 x) done in place
        x = np.dot(self._mix, L.reshape(3, -1)).reshape(3, h, w)
        x += self._base_neg
        np.expm1(x, out=x)
        x *= F(-255.0 * gain * (0.97 + 0.03 * math.sin(0.3 * t)))
        x += 0.5
        np.clip(x, 0.0, 255.0, out=x)
        return Image.fromarray(np.ascontiguousarray(x.transpose(1, 2, 0)).astype(np.uint8), "RGB")


class AuroraDetail:
    """SHARP layer of the aurora, drawn at the screen's native resolution as anti-aliased vector curves:
    the fibre strands of both ribbons, their bright edges, the horizon flare streaks and the bubbles.
    Each curve is evaluated analytically per pixel column (or row) and splatted with a thin gaussian profile,
    so cost grows with screen *width*, not screen area."""

    TAPS = (-2, -1, 0, 1, 2)

    def __init__(self, W, H):
        F = np.float32
        self.W, self.H = int(W), int(H)
        self.scale = max(0.75, self.H / 1080.0)
        self.sig = 1.15 * self.scale                     # thin line half-width in pixels
        self.inv_sig2 = np.float32(1.0 / (self.sig * self.sig))
        self.u = ((np.arange(self.W) + 0.5) / self.W).astype(np.float64)
        self.v = ((np.arange(self.H) + 0.5) / self.H).astype(np.float64)

        # left sheet columns (strands fade out where they get too dense to draw cleanly)
        wl = left_geometry(self.u, 0.0)[1]
        pitch = wl * self.H * 2 * math.pi / 150.0
        self.l_amp = (_sstep(2.8 * self.scale, 5.8 * self.scale, pitch) * (1.0 - _sstep(0.55, 0.85, self.u))).astype(np.float64)
        self.l_cols = np.nonzero(self.l_amp > 0.01)[0]
        self.l_w = wl[self.l_cols]
        self.l_a = self.l_amp[self.l_cols]
        self.l_edge_cols = np.nonzero(self.u < 0.74)[0]
        self.l_edge_fade = (1.0 - _sstep(0.50, 0.70, self.u[self.l_edge_cols]))

        # right ribbon rows
        _, wr = right_geometry(self.v, 0.0)
        pitch_r = wr * self.W * 2 * math.pi / 40.0
        self.r_gate = _sstep(0.0, 0.25, self.v)
        self.r_amp = _sstep(2.8 * self.scale, 5.8 * self.scale, pitch_r) * self.r_gate
        self.r_rows = np.arange(self.H)
        self.all_cols = np.arange(self.W)

        self.streaks = [(0.80, 0.5, 0.6), (0.835, 0.35, -0.8), (0.915, 0.4, 0.7), (0.955, 0.25, -0.5)]
        rng = np.random.default_rng(7)
        self.bubbles = [(rng.uniform(0.03, 0.97), rng.uniform(0, 1), rng.uniform(0.010, 0.042),
                         rng.uniform(0.010, 0.030), rng.uniform(0, 6.28)) for _ in range(12)]
        self.col_green = np.array([0.70, 1.00, 0.55], F)
        self.col_cyan = np.array([0.60, 0.95, 1.00], F)
        self.col_white = np.array([1.00, 1.00, 0.97], F)

    # ----------------------------------------------------------------------------
    def _splat(self, flat, mstride, jstride, M, major, center, strength, cosf, color):
        """Screen-blend thin anti-aliased curves into flat (H*W, 3) uint8.
        pixel index = minor * mstride + major * jstride;  center/strength/cosf: (strands, len(major))."""
        F = np.float32
        center = center.astype(F)
        strength = strength.astype(F)
        cosf = cosf.astype(F)
        color = (color * F(1.55)).astype(F)
        for par in (0, 1):                                      # alternate strands so neighbours never collide
            c, st, cs = center[par::2], strength[par::2], cosf[par::2]
            si, ci = np.nonzero(st > 0.012)                     # only pixels where a line is actually visible
            if si.size == 0:
                continue
            cc, s, cv = c[si, ci], st[si, ci], cs[si, ci]
            mj = major[ci] * jstride
            base = np.floor(cc).astype(np.int32)
            for k in self.TAPS:
                r = base + k
                d = (r.astype(F) + F(0.5) - cc) * cv
                w = s * np.exp(-(d * d) * self.inv_sig2)
                ok = (r >= 0) & (r < M) & (w > 0.012)
                if not ok.any():
                    continue
                idx = r[ok] * mstride + mj[ok]
                px = flat[idx].astype(F)
                x = w[ok][:, None] * color[None, :]
                px += (x / (1.0 + x)) * (F(255.0) - px)
                px += F(0.5)
                flat[idx] = px.astype(np.uint8)

    def _left(self, frame, flat, t, gain):
        cols = self.l_cols
        if cols.size < 4:
            return
        H, W = self.H, self.W
        top, _ = left_geometry(self.u[cols], t)
        S = 33
        j = np.arange(S, dtype=np.float64)[:, None]
        q = ((2 * math.pi * j - 0.9 * t + 7.5) % 202.5) / 150.0 - 0.05            # (S,1), drifts toward the top edge
        y = (top[None, :] + q * self.l_w[None, :]) * H
        st = (0.62 * gain) * self.l_a[None, :] * (0.45 + 0.95 * np.clip(q, 0, 1)) \
             * _sstep(-0.02, 0.06, q) * (1.0 - _sstep(0.55, 1.15, q))
        slope = np.gradient(y, axis=1)
        self._splat(flat, W, 1, H, cols, y, st, 1.0 / np.sqrt(1.0 + slope * slope), self.col_green)
        # bright crisp core on the sheet's top edge
        ec = self.l_edge_cols
        te, _ = left_geometry(self.u[ec], t)
        ye = (te * H)[None, :]
        se = ((0.85 * gain) * self.l_edge_fade)[None, :]
        sl = np.gradient(ye, axis=1)
        self._splat(flat, W, 1, H, ec, ye, se, 1.0 / np.sqrt(1.0 + sl * sl), self.col_white * 0.9 + self.col_green * 0.4)

    def _right(self, frame, flat, t, gain):
        H, W = self.H, self.W
        gx, wr = right_geometry(self.v, t)
        S = 9
        j = np.arange(S, dtype=np.float64)[:, None]
        qr = ((2 * math.pi * j + 1.2 * t + 4.0) % 56.0) / 40.0 - 0.1
        x = (gx[None, :] - qr * wr[None, :]) * W
        st = (0.62 * gain) * self.r_amp[None, :] * _sstep(-0.05, 0.1, qr) * (1.0 - _sstep(0.7, 1.3, qr))
        slope = np.gradient(x, axis=1)
        self._splat(flat, 1, W, W, self.r_rows, x, st, 1.0 / np.sqrt(1.0 + slope * slope), self.col_cyan)
        xe = (gx * W)[None, :]
        se = ((0.80 * gain) * self.r_gate)[None, :]
        sl = np.gradient(xe, axis=1)
        self._splat(flat, 1, W, W, self.r_rows, xe, se, 1.0 / np.sqrt(1.0 + sl * sl), self.col_white * 0.9 + self.col_cyan * 0.3)

    def _streaks(self, frame, flat, t, gain):
        H, W = self.H, self.W
        cols = self.all_cols
        u = self.u
        ys, ss = [], []
        for k, (yy, amp, sp) in enumerate(self.streaks):
            ys.append((yy + 0.006 * np.sin(u * 7.0 + sp * t + k)) * H)
            ss.append((0.62 * amp * gain) * np.exp(-(((u - 0.5 - 0.08 * math.sin(0.3 * t + k)) / 0.45) ** 2)))
        y = np.array(ys)
        st = np.array(ss)
        sl = np.gradient(y, axis=1)
        self._splat(flat, W, 1, H, cols, y, st, 1.0 / np.sqrt(1.0 + sl * sl), self.col_white)

    def _bubbles(self, frame, t, gain):
        H, W = self.H, self.W
        for (bx, by0, r, sp, ph) in self.bubbles:
            by = 1.12 - ((by0 + t * sp) % 1.25)
            x = bx + 0.012 * math.sin(0.5 * t + ph)
            cx, cy, rp = x * W, by * H, r * H
            x0, x1 = int(max(0, cx - rp * 1.6 - 2)), int(min(W, cx + rp * 1.6 + 2))
            y0, y1 = int(max(0, cy - rp * 1.6 - 2)), int(min(H, cy + rp * 1.6 + 2))
            if x1 <= x0 or y1 <= y0:
                continue
            uu = (np.arange(x0, x1, dtype=np.float32) + 0.5 - cx)[None, :]
            vv = (np.arange(y0, y1, dtype=np.float32) + 0.5 - cy)[:, None]
            d = np.sqrt(uu * uu + vv * vv)
            rim = np.exp(-(((d - rp) / max(1.3 * self.scale, rp * 0.045)) ** 2)) * 0.42
            fill = (1.0 - _sstep(rp * 0.2, rp, d)) * 0.05 * (d < rp)
            hl = np.exp(-(((uu + rp * 0.30) ** 2 + (vv + rp * 0.38) ** 2) / (rp * rp * 0.035))) * 0.45
            fade = 0.55 * float(np.clip(1.0 - abs(by - 0.5) * 0.9, 0.2, 1.0)) * gain
            lay = ((rim + fill + hl) * fade).astype(np.float32)
            px = frame[y0:y1, x0:x1].astype(np.float32)
            xx = lay[..., None] * np.array([0.8, 1.0, 1.0], np.float32) * np.float32(1.55)
            px += (xx / (1.0 + xx)) * (255.0 - px)
            frame[y0:y1, x0:x1] = (px + 0.5).astype(np.uint8)

    def apply(self, frame, t, gain):
        if gain <= 0.004:
            return
        flat = frame.reshape(-1, 3)                         # contiguous view, no copy
        self._left(frame, flat, t, gain)
        self._right(frame, flat, t, gain)
        self._streaks(frame, flat, t, gain)
        self._bubbles(frame, t, gain)


class AuroraHD:
    """Full-resolution aurora = soft low-res layer (bicubic-stretched) + native-resolution vector detail."""

    def __init__(self, W, H, soft_width):
        self.size = (int(W), int(H))
        sh = max(8, int(round(soft_width * H / W)))
        self.soft = Aurora(soft_width, sh)
        self.detail = AuroraDetail(W, H)

    def render(self, t, gain=1.0):
        low = self.soft.render(t, gain)
        frame = np.array(low.resize(self.size, Image.BILINEAR))
        self.detail.apply(frame, t, gain)
        return Image.fromarray(frame, "RGB")


# --------------------------------------------------------------------------------------
#  Blue "streak" background used by the exit animation (Windows-XP-style luminous bundles)
# --------------------------------------------------------------------------------------
XP_BUNDLES = [   # v at u=0, slope, width, brightness, phase
    (0.06, 0.58, 0.030, 1.00, 0.0),
    (0.20, 0.54, 0.045, 0.85, 1.7),
    (0.36, 0.50, 0.055, 0.70, 3.1),
    (0.58, 0.38, 0.070, 0.45, 4.4),
    (0.76, 0.26, 0.060, 0.38, 5.6),
]


def xp_geometry(b, u, t):
    """Centre line, half-width and along-the-streak brightness of one bundle (u = 0..1 across the screen)."""
    a, m, w0, br, ph = b
    centre = a + m * u + 0.030 * np.sin(2.4 * u + ph + 0.30 * t) + 0.012 * np.sin(6.1 * u - 0.45 * t + 2 * ph)
    width = w0 * (1.0 + 0.9 * u)
    along = br * (0.30 + 0.70 * np.exp(-(u / 0.5) ** 2)) * (1.0 - 0.55 * _sstep(0.8, 1.0, u))
    return centre, width, along


class BlueAurora:
    """Soft layer: navy-to-royal-blue gradient, broad luminous streak bundles, top-left bloom."""

    def __init__(self, w=416, h=234):
        F = np.float32
        self.F = F
        self.w, self.h = int(w), int(h)
        self.aspect = self.w / self.h
        self.u1 = ((np.arange(self.w) + 0.5) / self.w).astype(F)
        self.v1 = ((np.arange(self.h) + 0.5) / self.h).astype(F)
        U, V = self.u1[None, :], self.v1[:, None]
        s = np.clip(0.50 * V + 0.55 * (1.0 - U) - 0.12, 0.0, 1.0)
        stops = np.array([0.0, 0.38, 0.72, 1.0])
        cols = np.array([(62, 88, 212), (14, 80, 216), (4, 32, 152), (2, 10, 94)], dtype=np.float64) / 255.0
        base = np.stack([np.interp(s, stops, cols[:, k]) for k in range(3)], -1)         # target on-screen colour
        self._base_neg = np.ascontiguousarray(np.log(1.0 - np.clip(base, 0, 0.985)).transpose(2, 0, 1)).astype(F)  # = -1.55 * linear
        c_cyan = np.array([0.55, 0.88, 1.0], F)
        c_blue = np.array([0.20, 0.50, 1.0], F)
        self._mix = (np.stack([c_cyan, c_blue], axis=1) * F(-1.55)).astype(F)
        self._layers = np.zeros((2, self.h, self.w), F)

    def render(self, t, gain=1.0):
        F = self.F
        w, h = self.w, self.h
        L = self._layers
        L.fill(0.0)
        K, B = L[0], L[1]
        V = self.v1[:, None]
        for b in XP_BUNDLES:
            c, wd, br = xp_geometry(b, self.u1, t)
            d = (V - c[None, :]) / wd[None, :]
            g = np.exp(-d * d)
            tex = 0.55 + 0.45 * np.cos(d * 5.5 + 0.35 * t + b[4])
            lum = g * tex * br[None, :]
            B += lum * 0.9
            K += lum * lum * 1.3
        U = self.u1[None, :]
        K += 0.80 * np.exp(-((((U - 0.06) * self.aspect) ** 2) / 0.10 + ((V - 0.10) ** 2) / 0.035))      # top-left bloom
        B += 0.10 * np.exp(-(((V - (0.45 + 0.30 * U)) / 0.25) ** 2))                                          # broad haze
        x = np.dot(self._mix, L.reshape(2, -1)).reshape(3, h, w)
        x += self._base_neg
        np.expm1(x, out=x)
        x *= F(-255.0 * gain * (0.97 + 0.03 * math.sin(0.35 * t)))
        x += 0.5
        np.clip(x, 0.0, 255.0, out=x)
        return Image.fromarray(np.ascontiguousarray(x.transpose(1, 2, 0)).astype(np.uint8), "RGB")


class BlueDetail(AuroraDetail):
    """Native-resolution fine light fibres inside each streak bundle (reuses AuroraDetail's anti-aliased splatter)."""
    FIBERS = 14

    def __init__(self, W, H):
        self.W, self.H = int(W), int(H)
        self.scale = max(0.75, self.H / 1080.0)
        self.sig = 1.05 * self.scale
        self.inv_sig2 = np.float32(1.0 / (self.sig * self.sig))
        self.u = ((np.arange(self.W) + 0.5) / self.W).astype(np.float64)
        self.cols = np.nonzero(self.u < 0.95)[0]
        self.uc = self.u[self.cols]
        self.col_fiber = np.array([0.72, 0.93, 1.0], np.float32)

    def apply(self, frame, t, gain):
        if gain <= 0.004:
            return
        H, W, S = self.H, self.W, self.FIBERS
        flat = frame.reshape(-1, 3)
        j = np.arange(S, dtype=np.float64)[:, None]
        for bi, b in enumerate(XP_BUNDLES):
            c, wd, br = xp_geometry(b, self.uc, t)
            drift = 0.045 * t * (1 if bi % 2 == 0 else -1) + b[4] * 0.1
            q = ((j * 2.7 / S + drift + 1.35) % 2.7) - 1.35                       # fibres drift slowly across the bundle like my farts drift through the air lol :P
            y = (c[None, :] + q * wd[None, :]) * H
            st = (0.42 * gain) * br[None, :] * np.exp(-(q / 0.75) ** 2) * (1.0 - _sstep(0.78, 0.95, self.uc))[None, :]
            slope = np.gradient(y, axis=1)
            self._splat(flat, W, 1, H, self.cols, y, st, 1.0 / np.sqrt(1.0 + slope * slope), self.col_fiber)


class BlueHD:
    """Full-resolution XP-style blue streak background = soft layer + native-resolution fibres."""

    def __init__(self, W, H, soft_width=416):
        self.size = (int(W), int(H))
        self.soft = BlueAurora(soft_width, max(8, int(round(soft_width * H / W))))
        self.detail = BlueDetail(W, H)

    def render(self, t, gain=1.0):
        frame = np.array(self.soft.render(t, gain).resize(self.size, Image.BILINEAR))
        self.detail.apply(frame, t, gain)
        return Image.fromarray(frame, "RGB")


class StaticBackdrop:
    """Fallback if numpy is missing: a calm Vista-coloured gradient (still fades in)."""

    def __init__(self, w=480, h=270, colors=((12, 120, 80), (13, 100, 110), (225, 225, 60), (80, 205, 235))):
        self.w, self.h = w, h
        tl, tr, bl, br = colors
        hm = Image.linear_gradient("L").rotate(90).resize((w, h))
        vm = Image.linear_gradient("L").resize((w, h))
        top = Image.composite(Image.new("RGB", (w, h), tr), Image.new("RGB", (w, h), tl), hm.point(lambda p: 255 - p))
        bot = Image.composite(Image.new("RGB", (w, h), br), Image.new("RGB", (w, h), bl), hm.point(lambda p: 255 - p))
        self.img = Image.composite(bot, top, vm)

    def render(self, t, gain=1.0):
        if gain >= 0.999:
            return self.img
        return Image.blend(Image.new("RGB", self.img.size, (0, 0, 0)), self.img, gain)


