"""Data in Motion - animation + voiceover engine.

An episode is a list of Scene objects. Each Scene has narration beats
(one string each) and a draw(c, x) function. `x` is a Ctx giving the
scene-local time, beat start times and easing helpers, so animations can
be keyed to the moment each sentence starts.

    python3 build.py episodes/ep01.py      -> out/ep01/ep01.mp4 (+ .srt, thumb)
"""
import math, os, re, json, subprocess, shutil, hashlib, random
import numpy as np
import skia

W, H, FPS = 1920, 1080, 30
HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------- palette
def C(h, a=1.0):
    h = h.lstrip('#')
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return skia.Color(r, g, b, int(max(0, min(1, a)) * 255))

BG0, BG1 = '#060914', '#0F1733'
INK, DIM, FAINT = '#EEF2FF', '#9AA6C8', '#56618A'
ORANGE, CYAN, VIOLET, GREEN, PINK, YELLOW, BLUE = (
    '#FF8A3D', '#3DD6FF', '#8B7BFF', '#3DFFA8', '#FF5C9A', '#FFD23D', '#4D8BFF')
PART = ['#FF8A3D', '#3DD6FF', '#8B7BFF', '#3DFFA8', '#FF5C9A', '#FFD23D', '#4D8BFF', '#FF6B6B',
        '#5CE1E6', '#C77DFF', '#9BE15D', '#FFA94D']
CARD = '#121B3A'
CARD_HI = '#1A2550'

# ---------------------------------------------------------------- fonts
_F = '/usr/share/fonts/opentype/inter/'
_TF = {
    'regular': _F + 'Inter-Regular.otf', 'medium': _F + 'Inter-Medium.otf',
    'semibold': _F + 'Inter-SemiBold.otf', 'bold': _F + 'Inter-Bold.otf',
    'black': _F + 'InterDisplay-Black.otf', 'display': _F + 'InterDisplay-ExtraBold.otf',
    'mono': '/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf',
    'monob': '/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf',
}
_tfc, _fc = {}, {}
def font(weight='semibold', size=40):
    k = (weight, size)
    if k not in _fc:
        if weight not in _tfc:
            path = _TF[weight]
            if not os.path.exists(path):   # fallback if Inter is missing
                path = _TF['monob'] if weight in ('bold', 'black', 'display') else _TF['mono'] if weight == 'mono' else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
            _tfc[weight] = skia.Typeface.MakeFromFile(path)
        f = skia.Font(_tfc[weight], size)
        f.setEdging(skia.Font.Edging.kSubpixelAntiAlias)
        f.setSubpixel(True)
        _fc[k] = f
    return _fc[k]

# ---------------------------------------------------------------- easing
def clamp(v, a=0.0, b=1.0): return a if v < a else b if v > b else v
def lerp(a, b, t): return a + (b - a) * t
def ease_out(t): t = clamp(t); return 1 - (1 - t) ** 3
def ease_in_out(t): t = clamp(t); return 4 * t ** 3 if t < .5 else 1 - (-2 * t + 2) ** 3 / 2
def ease_back(t):
    t = clamp(t); c1 = 1.70158; c3 = c1 + 1
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2
def mix(c1, c2, t):
    a, b = C(c1), C(c2)
    f = lambda s, e: int(lerp(s, e, clamp(t)))
    return '#%02X%02X%02X' % (f(skia.ColorGetR(a), skia.ColorGetR(b)), f(skia.ColorGetG(a), skia.ColorGetG(b)),
                             f(skia.ColorGetB(a), skia.ColorGetB(b)))

class Ctx:
    """Scene-local timing. x.t = seconds into scene; x.b[i] = start of beat i."""
    def __init__(self, t, b, e, D, gt):
        self.t, self.b, self.e, self.D, self.gt = t, b, e, D, gt
    def p(self, i=None, dur=0.8, delay=0.0, ease=ease_out, at=None):
        start = (self.b[i] if i is not None else 0) + delay if at is None else at
        return ease((self.t - start) / dur) if dur > 0 else float(self.t >= start)
    def lin(self, i=None, dur=1.0, delay=0.0):
        return self.p(i, dur, delay, ease=clamp)
    def since(self, i, delay=0.0): return self.t - self.b[i] - delay
    def out(self, dur=0.45):  # 1 -> 0 at the end of the scene
        return 1 - ease_in_out((self.t - (self.D - dur)) / dur)

