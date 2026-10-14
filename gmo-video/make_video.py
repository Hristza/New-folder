"""Генерира учебно видео „ГМО бактерия, която произвежда човешки инсулин“.

Изисква: Python 3, Pillow, numpy, ffmpeg.
Стартиране:  python3 make_video.py   ->  gmo_insulin_ecoli.mp4
"""
import math
import os
import subprocess
import sys
import wave
from multiprocessing import Pool

import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H = 1920, 1080
S = 2  # суперсемплиране за гладки ръбове
FPS = 30
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gmo_insulin_ecoli.mp4")

FONT_DIR = "/usr/share/fonts/opentype/inter"
FONTS = {
    "reg": os.path.join(FONT_DIR, "Inter-Regular.otf"),
    "med": os.path.join(FONT_DIR, "Inter-Medium.otf"),
    "bold": os.path.join(FONT_DIR, "Inter-Bold.otf"),
    "xbold": os.path.join(FONT_DIR, "Inter-ExtraBold.otf"),
    "it": os.path.join(FONT_DIR, "Inter-Italic.otf"),
}
_font_cache = {}

# Палитра
BG_TOP = (9, 21, 43)
BG_BOT = (16, 46, 66)
WHITE = (240, 246, 250)
MUTED = (160, 185, 205)
TEAL = (64, 214, 190)
ORANGE = (255, 159, 67)
PINK = (255, 107, 129)
PURPLE = (162, 120, 255)
GREEN = (98, 205, 122)
GREEN_D = (40, 120, 70)
YELLOW = (255, 214, 102)
BLUE = (84, 160, 255)
BASES = [TEAL, ORANGE, PINK, YELLOW]


def font(kind, size):
    key = (kind, size)
    if key not in _font_cache:
        _font_cache[key] = ImageFont.truetype(FONTS[kind], int(size * S))
    return _font_cache[key]


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease(x):
    x = clamp(x)
    return x * x * (3 - 2 * x)