# ---------------------------------------------------------------- primitives
def paint(color, a=1.0, stroke=0, blur=0, aa=True):
    p = skia.Paint(AntiAlias=aa, Color=C(color, a))
    if stroke:
        p.setStyle(skia.Paint.kStroke_Style); p.setStrokeWidth(stroke)
        p.setStrokeCap(skia.Paint.kRound_Cap); p.setStrokeJoin(skia.Paint.kRound_Join)
    if blur:
        p.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, blur))
    return p

def text(c, s, x, y, size=40, color=INK, weight='semibold', align='left', a=1.0, glow=0, spacing=0):
    if a <= 0.003: return 0
    f = font(weight, size)
    w = f.measureText(s) + spacing * max(0, len(s) - 1)
    if align == 'center': x -= w / 2
    elif align == 'right': x -= w
    if spacing:
        cx = x
        for ch in s:
            if glow: c.drawString(ch, cx, y, f, paint(color, a * .55, blur=glow))
            c.drawString(ch, cx, y, f, paint(color, a)); cx += f.measureText(ch) + spacing
        return w
    if glow: c.drawString(s, x, y, f, paint(color, a * .55, blur=glow))
    c.drawString(s, x, y, f, paint(color, a))
    return w

def tw(s, size=40, weight='semibold'): return font(weight, size).measureText(s)

def rrect(c, x, y, w, h, r=18, fill=CARD, a=1.0, stroke=None, sw=2, glow=None, glow_a=.5, grad=None):
    if a <= 0.003: return
    R = skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x, y, w, h), r, r)
    if glow:
        c.drawRRect(R, paint(glow, a * glow_a, blur=22))
    if fill:
        p = paint(fill, a)
        if grad:
            p.setShader(skia.GradientShader.MakeLinear(
                [skia.Point(x, y), skia.Point(x, y + h)], [C(grad[0], a), C(grad[1], a)]))
        c.drawRRect(R, p)
    if stroke:
        c.drawRRect(R, paint(stroke, a, stroke=sw))

def card(c, x, y, w, h, title=None, color=CYAN, a=1.0, r=22, glow=True, sub=None, tsize=30):
    """Glassy panel with a colored top edge and optional title."""
    if a <= 0.003: return
    rrect(c, x, y, w, h, r, fill=CARD, a=a * .92, glow=color if glow else None, glow_a=.28,
          grad=(CARD_HI, CARD))
    rrect(c, x, y, w, h, r, fill=None, a=a * .9, stroke=color, sw=2)
    if title:
        text(c, title, x + w / 2, y + 22 + tsize, tsize, INK, 'bold', 'center', a)
    if sub:
        text(c, sub, x + w / 2, y + 22 + tsize + tsize * .95, tsize * .62, DIM, 'medium', 'center', a)

def block(c, x, y, w, h, color, a=1.0, label=None, r=10, lsize=22, glow=True):
    """A data chunk (partition)."""
    if a <= 0.003: return
    if glow: c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x, y, w, h), r, r), paint(color, a * .45, blur=14))
    rrect(c, x, y, w, h, r, fill=color, a=a, grad=(mix(color, '#FFFFFF', .22), mix(color, '#000000', .18)))
    # glossy highlight
    rrect(c, x + 4, y + 4, w - 8, max(2, h * .28), max(2, r - 4), fill='#FFFFFF', a=a * .16)
    if label:
        text(c, label, x + w / 2, y + h / 2 + lsize * .36, lsize, '#0A0F22', 'bold', 'center', a)

def line(c, x1, y1, x2, y2, color=DIM, a=1.0, w=3, glow=0, dash=None, phase=0):
    if a <= 0.003: return
    p = paint(color, a, stroke=w)
    if dash: p.setPathEffect(skia.DashPathEffect.Make(dash, phase))
    if glow:
        g = paint(color, a * .5, stroke=w + 4, blur=glow)
        if dash: g.setPathEffect(skia.DashPathEffect.Make(dash, phase))
        c.drawLine(x1, y1, x2, y2, g)
    c.drawLine(x1, y1, x2, y2, p)