def ease_out(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


def prog(t, start, dur):
    return ease((t - start) / dur)


def lerp(a, b, x):
    return a + (b - a) * x


def rgba(c, a=1.0):
    return (c[0], c[1], c[2], int(255 * clamp(a)))


def mix(c1, c2, x):
    return tuple(int(lerp(c1[i], c2[i], x)) for i in range(3))


# ---------------------------------------------------------------- рисуване
class Canvas:
    def __init__(self, img):
        self.img = img
        self.d = ImageDraw.Draw(img, "RGBA")

    @staticmethod
    def p(v):
        return int(round(v * S))

    def text(self, x, y, s, size, color=WHITE, a=1.0, kind="reg", anchor="la"):
        if a <= 0.01:
            return
        self.d.text((self.p(x), self.p(y)), s, font=font(kind, size), fill=rgba(color, a), anchor=anchor)

    def text_w(self, s, size, kind="reg"):
        return font(kind, size).getlength(s) / S

    def wrap(self, s, size, maxw, kind="reg"):
        lines, cur = [], ""
        for word in s.split(" "):
            test = (cur + " " + word).strip()
            if self.text_w(test, size, kind) <= maxw or not cur:
                cur = test
            else:
                lines.append(cur)
                cur = word
        if cur:
            lines.append(cur)
        return lines

    def para(self, x, y, s, size, maxw, color=WHITE, a=1.0, kind="reg", lh=1.35, align="left"):
        lines = self.wrap(s, size, maxw, kind)
        for i, ln in enumerate(lines):
            yy = y + i * size * lh
            if align == "center":
                self.text(x, yy, ln, size, color, a, kind, anchor="ma")
            else:
                self.text(x, yy, ln, size, color, a, kind)
        return len(lines) * size * lh

    def circle(self, cx, cy, r, fill=None, outline=None, width=0, a=1.0):
        if r <= 0:
            return
        box = [self.p(cx - r), self.p(cy - r), self.p(cx + r), self.p(cy + r)]
        self.d.ellipse(box, fill=rgba(fill, a) if fill else None,
                       outline=rgba(outline, a) if outline else None, width=self.p(width))

    def rrect(self, x0, y0, x1, y1, r, fill=None, outline=None, width=0, a=1.0):
        self.d.rounded_rectangle([self.p(x0), self.p(y0), self.p(x1), self.p(y1)], radius=self.p(r),
                                 fill=rgba(fill, a) if fill else None,
                                 outline=rgba(outline, a) if outline else None, width=self.p(width))

    def line(self, pts, color, width, a=1.0):
        self.d.line([(self.p(x), self.p(y)) for x, y in pts], fill=rgba(color, a), width=self.p(width), joint="curve")

    def arc(self, cx, cy, r, start, end, color, width, a=1.0):
        box = [self.p(cx - r), self.p(cy - r), self.p(cx + r), self.p(cy + r)]
        self.d.arc(box, start, end, fill=rgba(color, a), width=self.p(width))

    def poly(self, pts, fill, a=1.0, outline=None):
        self.d.polygon([(self.p(x), self.p(y)) for x, y in pts], fill=rgba(fill, a),
                       outline=rgba(outline, a) if outline else None)


# ---------------------------------------------------------------- фон
_BG = None


def background():
    global _BG
    if _BG is None:
        g = np.linspace(0, 1, H * S)[:, None, None]
        top = np.array(BG_TOP)[None, None, :]
        bot = np.array(BG_BOT)[None, None, :]
        arr = (top * (1 - g) + bot * g) * np.ones((1, W * S, 1))
        # мек светъл „ореол“ отдясно горе
        yy, xx = np.mgrid[0:H * S, 0:W * S]
        dist = np.sqrt((xx - W * S * 0.8) ** 2 + (yy - H * S * 0.15) ** 2) / (W * S)
        glow = np.clip(1 - dist * 1.6, 0, 1)[..., None] ** 2
        arr = arr + glow * np.array([20, 50, 60])[None, None, :]
        _BG = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")
    return _BG


rng = np.random.default_rng(7)
PARTICLES = [(rng.uniform(0, W), rng.uniform(0, H), rng.uniform(1.5, 4.5), rng.uniform(8, 25), rng.uniform(0, 6.28))
             for _ in range(55)]


def draw_particles(c, t):
    for x, y, r, sp, ph in PARTICLES:
        yy = (y - t * sp) % (H + 40) - 20
        xx = x + 12 * math.sin(t * 0.4 + ph)
        c.circle(xx, yy, r, fill=TEAL, a=0.10 + 0.06 * math.sin(t + ph))


# ---------------------------------------------------------------- елементи
def heading(c, t, title, label=None):
    a = prog(t, 0.1, 0.6)
    dx = lerp(-40, 0, ease_out((t - 0.1) / 0.7))
    c.rrect(110 + dx, 92, 120 + dx, 170, 4, fill=TEAL, a=a)
    if label:
        c.text(145 + dx, 86, label.upper(), 22, TEAL, a, "bold")
        c.text(145 + dx, 116, title, 52, WHITE, a, "bold")
    else:
        c.text(145 + dx, 100, title, 56, WHITE, a, "bold")


def caption(c, t, s, start=0.0, size=36):
    a = prog(t, start, 0.5)
    if a <= 0:
        return
    lines = c.wrap(s, size, 1500, "med")
    h = len(lines) * size * 1.35 + 44
    y0 = 1000 - h
    c.rrect(160, y0, 1760, 1000, 22, fill=(6, 14, 30), a=0.72 * a)
    c.rrect(160, y0, 168, 1000, 4, fill=ORANGE, a=a)
    for i, ln in enumerate(lines):
        c.text(960, y0 + 22 + i * size * 1.35, ln, size, WHITE, a, "med", anchor="ma")


def helix(c, x0, x1, cy, amp, phase, a=1.0, step=26, width=6, hl=None, hl_dy=0.0, hl_glow=0.0,
          colors=(TEAL, BLUE)):
    """Двойна спирала на ДНК. hl=(xa, xb) — подчертан участък (гена), който може да се отмести по y."""
    def off(x):
        return hl_dy if hl and hl[0] <= x <= hl[1] else 0.0

    xs = np.arange(x0, x1 + 1, 4)
    # задна нишка, стъпала, предна нишка
    for k, x in enumerate(np.arange(x0, x1, step)):
        th = x * 0.018 + phase
        y1 = cy + amp * math.sin(th) + off(x)
        y2 = cy - amp * math.sin(th) + off(x)
        in_hl = hl and hl[0] <= x <= hl[1]
        col = ORANGE if in_hl else BASES[k % 4]
        c.line([(x, y1), (x, (y1 + y2) / 2)], col, 5, a * 0.9)
        c.line([(x, (y1 + y2) / 2), (x, y2)], BASES[(k + 2) % 4] if not in_hl else YELLOW, 5, a * 0.9)
    segs = []
    if hl:
        segs = [(x0, hl[0]), (hl[0], hl[1]), (hl[1], x1)]
    else:
        segs = [(x0, x1)]
    for sa, sb in segs:
        xs = np.arange(sa, sb + 1, 4)
        if len(xs) < 2:
            continue
        is_hl = hl and sa == hl[0]
        for sign, col in ((1, colors[0]), (-1, colors[1])):
            ccol = ORANGE if is_hl else col
            pts = [(x, cy + sign * amp * math.sin(x * 0.018 + phase) + off((sa + sb) / 2)) for x in xs]
            if is_hl and hl_glow > 0:
                c.line(pts, YELLOW, width + 10, a * 0.25 * hl_glow)
            c.line(pts, ccol, width, a)


def bacterium(c, cx, cy, w, h, a=1.0, t=0.0, glow=0.0, plasmids=1, detail=True, rot_wiggle=0.0):
    if glow > 0:
        c.rrect(cx - w / 2 - 14, cy - h / 2 - 14, cx + w / 2 + 14, cy + h / 2 + 14, h / 2 + 14,
                fill=YELLOW, a=a * 0.18 * glow)
    if detail:
        # флагели
        for i, side in enumerate((-1, 1)):
            pts = []
            for k in range(30):
                u = k / 29
                xx = cx + side * (w / 2 + u * w * 0.35)
                yy = cy + (i - 0.5) * h * 0.3 + math.sin(u * 9 + t * 6 + i) * h * 0.08
                pts.append((xx, yy))
            c.line(pts, GREEN, max(2, h * 0.025), a * 0.7)
    c.rrect(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2, h / 2, fill=GREEN, outline=GREEN_D,
            width=max(2, h * 0.04), a=a * 0.9)
    c.rrect(cx - w / 2 + h * 0.12, cy - h / 2 + h * 0.12, cx + w / 2 - h * 0.12, cy + h / 2 - h * 0.12,
            h * 0.38, fill=(150, 230, 165), a=a * 0.45)
    if detail:
        # хромозома (заплетена линия)
        pts = []
        for k in range(80):
            u = k / 79 * 2 * math.pi
            rr = 0.22 + 0.06 * math.sin(5 * u + t)
            pts.append((cx - w * 0.08 + math.cos(u) * w * rr, cy + math.sin(u) * h * rr * 0.9))
        c.line(pts, PURPLE, max(2, h * 0.025), a * 0.8)
        for i in range(plasmids):
            px = cx + w * (0.25 + 0.08 * i)
            py = cy + h * (0.12 - 0.25 * i)
            r = h * 0.09
            c.circle(px, py, r, outline=ORANGE if glow > 0 else BLUE, width=max(2, h * 0.025), a=a)


def plasmid(c, cx, cy, r, a=1.0, gap=0.0, gene=0.0, gene_dx=0.0, gene_dy=0.0, gene_a=None, w=14, ticks=True,
            gene_color=ORANGE):
    """Плазмид — двойна пръстеновидна ДНК. gap — ъгъл на разреза (градуси, центриран на 0°)."""
    g = gap / 2
    for rr, col in ((r, BLUE), (r - w * 1.4, TEAL)):
        if gap > 0:
            c.arc(cx, cy, rr, g, 360 - g, col, w, a)
        else:
            c.arc(cx, cy, rr, 0, 360, col, w, a)
    if ticks:
        n = 36
        for k in range(n):
            ang = k * 360 / n
            if gap > 0 and (ang <= g + 2 or ang >= 360 - g - 2):
                continue
            th = math.radians(ang)
            r1, r2 = r - w * 0.4, r - w * 1.0
            c.line([(cx + math.cos(th) * r1, cy + math.sin(th) * r1), (cx + math.cos(th) * r2, cy + math.sin(th) * r2)],
                   BASES[k % 4], max(2, w * 0.3), a * 0.9)
    if gene > 0:
        ga = a if gene_a is None else gene_a
        half = gene / 2
        gx, gy = cx + gene_dx, cy + gene_dy
        c.arc(gx, gy, r, -half, half, gene_color, w, ga)
        c.arc(gx, gy, r - w * 1.4, -half, half, YELLOW, w, ga)


def enzyme(c, x, y, r, mouth, angle=180, a=1.0, color=PURPLE):
    """Рестрикционен ензим като „пакман“ (молекулярна ножица)."""
    m = 8 + 35 * mouth
    box = [c.p(x - r), c.p(y - r), c.p(x + r), c.p(y + r)]
    c.d.pieslice(box, angle + m, angle + 360 - m, fill=rgba(color, a), outline=rgba((90, 60, 180), a), width=c.p(3))
    ex = x + math.cos(math.radians(angle - 90 + 40)) * r * 0.45
    ey = y + math.sin(math.radians(angle - 90 + 40)) * r * 0.45
    c.circle(ex, ey, r * 0.1, fill=WHITE, a=a)


def sparkle(c, x, y, r, a, color=YELLOW):
    for k in range(4):
        th = k * math.pi / 2 + math.pi / 4 * (k % 2)
        c.line([(x, y), (x + math.cos(th) * r, y + math.sin(th) * r)], color, 4, a)
    c.circle(x, y, r * 0.25, fill=WHITE, a=a)


def check_icon(c, x, y, r, a, color=GREEN):
    c.circle(x, y, r, fill=color, a=a)
    c.line([(x - r * 0.45, y + r * 0.02), (x - r * 0.1, y + r * 0.38), (x + r * 0.5, y - r * 0.35)], WHITE,
           r * 0.22, a)


def vial(c, x, y, w, h, fill_lvl, a=1.0, label=True):
    c.rrect(x - w * 0.32, y - h / 2 - h * 0.14, x + w * 0.32, y - h / 2 + 2, 6, fill=(200, 210, 220), a=a)
    c.rrect(x - w * 0.4, y - h / 2 - h * 0.2, x + w * 0.4, y - h / 2 - h * 0.11, 6, fill=PINK, a=a)
    c.rrect(x - w / 2, y - h / 2, x + w / 2, y + h / 2, w * 0.18, fill=(220, 235, 245), a=a * 0.25,
            outline=(220, 235, 245), width=4)
    lv = y + h / 2 - 8 - (h - 28) * fill_lvl
    if fill_lvl > 0.02:
        c.rrect(x - w / 2 + 8, lv, x + w / 2 - 8, y + h / 2 - 8, w * 0.14, fill=(180, 225, 255), a=a * 0.85)
    if label:
        c.rrect(x - w / 2 + 6, y - h * 0.08, x + w / 2 - 6, y + h * 0.2, 6, fill=WHITE, a=a)
        c.text(x, y + h * 0.06, "ИНСУЛИН", w * 0.16, (30, 60, 110), a, "xbold", anchor="mm")


def arrow(c, x0, y0, x1, y1, color, width, a, head=22):
    c.line([(x0, y0), (x1, y1)], color, width, a)
    ang = math.atan2(y1 - y0, x1 - x0)
    pts = [(x1, y1),
           (x1 - head * math.cos(ang - 0.45), y1 - head * math.sin(ang - 0.45)),
           (x1 - head * math.cos(ang + 0.45), y1 - head * math.sin(ang + 0.45))]
    c.poly(pts, color, a)


def person(c, x, y, s, a, color=PINK):
    c.circle(x, y - s * 0.55, s * 0.28, fill=color, a=a)
    c.rrect(x - s * 0.42, y - s * 0.2, x + s * 0.42, y + s * 0.75, s * 0.3, fill=color, a=a)


# ---------------------------------------------------------------- сцени
def sc_title(c, t, d):
    helix(c, -40, W + 40, 560, 95, t * 1.6, a=0.35 + 0.15 * prog(t, 0, 1.5), step=30, width=7)
    a1 = prog(t, 0.6, 1.0)
    c.rrect(260, 300, 1660, 820, 40, fill=(6, 14, 30), a=0.70 * a1)
    c.text(960, 360, "ГМО В МЕДИЦИНАТА", 30, TEAL, a1, "bold", anchor="ma")
    a2 = prog(t, 1.2, 1.0)
    c.text(960, 430, "Бактерията, която", 84, WHITE, a2, "xbold", anchor="ma")
    c.text(960, 535, "произвежда инсулин", 84, ORANGE, a2, "xbold", anchor="ma")
    a3 = prog(t, 2.4, 1.0)
    c.text(960, 675, "Генно модифицирана Escherichia coli", 40, MUTED, a3, "it", anchor="ma")
    c.text(960, 735, "и човешкият инсулин", 40, MUTED, a3, "it", anchor="ma")
    a4 = prog(t, 3.4, 1.0)
    bacterium(c, 960, 905, 210, 90, a4, t, glow=0.6 + 0.4 * math.sin(t * 3), plasmids=1)


def sc_problem(c, t, d):
    heading(c, t, "Проблемът: диабет", "Защо е нужно?")
    # брояч
    a = prog(t, 0.6, 0.8)
    n = int(500 * ease_out((t - 0.8) / 2.6))
    c.rrect(140, 250, 760, 800, 34, fill=(6, 14, 30), a=0.55 * a)
    c.text(450, 300, "по света живеят", 34, MUTED, a, "med", anchor="ma")
    c.text(450, 360, f"{max(n, 0)}+", 150, ORANGE, a, "xbold", anchor="ma")
    c.text(450, 540, "милиона", 54, WHITE, a, "bold", anchor="ma")
    c.text(450, 610, "възрастни с диабет", 40, WHITE, a, "med", anchor="ma")
    c.text(450, 720, "Източник: IDF Diabetes Atlas", 22, MUTED, a * 0.8, "it", anchor="ma")
    items = [
        ("Инсулинът е хормон, който регулира нивото на захар в кръвта.", 2.0),
        ("Много хора с диабет трябва да си го инжектират всеки ден.", 4.0),
        ("Преди 1982 г. инсулинът се е извличал от панкреаса на прасета и крави.", 6.0),
        ("Количествата са ограничени, а при някои хора животинският инсулин предизвиква алергии.", 8.0),
    ]
    y = 260
    for s, st in items:
        a = prog(t, st, 0.6)
        dx = lerp(40, 0, ease_out((t - st) / 0.7))
        c.circle(870 + dx, y + 24, 10, fill=TEAL, a=a)
        h = c.para(905 + dx, y, s, 36, 870, WHITE, a, "med", lh=1.3)
        y += h + 46


def sc_gmo(c, t, d):
    heading(c, t, "Какво е ГМО?", "Определение")
    a = prog(t, 0.6, 0.8)
    c.rrect(140, 230, 1780, 440, 30, fill=(6, 14, 30), a=0.6 * a)
    c.rrect(140, 230, 150, 440, 4, fill=TEAL, a=a)
    c.para(190, 265, "Генетично модифициран организъм (ГМО) е организъм, чиято ДНК е променена "
                     "с методите на генното инженерство — например чрез добавяне на ген от друг вид.",
           42, 1540, WHITE, a, "med", lh=1.35)
    # схема човек -> ген -> бактерия
    a1 = prog(t, 3.0, 0.7)
    person(c, 430, 640, 150, a1)
    c.text(430, 760, "Човек", 34, WHITE, a1, "bold", anchor="ma")
    a2 = prog(t, 4.0, 0.7)
    arrow(c, 560, 640, 700, 640, MUTED, 6, a2)
    helix(c, 740, 1100, 640, 40, t * 2, a=a2, step=22, width=5, hl=(740, 1100), hl_glow=1.0)
    c.text(920, 760, "ген за инсулин", 34, ORANGE, a2, "bold", anchor="ma")
    a3 = prog(t, 5.0, 0.7)
    arrow(c, 1140, 640, 1280, 640, MUTED, 6, a3)
    bacterium(c, 1520, 640, 330, 150, a3, t, glow=a3 * (0.5 + 0.5 * math.sin(t * 3)))
    c.text(1520, 760, "E. coli", 34, GREEN, a3, "bold", anchor="ma")
    caption(c, t, "Нашият пример: в бактерията E. coli учените вграждат човешкия ген за инсулин.", 6.0)


STEP_TITLE = "Как се създава ГМО бактерията?"


def sc_step1(c, t, d):
    heading(c, t, STEP_TITLE, "Стъпка 1 от 5")
    a = prog(t, 0.3, 0.8)
    c.circle(470, 500, 300, fill=(255, 140, 160), a=0.18 * a, outline=PINK, width=5)
    c.circle(470, 500, 125, fill=PURPLE, a=0.45 * a, outline=PURPLE, width=4)
    c.text(470, 830, "човешка клетка", 30, MUTED, a, "med", anchor="ma")
    c.text(470, 480, "ядро", 28, WHITE, a, "bold", anchor="ma")
    grow = prog(t, 1.0, 1.6)
    if grow > 0:
        x1 = lerp(560, 1780, grow)
        lift = -190 * prog(t, 3.6, 1.2)
        helix(c, 560, x1, 500, 34, t * 1.5, a=1.0, step=22, width=5,
              hl=(1080, 1340) if t > 2.5 else None, hl_dy=lift, hl_glow=prog(t, 2.5, 0.6))
        a2 = prog(t, 4.4, 0.6)
        c.text(1210, 205, "ген за инсулин", 36, ORANGE, a2, "bold", anchor="ma")
    caption(c, t, "1. Изолира се човешкият ген, който „кодира“ инсулина (днес може и да се синтезира в лаборатория).", 1.2)


def sc_step2(c, t, d):
    heading(c, t, STEP_TITLE, "Стъпка 2 от 5")
    zoom = prog(t, 1.8, 1.4)
    ab = 1 - zoom
    bacterium(c, 960, 520, 1100, 480, ab, t, plasmids=0, detail=True)
    px, py, pr = lerp(1230, 960, zoom), lerp(560, 520, zoom), lerp(80, 230, zoom)
    pw = lerp(8, 16, zoom)
    gap = 44 * prog(t, 5.1, 0.6)
    plasmid(c, px, py, pr, 1.0, gap=gap, w=pw, ticks=zoom > 0.5)
    a_l = prog(t, 0.6, 0.6) * (1 - prog(t, 1.6, 0.4))
    c.text(1230, 420, "плазмид", 32, ORANGE, a_l, "bold", anchor="ma")
    c.text(960, 300, "бактерия E. coli", 32, GREEN, a_l, "bold", anchor="ma")
    c.text(960, 520 + 230 + 26, "плазмид — малка кръгова ДНК", 30, MUTED, prog(t, 3.0, 0.6), "med", anchor="ma")
    # ензимът идва отдясно, „захапва“ и си отива
    if t > 3.2:
        ein = ease_out((t - 3.2) / 1.6)
        eout = ease((t - 6.0) / 1.2)
        ex = lerp(1900, 960 + 230 + 70, ein) + 700 * eout
        mouth = abs(math.sin((t - 3.2) * 5)) if 4.6 < t < 5.6 else 0.6
        enzyme(c, ex, 520, 62, mouth, angle=180, a=1.0)
        c.text(ex, 610, "рестрикционен ензим", 28, PURPLE, prog(t, 3.8, 0.5) * (1 - eout), "bold", anchor="ma")
    if 5.0 < t < 6.2:
        sparkle(c, 960 + 230 - 10, 520, 34, 1 - abs(t - 5.4) / 0.8)
    caption(c, t, "2. Плазмид от бактерията се разрязва с рестрикционен ензим — „молекулярна ножица“.", 1.2)


def sc_step3(c, t, d):
    heading(c, t, STEP_TITLE, "Стъпка 3 от 5")
    cx, cy, r = 960, 520, 230
    move = ease_out((t - 0.8) / 2.6)
    plasmid(c, cx, cy, r, 1.0, gap=44, w=16, gene=44 if t > 0.3 else 0,
            gene_dx=lerp(720, 0, move), gene_dy=lerp(-160, 0, move), gene_a=prog(t, 0.3, 0.6))
    c.text(cx + r + lerp(720, 0, move), cy + lerp(-160, 0, move) - 140, "ген за инсулин", 30, ORANGE,
           prog(t, 0.5, 0.5) * (1 - prog(t, 2.4, 0.5)), "bold", anchor="ma")
    if t > 3.6:
        for ang in (-22, 22):
            th = math.radians(ang)
            sx, sy = cx + math.cos(th) * (r - 10), cy + math.sin(th) * (r - 10)
            sparkle(c, sx, sy, 30 + 6 * math.sin(t * 9), 1 - prog(t, 5.3, 0.8))
        c.text(cx + r + 120, cy - 40, "ДНК лигаза", 32, YELLOW, prog(t, 3.8, 0.5) * (1 - prog(t, 5.3, 0.8)), "bold")
        c.text(cx + r + 120, cy + 4, "„лепи“ краищата", 28, MUTED, prog(t, 3.8, 0.5) * (1 - prog(t, 5.3, 0.8)), "med")
    a = prog(t, 5.4, 0.6)
    c.text(cx, cy + r + 24, "рекомбинантен плазмид", 34, ORANGE, a, "bold", anchor="ma")
    caption(c, t, "3. Генът за инсулин се вгражда в отвора и се „залепва“ с ензима ДНК лигаза.", 1.2)


def sc_step4(c, t, d):
    heading(c, t, STEP_TITLE, "Стъпка 4 от 5")
    bx, by = 1300, 520
    enter = ease((t - 1.4) / 2.8)
    glow = prog(t, 4.0, 0.6) * (0.6 + 0.4 * math.sin(t * 4))
    bacterium(c, bx, by, 640, 300, prog(t, 0.2, 0.6), t, glow=glow, plasmids=0)
    px, py = lerp(520, bx + 120, enter), lerp(520, by + 20, enter) - math.sin(enter * math.pi) * 120
    pr = lerp(170, 48, enter)
    plasmid(c, px, py, pr, 1.0, w=lerp(12, 7, enter), gene=44, ticks=enter < 0.5)
    c.text(520, 730, "рекомбинантен плазмид", 30, ORANGE, 1 - prog(t, 1.2, 0.5), "bold", anchor="ma")
    c.text(bx, by + 190, "E. coli с човешки ген", 34, GREEN, prog(t, 4.4, 0.6), "bold", anchor="ma")
    caption(c, t, "4. Рекомбинантният плазмид се вкарва в бактерията E. coli (трансформация). Тя вече е ГМО!", 1.0)


def _grid(n, x0, y0, x1, y1):
    cols = int(math.ceil(math.sqrt(n * (x1 - x0) / (y1 - y0))))
    rows = int(math.ceil(n / cols))
    pos = []
    for i in range(n):
        r_, c_ = divmod(i, cols)
        pos.append((x0 + (c_ + 0.5) * (x1 - x0) / cols, y0 + (r_ + 0.5) * (y1 - y0) / rows))
    return pos, (x1 - x0) / cols


def sc_step5(c, t, d):
    heading(c, t, STEP_TITLE, "Стъпка 5 от 5")
    area = (180, 250, 1340, 820)
    t0, per = 0.8, 1.15
    k = int(clamp((t - t0) / per, 0, 5))
    u = clamp((t - t0 - k * per) / 0.7) if k < 5 else 1.0
    if t < t0:
        k, u = 0, 0.0
    n_now = 2 ** k
    pos_now, cell = _grid(n_now, *area)
    if k < 5 and t >= t0:
        pos_next, cell_next = _grid(n_now * 2, *area)
    else:
        pos_next, cell_next = pos_now, cell
    eu = ease(u)
    size_now = min(cell * 0.62, 380)
    size_next = min(cell_next * 0.62, 380)
    for j, (x, y) in enumerate(pos_now):
        if k < 5 and t >= t0:
            for ch in (2 * j, 2 * j + 1):
                nx, ny = pos_next[ch]
                bx, by = lerp(x, nx, eu), lerp(y, ny, eu)
                bw = lerp(size_now, size_next, eu)
                if eu < 0.5:  # удължава се преди делене
                    bw = lerp(size_now, size_now * 1.2, eu * 2)
                    bx, by = lerp(x, x + (-1 if ch % 2 == 0 else 1) * bw * 0.05, eu), y
                bacterium(c, bx, by, bw, bw * 0.45, 1.0, t, glow=0.3, plasmids=0, detail=bw > 120)
        else:
            bacterium(c, x, y, size_now, size_now * 0.45, 1.0, t, glow=0.3, plasmids=0, detail=size_now > 120)
    # брояч
    shown = 2 ** k if (k == 5 or u < 0.5) else 2 ** (k + 1)
    minutes = 20 * (k if (k == 5 or u < 0.5) else k + 1)
    c.rrect(1420, 270, 1780, 640, 28, fill=(6, 14, 30), a=0.6)
    c.text(1600, 300, "време", 28, MUTED, 1, "med", anchor="ma")
    c.text(1600, 340, f"{minutes} мин", 64, WHITE, 1, "xbold", anchor="ma")
    c.text(1600, 450, "бактерии", 28, MUTED, 1, "med", anchor="ma")
    c.text(1600, 490, f"{shown}", 84, GREEN, 1, "xbold", anchor="ma")
    a = prog(t, 6.6, 0.6)
    c.rrect(1420, 660, 1780, 820, 28, fill=ORANGE, a=0.9 * a)
    c.para(1600, 680, "Теоретично за 10 часа: над 1 милиард!", 30, 320, (20, 25, 40), a, "bold", lh=1.25,
           align="center")
    caption(c, t, "5. Бактериите се делят на около 20 минути. Всяка нова клетка носи гена и произвежда човешки инсулин.", 0.8)


def sc_reactor(c, t, d):
    heading(c, t, "Производство в биореактор", "От бактерията до лекарството")
    a = prog(t, 0.4, 0.8)
    # резервоар
    x0, y0, x1, y1 = 230, 270, 690, 740
    c.rrect(x0, y0, x1, y1, 50, fill=(150, 170, 190), a=0.25 * a, outline=(190, 205, 220), width=6)
    lvl = 340
    c.rrect(x0 + 12, lvl, x1 - 12, y1 - 12, 40, fill=(214, 196, 98), a=0.55 * a)
    # мотор и бъркалка
    c.rrect(410, 200, 510, 270, 10, fill=(120, 140, 160), a=a)
    c.line([(460, 270), (460, 660)], (200, 210, 220), 8, a)
    for yy in (480, 630):
        w = 110 * math.cos(t * 5)
        c.line([(460 - w, yy), (460 + w, yy)], (220, 230, 240), 14, a)
    rr = np.random.default_rng(3)
    for i in range(26):
        bx = rr.uniform(x0 + 50, x1 - 50)
        by = (rr.uniform(lvl + 30, y1 - 40) - t * rr.uniform(10, 40) - lvl) % (y1 - 70 - lvl) + lvl + 30
        bx += 20 * math.sin(t * 1.5 + i)
        bacterium(c, bx, by, 56, 24, a, t, detail=False)
    for i in range(18):
        bx = rr.uniform(x0 + 40, x1 - 40) + 6 * math.sin(t * 4 + i)
        by = y1 - 30 - ((t * rr.uniform(60, 140) + rr.uniform(0, 400)) % (y1 - lvl - 40))
        c.circle(bx, by, rr.uniform(5, 10), outline=WHITE, width=2, a=a * 0.6)
    c.text(460, 755, "Биореактор", 32, WHITE, a, "bold", anchor="ma")
    c.text(460, 797, "хиляди литри хранителна среда", 24, MUTED, a, "med", anchor="ma")
    # тръби
    a2 = prog(t, 3.0, 0.8)
    c.line([(690, 660), (900, 660), (900, 560), (980, 560)], (170, 185, 200), 18, a2)
    c.line([(1240, 560), (1450, 560)], (170, 185, 200), 18, a2)
    # пречистване
    c.rrect(980, 440, 1240, 680, 24, fill=(70, 110, 160), a=a2 * 0.8, outline=BLUE, width=5)
    for k in range(5):
        c.line([(1010 + k * 50, 470), (1010 + k * 50, 650)], WHITE, 3, a2 * 0.35)
    c.text(1110, 700, "Пречистване", 32, WHITE, a2, "bold", anchor="ma")
    c.text(1110, 742, "и контрол на качеството", 24, MUTED, a2, "med", anchor="ma")
    # поток от молекули
    if t > 3.6:
        path = [(690, 660), (900, 660), (900, 560), (1450, 560)]
        segl = [math.dist(path[i], path[i + 1]) for i in range(3)]
        L = sum(segl)
        for i in range(12):
            s = ((t - 3.6) * 160 + i * L / 12) % L
            for j in range(3):
                if s <= segl[j]:
                    f = s / segl[j]
                    mx = lerp(path[j][0], path[j + 1][0], f)
                    my = lerp(path[j][1], path[j + 1][1], f)
                    break
                s -= segl[j]
            if 980 < mx < 1240:
                continue
            c.circle(mx, my, 9, fill=ORANGE, a=prog(t, 3.6, 0.5))
    a3 = prog(t, 5.2, 0.8)
    vial(c, 1560, 560, 150, 280, prog(t, 5.6, 5.0), a3)
    c.text(1560, 760, "Готов инсулин", 32, WHITE, a3, "bold", anchor="ma")
    s = "Бактериите се отглеждат в огромни биореактори, после инсулинът се извлича, пречиства и проверява."
    caption(c, t, s, 1.2)


def sc_history(c, t, d):
    heading(c, t, "Кратка история", "Важни години")
    grow = prog(t, 0.6, 1.6)
    y = 500
    c.line([(170, y), (lerp(170, 1750, grow), y)], MUTED, 6, 0.6)
    events = [
        ("1973", "Коен и Бойер създават първата рекомбинантна ДНК.", TEAL),
        ("1978", "Учени от Genentech получават човешки инсулин от E. coli.", BLUE),
        ("1982", "Хумулин (Humulin) — първото лекарство от ГМО, одобрено за употреба.", ORANGE),
        ("Днес", "Рекомбинантният инсулин (от бактерии и дрожди) е стандарт в лечението.", GREEN),
    ]
    for i, (yr, txt, col) in enumerate(events):
        x = 300 + i * 440
        st = 1.4 + i * 2.2
        a = prog(t, st, 0.6)
        pulse = 1 + 0.15 * math.sin(t * 4 + i) if a > 0.9 else 1
        c.circle(x, y, 34 * pulse, fill=col, a=a * 0.25)
        c.circle(x, y, 20, fill=col, a=a)
        dy = lerp(30, 0, ease_out((t - st) / 0.7))
        c.text(x, y - 130 + dy, yr, 64, col, a, "xbold", anchor="ma")
        c.para(x, y + 60 + dy, txt, 30, 360, WHITE, a, "med", lh=1.3, align="center")


def sc_benefits(c, t, d):
    heading(c, t, "Предимства", "Защо ГМО инсулинът е по-добър?")
    items = [
        "Идентичен е с инсулина, който произвежда човешкото тяло",
        "По-рядко предизвиква алергични реакции",
        "Може да се произвежда в почти неограничени количества",
        "Не е нужно да се използват животни",
        "Постоянно качество и по-ниска цена",
    ]
    for i, s in enumerate(items):
        st = 0.8 + i * 1.5
        a = prog(t, st, 0.6)
        dx = lerp(-60, 0, ease_out((t - st) / 0.7))
        y = 240 + i * 132
        c.rrect(150 + dx, y, 1310 + dx, y + 108, 26, fill=(6, 14, 30), a=0.6 * a)
        check_icon(c, 210 + dx, y + 54, 30, a)
        c.text(265 + dx, y + 54, s, 33, WHITE, a, "med", anchor="lm")
    a = prog(t, 0.6, 1.0)
    c.circle(1610, 560, 220, fill=TEAL, a=0.08 * a)
    vial(c, 1610, 560, 170, 320, 0.8, a)
    for k in range(6):
        ang = t * 0.7 + k * math.pi / 3
        c.circle(1610 + math.cos(ang) * 250, 560 + math.sin(ang) * 250, 12, fill=ORANGE, a=a * 0.8)


def shield(c, x, y, s, a):
    pts = [(x, y - s), (x + s * 0.8, y - s * 0.7), (x + s * 0.75, y + s * 0.1), (x, y + s),
           (x - s * 0.75, y + s * 0.1), (x - s * 0.8, y - s * 0.7)]
    c.poly(pts, BLUE, a * 0.85)
    c.line([(x - s * 0.35, y), (x - s * 0.05, y + s * 0.3), (x + s * 0.4, y - s * 0.3)], WHITE, s * 0.12, a)


def sc_safety(c, t, d):
    heading(c, t, "Безопасност и контрол", "А има ли рискове?")
    items = [
        "Бактериите работят само в затворени биореактори и не попадат в природата.",
        "Използват се лабораторни щамове (E. coli K-12), които трудно оцеляват извън лабораторията.",
        "Готовото лекарство е пречистено — в него няма живи бактерии.",
        "Производството се контролира строго от агенции като EMA (ЕС) и FDA (САЩ).",
    ]
    y = 240
    for i, s in enumerate(items):
        st = 0.8 + i * 1.9
        a = prog(t, st, 0.6)
        dx = lerp(-60, 0, ease_out((t - st) / 0.7))
        lines = c.wrap(s, 34, 1000, "med")
        h = len(lines) * 34 * 1.3 + 44
        c.rrect(150 + dx, y, 1260 + dx, y + h, 26, fill=(6, 14, 30), a=0.6 * a)
        c.circle(205 + dx, y + h / 2, 24, fill=BLUE, a=a)
        c.text(205 + dx, y + h / 2, str(i + 1), 28, WHITE, a, "bold", anchor="mm")
        c.para(250 + dx, y + 22, s, 34, 1000, WHITE, a, "med", lh=1.3)
        y += h + 24
    a = prog(t, 0.5, 1.0)
    shield(c, 1550, 540, 200 + 6 * math.sin(t * 2), a)


def sc_conclusion(c, t, d):
    helix(c, -40, W + 40, 900, 60, t * 1.4, a=0.35, step=28, width=6)
    heading(c, t, "Заключение")
    a = prog(t, 0.6, 1.0)
    c.para(960, 250, "Един човешки ген, вграден в бактерия, позволи инсулинът да стигне до "
                     "милиони хора по света.", 54, 1500, WHITE, a, "bold", lh=1.3, align="center")
    a2 = prog(t, 3.0, 1.0)
    c.para(960, 470, "E. coli показва, че генното инженерство има реално приложение в медицината "
                     "и буквално спасява животи.", 40, 1400, ORANGE, a2, "med", lh=1.35, align="center")
    a3 = prog(t, 5.5, 1.0)
    c.para(960, 640, "Същият принцип днес се използва и за растежен хормон, ваксини и ензими за сирене.",
           32, 1400, MUTED, a3, "it", lh=1.35, align="center")


def sc_sources(c, t, d):
    heading(c, t, "Благодаря за вниманието!", "Край")
    a = prog(t, 0.6, 0.8)
    c.text(150, 260, "Използвани източници:", 36, TEAL, a, "bold")
    src = [
        "Goeddel D. V. et al. (1979). Expression in Escherichia coli of chemically synthesized genes "
        "for human insulin. PNAS 76(1): 106–110.",
        "Johnson I. S. (1983). Human insulin from recombinant DNA technology. Science 219: 632–637.",
        "International Diabetes Federation — IDF Diabetes Atlas.",
        "U.S. Food and Drug Administration — одобрение на Humulin (1982).",
    ]
    y = 330
    for i, s in enumerate(src):
        ai = prog(t, 1.0 + i * 0.5, 0.6)
        c.text(160, y, "•", 30, ORANGE, ai, "bold")
        y += c.para(195, y, s, 30, 1500, WHITE, ai, "reg", lh=1.3) + 22
    bacterium(c, 1620, 900, 260, 110, prog(t, 2.5, 0.8), t, glow=0.5 + 0.5 * math.sin(t * 3))


SCENES = [
    (sc_title, 9), (sc_problem, 13), (sc_gmo, 12),
    (sc_step1, 8), (sc_step2, 8), (sc_step3, 8), (sc_step4, 7), (sc_step5, 9),
    (sc_reactor, 13), (sc_history, 13), (sc_benefits, 12), (sc_safety, 12),
    (sc_conclusion, 11), (sc_sources, 10),
]
STARTS = np.cumsum([0] + [d for _, d in SCENES])
TOTAL = float(STARTS[-1])
FADE = 0.45


def render(fi):
    t_glob = fi / FPS
    idx = int(np.searchsorted(STARTS, t_glob, side="right") - 1)
    idx = min(idx, len(SCENES) - 1)
    fn, d = SCENES[idx]
    t = t_glob - STARTS[idx]
    base = background().copy()
    draw_particles(Canvas(base), t_glob)
    frame = base.copy()
    fn(Canvas(frame), t, d)
    a = min(clamp(t / FADE), clamp((d - t) / FADE))
    if idx == 0:
        a = min(clamp((d - t) / FADE), clamp(t / 1.0))
    if a < 1:
        frame = Image.blend(base, frame, a)
    return frame.resize((W, H), Image.LANCZOS).tobytes()


# ---------------------------------------------------------------- музика
def music(path, dur, sr=44100):
    n = int(dur * sr)
    t = np.arange(n) / sr
    out = np.zeros(n)
    midi = lambda m: 440 * 2 ** ((m - 69) / 12)
    chords = [[57, 60, 64], [53, 57, 60], [48, 55, 64], [55, 59, 62]]  # Am F C G
    bar = 4.0
    for b in range(int(dur / bar) + 1):
        ch = chords[b % 4]
        s0 = int(b * bar * sr)
        s1 = min(n, int((b + 1) * bar * sr + sr))
        if s0 >= n:
            break
        tt = t[s0:s1] - b * bar
        env = np.minimum(tt / 1.2, 1) * np.exp(-np.maximum(tt - bar, 0) * 3)
        for m in ch:
            f = midi(m)
            out[s0:s1] += env * 0.10 * (np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(2 * np.pi * f * 2.003 * tt))
        bass = midi(ch[0] - 12)
        out[s0:s1] += env * 0.10 * np.sin(2 * np.pi * bass * tt)
        # тихо арпеджио
        for k in range(8):
            m = ch[k % 3] + 12 * (1 + (k // 3) % 2)
            a0 = int((b * bar + k * 0.5) * sr)
            a1 = min(n, a0 + int(1.2 * sr))
            if a0 >= n:
                break
            ta = t[a0:a1] - (b * bar + k * 0.5)
            out[a0:a1] += 0.05 * np.exp(-ta * 3.5) * np.sin(2 * np.pi * midi(m) * ta)
    # просто ехо
    dl = int(0.33 * sr)
    echo = np.zeros(n)
    echo[dl:] = out[:-dl] * 0.35
    out = out + echo
    fade = np.minimum(1, np.minimum(t / 2.0, (dur - t) / 3.0))
    out = out * np.clip(fade, 0, 1)
    out = out / np.max(np.abs(out)) * 0.35
    st = np.stack([out, np.roll(out, int(0.012 * sr))], axis=1)
    data = (st * 32767).astype(np.int16)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(data.tobytes())


def main():
    preview = "--preview" in sys.argv
    if preview:
        outdir = sys.argv[sys.argv.index("--preview") + 1]
        os.makedirs(outdir, exist_ok=True)
        for i, st in enumerate(STARTS[:-1]):
            d = SCENES[i][1]
            for frac in (0.5, 0.95):
                fi = int((st + d * frac - 0.5) * FPS)
                Image.frombytes("RGB", (W, H), render(fi)).save(os.path.join(outdir, f"s{i:02d}_{frac}.jpg"),
                                                                 quality=85)
        return
    nframes = int(TOTAL * FPS)
    wav = OUT.replace(".mp4", "_music.wav")
    music(wav, TOTAL)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-i", wav, "-c:v", "libx264", "-preset", "medium", "-crf", "20",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", OUT]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    with Pool() as pool:
        for i, buf in enumerate(pool.imap(render, range(nframes), chunksize=6)):
            proc.stdin.write(buf)
            if i % (FPS * 10) == 0:
                print(f"{i / FPS:5.0f}s / {TOTAL:.0f}s", flush=True)
    proc.stdin.close()
    proc.wait()
    os.remove(wav)
    print("Готово:", OUT)


if __name__ == "__main__":
    main()