def arrow(c, x1, y1, x2, y2, color=CYAN, a=1.0, prog=1.0, w=4, head=16, flow=None, glow=8):
    """Arrow drawn from (x1,y1) to (x2,y2) up to `prog`. flow=time -> moving dots."""
    if a <= 0.003 or prog <= 0.001: return
    ex, ey = lerp(x1, x2, prog), lerp(y1, y2, prog)
    ang = math.atan2(y2 - y1, x2 - x1)
    bx, by = ex - math.cos(ang) * head * .8, ey - math.sin(ang) * head * .8
    line(c, x1, y1, bx, by, color, a * .85, w, glow=glow)
    path = skia.Path()
    path.moveTo(ex, ey)
    path.lineTo(ex - head * math.cos(ang - .45), ey - head * math.sin(ang - .45))
    path.lineTo(ex - head * math.cos(ang + .45), ey - head * math.sin(ang + .45))
    path.close()
    c.drawPath(path, paint(color, a * .6, blur=6)); c.drawPath(path, paint(color, a))
    if flow is not None and prog >= .999:
        L = math.hypot(x2 - x1, y2 - y1)
        n = max(1, int(L / 70))
        for k in range(n):
            f = ((flow * 0.9 + k / n) % 1.0)
            px, py = lerp(x1, bx, f), lerp(y1, by, f)
            c.drawCircle(px, py, 7, paint('#FFFFFF', a * .35, blur=6))
            c.drawCircle(px, py, 3.5, paint('#FFFFFF', a * .9))

def curve_arrow(c, p0, p1, p2, color=CYAN, a=1.0, prog=1.0, w=4, head=16):
    """Quadratic bezier arrow p0 -> p2 with control p1."""
    if a <= 0.003 or prog <= 0.001: return
    pts = []
    N = 40
    for k in range(int(N * prog) + 1):
        tt = k / N
        x = (1 - tt) ** 2 * p0[0] + 2 * (1 - tt) * tt * p1[0] + tt ** 2 * p2[0]
        y = (1 - tt) ** 2 * p0[1] + 2 * (1 - tt) * tt * p1[1] + tt ** 2 * p2[1]
        pts.append((x, y))
    if len(pts) < 2: return
    path = skia.Path(); path.moveTo(*pts[0])
    for q in pts[1:]: path.lineTo(*q)
    c.drawPath(path, paint(color, a * .5, stroke=w + 4, blur=8))
    c.drawPath(path, paint(color, a * .9, stroke=w))
    (xa, ya), (xb, yb) = pts[-2], pts[-1]
    ang = math.atan2(yb - ya, xb - xa)
    hp = skia.Path(); hp.moveTo(xb + math.cos(ang) * 4, yb + math.sin(ang) * 4)
    hp.lineTo(xb - head * math.cos(ang - .45), yb - head * math.sin(ang - .45))
    hp.lineTo(xb - head * math.cos(ang + .45), yb - head * math.sin(ang + .45)); hp.close()
    c.drawPath(hp, paint(color, a))

def pill(c, s, x, y, size=24, color=CYAN, a=1.0, align='center', fill=None, txt=None):
    if a <= 0.003: return
    w = tw(s, size, 'bold') + size * 1.3; h = size * 1.75
    if align == 'center': x -= w / 2
    rrect(c, x, y, w, h, h / 2, fill=fill or mix(color, BG0, .78), a=a, stroke=color, sw=2)
    text(c, s, x + w / 2, y + h / 2 + size * .36, size, txt or color, 'bold', 'center', a)
    return w

# ---------------------------------------------------------------- icons
def server(c, x, y, w=150, h=170, color=CYAN, a=1.0, t=0, busy=0.0, label=None):
    """A rack server icon (3 units with blinking LEDs)."""
    if a <= 0.003: return
    rrect(c, x, y, w, h, 16, fill='#0E1530', a=a, stroke=color, sw=2, glow=color, glow_a=.25)
    uh = (h - 40) / 3
    for i in range(3):
        yy = y + 14 + i * (uh + 6)
        rrect(c, x + 12, yy, w - 24, uh, 8, fill='#18224A', a=a)
        for j in range(3):
            on = busy > 0 and (math.sin(t * 9 + i * 2.1 + j * 1.3) > .2)
            col = GREEN if on else '#33406E'
            c.drawCircle(x + 30 + j * 18, yy + uh / 2, 4.5, paint(col, a))
            if on: c.drawCircle(x + 30 + j * 18, yy + uh / 2, 9, paint(GREEN, a * .5 * busy, blur=5))
        rrect(c, x + w - 64, yy + uh / 2 - 3, 40, 6, 3, fill='#33406E', a=a)
    if label: text(c, label, x + w / 2, y + h + 34, 24, DIM, 'semibold', 'center', a)

def laptop(c, x, y, s=1.0, a=1.0, color=CYAN):
    if a <= 0.003: return
    w, h = 300 * s, 190 * s
    rrect(c, x, y, w, h, 16 * s, fill='#0E1530', a=a, stroke=color, sw=2.5, glow=color, glow_a=.22)
    rrect(c, x + 14 * s, y + 14 * s, w - 28 * s, h - 28 * s, 8 * s, fill='#0A1A33', a=a)
    base = skia.Path()
    base.moveTo(x - 40 * s, y + h + 26 * s); base.lineTo(x + w + 40 * s, y + h + 26 * s)
    base.lineTo(x + w + 6 * s, y + h + 4 * s); base.lineTo(x - 6 * s, y + h + 4 * s); base.close()
    c.drawPath(base, paint('#22305E', a)); c.drawPath(base, paint(color, a, stroke=2))

def file_icon(c, x, y, w=170, h=210, color=ORANGE, a=1.0, label='', sub=''):
    if a <= 0.003: return
    fold = w * .26
    p = skia.Path()
    p.moveTo(x, y + 14); p.quadTo(x, y, x + 14, y); p.lineTo(x + w - fold, y); p.lineTo(x + w, y + fold)
    p.lineTo(x + w, y + h - 14); p.quadTo(x + w, y + h, x + w - 14, y + h); p.lineTo(x + 14, y + h)
    p.quadTo(x, y + h, x, y + h - 14); p.close()
    c.drawPath(p, paint(color, a * .45, blur=18))
    pp = paint(color, a); pp.setShader(skia.GradientShader.MakeLinear(
        [skia.Point(x, y), skia.Point(x, y + h)], [C(mix(color, '#FFFFFF', .15), a), C(mix(color, '#000000', .25), a)]))
    c.drawPath(p, pp)
    f = skia.Path(); f.moveTo(x + w - fold, y); f.lineTo(x + w - fold, y + fold); f.lineTo(x + w, y + fold); f.close()
    c.drawPath(f, paint('#FFFFFF', a * .35))
    for i in range(4):
        rrect(c, x + 22, y + fold + 22 + i * 24, (w - 44) * (1 if i < 3 else .6), 9, 4, fill='#000000', a=a * .18)
    if label: text(c, label, x + w / 2, y + h + 44, 32, INK, 'bold', 'center', a)
    if sub: text(c, sub, x + w / 2, y + h + 82, 26, DIM, 'medium', 'center', a)

def core(c, x, y, s=64, color=CYAN, a=1.0, fillc=None, fill_a=0.0, label=None):
    """CPU core chip; fillc = color of partition currently being processed."""
    if a <= 0.003: return
    for k in range(4):  # pins
        off = s * (.2 + k * .2)
        for (px, py, pw, ph) in [(x + off - 2, y - 8, 4, 8), (x + off - 2, y + s, 4, 8),
                                 (x - 8, y + off - 2, 8, 4), (x + s, y + off - 2, 8, 4)]:
            c.drawRect(skia.Rect.MakeXYWH(px, py, pw, ph), paint(FAINT, a))
    rrect(c, x, y, s, s, 10, fill='#1A2550', a=a, stroke=color, sw=2)
    if fillc and fill_a > 0:
        rrect(c, x + 8, y + 8, s - 16, s - 16, 7, fill=fillc, a=a * fill_a, glow=fillc, glow_a=.6)
    if label: text(c, label, x + s / 2, y + s / 2 + 8, 22, INK if not fillc else '#0A0F22', 'bold', 'center', a)

def spark_star(c, cx, cy, r, color=ORANGE, a=1.0, rot=0.0):
    """Original 6-point spark mark (channel logo)."""
    if a <= 0.003: return
    p = skia.Path()
    n = 6
    for k in range(n * 2):
        ang = rot + k * math.pi / n - math.pi / 2
        rr = r if k % 2 == 0 else r * .36
        px, py = cx + math.cos(ang) * rr, cy + math.sin(ang) * rr
        (p.moveTo if k == 0 else p.lineTo)(px, py)
    p.close()
    c.drawPath(p, paint(color, a * .7, blur=r * .35))
    pp = paint(color, a); pp.setShader(skia.GradientShader.MakeRadial(
        skia.Point(cx, cy), r, [C('#FFF3C4', a), C(color, a), C(PINK, a)], [0, .45, 1]))
    c.drawPath(p, pp)

# ---------------------------------------------------------------- code panel
_KW = {'from', 'import', 'def', 'return', 'for', 'in', 'if', 'else', 'lambda', 'as', 'with', 'print', 'True', 'False', 'None', 'and', 'or', 'not'}
def _tok(s):
    out = []
    for m in re.finditer(r'(#.*$)|("[^"]*"|\'[^\']*\')|(\b\d+(?:\.\d+)?\b)|([A-Za-z_][A-Za-z0-9_]*)|(\s+)|(.)', s):
        g = m.group(0)
        if m.group(1): out.append((g, FAINT))
        elif m.group(2): out.append((g, GREEN))
        elif m.group(3): out.append((g, YELLOW))
        elif m.group(4):
            nxt = s[m.end():m.end() + 1]
            if g in _KW: out.append((g, PINK))
            elif nxt == '(': out.append((g, CYAN))
            elif g[0].isupper(): out.append((g, ORANGE))
            else: out.append((g, INK))
        else: out.append((g, DIM))
    return out

def code_panel(c, x, y, w, lines, a=1.0, chars=None, size=30, hl=None, hl_a=1.0, title='main.py', lh=None):
    """Editor window. chars = number of characters typed so far (None = all). hl = set of highlighted line idxs."""
    if a <= 0.003: return
    lh = lh or size * 1.65
    h = 80 + len(lines) * lh + 20
    rrect(c, x, y, w, h, 20, fill='#0B1128', a=a * .96, stroke='#2A3666', sw=2, glow=VIOLET, glow_a=.18)
    for i, col in enumerate(['#FF5F57', '#FEBC2E', '#28C840']):
        c.drawCircle(x + 30 + i * 26, y + 30, 8, paint(col, a))
    text(c, title, x + w / 2, y + 38, 22, FAINT, 'medium', 'center', a)
    f = font('mono', size)
    remaining = 10 ** 9 if chars is None else int(chars)
    total = sum(len(l) + 1 for l in lines)
    for i, ln in enumerate(lines):
        yy = y + 80 + i * lh + size
        if hl and i in hl:
            rrect(c, x + 12, yy - size * 1.05, w - 24, lh, 8, fill=YELLOW, a=a * .13 * hl_a)
            rrect(c, x + 12, yy - size * 1.05, 5, lh, 2, fill=YELLOW, a=a * hl_a)
        if remaining <= 0 and chars is not None: break
        text(c, str(i + 1), x + 52, yy, size * .8, '#3A4677', 'mono', 'right', a)
        cx = x + 76
        line_start_rem = remaining
        for tok, col in _tok(ln):
            if remaining <= 0: break
            piece = tok[:remaining]; remaining -= len(piece)
            dim = 1.0 if not hl or i in hl else lerp(1, .4, hl_a)
            c.drawString(piece, cx, yy, f, paint(col, a * dim))
            cx += f.measureText(piece)
        typing_here = chars is not None and chars < total and line_start_rem <= len(ln) + 1
        remaining -= 1  # newline
        if typing_here:
            rrect(c, cx + 3, yy - size * .85, 3, size * 1.05, 1, fill=CYAN, a=a)
    return h

# ---------------------------------------------------------------- background + chrome
_rng = random.Random(7)
_STARS = [(_rng.random() * W, _rng.random() * H, _rng.random() * 1.6 + .4, _rng.random() * 6.28) for _ in range(140)]
_ORBS = [(.18, .25, VIOLET, 520, .0), (.82, .72, CYAN, 560, 2.0), (.65, .15, ORANGE, 380, 4.0)]

def background(c, gt):
    p = skia.Paint()
    p.setShader(skia.GradientShader.MakeRadial(skia.Point(W * .5, H * .42), W * .75, [C(BG1), C(BG0)]))
    c.drawRect(skia.Rect.MakeWH(W, H), p)
    for (ox, oy, col, r, ph) in _ORBS:
        x = W * ox + math.sin(gt * .11 + ph) * 60; y = H * oy + math.cos(gt * .09 + ph) * 40
        c.drawCircle(x, y, r, paint(col, .07, blur=r * .45))
    # perspective-free dot grid
    g = paint('#2A3566', .35)
    for gx in range(40, W, 60):
        for gy in range(40, H, 60):
            c.drawCircle(gx, gy, 1.4, g)
    for (sx, sy, sr, ph) in _STARS:
        tw_ = .25 + .25 * math.sin(gt * 1.3 + ph)
        c.drawCircle(sx, (sy - gt * 6 * sr) % H, sr, paint('#BFD0FF', tw_))

def chrome(c, gt, ep_label, topic, a=1.0):
    """Persistent channel bug + episode tag."""
    spark_star(c, 62, 58, 22, rot=gt * .4, a=a)
    text(c, 'DATA IN MOTION', 96, 68, 24, INK, 'bold', a=a * .9, spacing=2.5)
    pill(c, ep_label, W - 60 - tw(ep_label, 22, 'bold') - 30, 36, 22, ORANGE, a=a * .95, align='left')
    if topic:
        text(c, topic, W - 60 - tw(ep_label, 22, 'bold') - 60, 68, 22, DIM, 'medium', 'right', a * .9)

def caption(c, s, a=1.0):
    if not s or a <= 0.003: return
    size = 40
    f = font('semibold', size)
    w = f.measureText(s)
    x, y = W / 2 - w / 2, H - 70
    rrect(c, x - 26, y - size - 14, w + 52, size + 36, 16, fill='#050813', a=a * .78)
    text(c, s, W / 2, y, size, INK, 'semibold', 'center', a)

def progress_bar(c, frac):
    c.drawRect(skia.Rect.MakeXYWH(0, H - 6, W, 6), paint('#1A2347'))
    p = paint(ORANGE); p.setShader(skia.GradientShader.MakeLinear(
        [skia.Point(0, 0), skia.Point(W, 0)], [C(ORANGE), C(PINK), C(VIOLET)]))
    c.drawRect(skia.Rect.MakeXYWH(0, H - 6, W * frac, 6), p)

# ---------------------------------------------------------------- scene model
class Scene:
    def __init__(self, name, beats, draw, gap=0.35, head=0.5, tail=0.9, chrome=True, captions=True):
        self.name, self.beats, self.draw = name, beats, draw
        self.gap, self.head, self.tail = gap, head, tail
        self.chrome, self.captions = chrome, captions

def caption_chunks(textline, max_chars=56):
    """Split a sentence into balanced caption lines, preferring sentence/comma breaks."""
    out = []
    for sent in re.split(r'(?<=[.?!])\s+', textline.strip()):
        words = sent.split()
        n = max(1, math.ceil(len(sent) / max_chars))
        target = len(sent) / n
        cur = ''
        for wd in words:
            cand = (cur + ' ' + wd).strip()
            if cur and (len(cand) > max_chars or (len(cur) >= target * .92 and len(out) < 99 and
                                                   (cur.endswith(',') or len(cand) > target * 1.12))):
                out.append(cur); cur = wd
            else:
                cur = cand
        if cur:
            if out and len(cur) < 12 and len(out[-1]) + len(cur) + 1 <= max_chars + 8 and not out[-1].endswith(('.', '?', '!')):
                out[-1] += ' ' + cur
            else:
                out.append(cur)
    return out


# ---------------------------------------------------------------- real Spark UI screenshots (Series 2)
_imgs = {}
def load_img(path):
    if path not in _imgs:
        _imgs[path] = skia.Image.MakeFromEncoded(skia.Data.MakeFromFileName(path))
        if _imgs[path] is None: raise SystemExit(f'cannot read image {path}')
    return _imgs[path]

class Shot:
    """Maps screenshot pixels to canvas pixels after ui_shot() places a crop of it."""
    def __init__(self, x, y, k, sx, sy, w=W, h=H):
        self.x, self.y, self.k, self.sx, self.sy, self.w, self.h = x, y, k, sx, sy, w, h
    def pt(self, px, py): return self.x + (px - self.sx) * self.k, self.y + 52 + (py - self.sy) * self.k
    def rect(self, px, py, pw, ph):
        """Screenshot box -> canvas box, clipped to the visible part of the screenshot."""
        x, y = self.pt(px, py); x2, y2 = x + pw * self.k, y + ph * self.k
        vx, vy, vx2, vy2 = self.x + 6, self.y + 56, self.x + self.w - 6, self.y + 52 + self.h - 4
        x, y, x2, y2 = max(x, vx), max(y, vy), min(x2, vx2), min(y2, vy2)
        return (x, y, max(0, x2 - x), max(0, y2 - y))

def ui_shot(c, path, x, y, w, crop=None, a=1.0, url='localhost:4040', zoom_from=None, zoom=0.0):
    """Draw a (cropped) real Spark UI screenshot in a browser frame, w canvas px wide.
    crop = (sx, sy, sw, sh) in screenshot pixels. zoom_from + zoom (0..1) animates from one crop to another.
    Returns a Shot for placing highlights with screenshot coordinates (from capture boxes.json)."""
    img = load_img(path)
    sx, sy, sw, sh = crop or (0, 0, img.width(), img.height())
    if zoom_from and zoom < 1:
        k_ = ease_in_out(zoom); fx, fy, fw, fh = zoom_from
        sx, sy, sw, sh = lerp(fx, sx, k_), lerp(fy, sy, k_), lerp(fw, sw, k_), lerp(fh, sh, k_)
    k = w / sw; h = sh * k
    if a <= 0.003: return Shot(x, y, k, sx, sy, w, h)
    rrect(c, x, y, w, h + 52, 18, fill='#0B1128', a=a, stroke='#2A3666', sw=2, glow=CYAN, glow_a=.15)
    for i, col in enumerate(['#FF5F57', '#FEBC2E', '#28C840']):
        c.drawCircle(x + 26 + i * 22, y + 26, 7, paint(col, a))
    rrect(c, x + 110, y + 12, min(520, w - 130), 28, 14, fill='#18224A', a=a)
    text(c, url, x + 128, y + 32, 17, DIM, 'medium', 'left', a)
    c.save()
    c.clipRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x + 2, y + 52, w - 4, h - 2), 14, 14), True)
    p = skia.Paint(AntiAlias=True); p.setAlphaf(a)
    c.drawImageRect(img, skia.Rect.MakeXYWH(sx, sy, sw, sh), skia.Rect.MakeXYWH(x, y + 52, w, h),
                    skia.SamplingOptions(skia.CubicResampler.Mitchell()), p)
    c.restore()
    return Shot(x, y, k, sx, sy, w, h)

def spotlight(c, rect, a=1.0, color=YELLOW, dim=.55, pad=8, t=0.0):
    """Dim everything except rect=(x,y,w,h) and draw a pulsing outline around it."""
    if a <= 0.003: return
    x, y, w, h = rect; x -= pad; y -= pad; w += 2 * pad; h += 2 * pad
    path = skia.Path(); path.addRect(skia.Rect.MakeWH(W, H))
    path.addRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x, y, w, h), 10, 10))
    path.setFillType(skia.PathFillType.kEvenOdd)
    c.drawPath(path, paint('#03050D', a * dim))
    pulse = .75 + .25 * math.sin(t * 5)
    rrect(c, x, y, w, h, 10, fill=None, a=a * pulse, stroke=color, sw=4, glow=color, glow_a=.5)

def callout(c, s, x, y, target=None, color=YELLOW, a=1.0, size=30, prog=1.0):
    """Label pill at (x, y) (centre) with an optional curved arrow to target=(tx, ty)."""
    if a <= 0.003: return
    if target:
        tx, ty = target
        curve_arrow(c, (x, y + size), ((x + tx) / 2, min(y, ty) - 60 if ty < y else max(y, ty) + 60), (tx, ty), color, a, prog)
    pill(c, s, x, y - size * .9, size, color, a)
