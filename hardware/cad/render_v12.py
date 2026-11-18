# Agent Dot v12 drawings (one-piece body, SuperMini + TP4056, one pixel)
#   cd hardware/cad && freecadcmd -c "exec(open('render_v12.py').read())"
import numpy as np, math, os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
EXPORT_DIR = None
exec(open('agent_dot.FCMacro').read())
import MeshPart

OUT = 'out/views'
FLAT = globals().get('LAYOUT') == 'floor'
if FLAT:
    P['LED_LAYOUT'] = 'floor'; OUT = 'out/views_5mm_flat'
if not globals().get('VOVR'):
    exec(open('v12.py').read())
if globals().get('VOVR'):
    P.update(VOVR); OUT = 'out/views_' + VTAG; FLAT = P.get('LED_LAYOUT') == 'floor'
os.makedirs(OUT, exist_ok=True)
L, parts, pads, comps = build(P)
p = P

PAL = {
    'LED_End_Plug': '#3a3a40', 'Body': '#4f4f58', 'Clip_Bridge': '#4a4a52', 'LED_Housing': '#3a3a40', 'Diffuser_Strip': '#e9ddff',
    'Enclosure_Base': '#5a5a63', 'Enclosure_Cover': '#6a6a73', 'Thickness_Insert': '#8a8a94',
    'Pad': '#b9b2c9', 'XIAO_PCB': '#2f7d4f', 'XIAO_USB_C': '#c9c9cf', 'XIAO_ESP32C3_chip': '#222',
    'Battery_LiPo': '#d8b84a', 'Switch': '#333', 'Switch_actuator': '#eee', 'LED_PCB': '#1f6b46',
    'LEDs': '#b07cff', 'Screw': '#a9a9b0', 'Lid': '#9fa3aa', 'Screen': '#15151a', 'Cam': '#000',
}
ACCENT = '#6b2fd6'


def pal(n):
    for k, v in PAL.items():
        if n.startswith(k):
            return v
    return '#888'


def hex2rgb(h):
    h = h.lstrip('#')
    if len(h) == 3:
        h = ''.join(c * 2 for c in h)
    return np.array([int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)])


def tess(shape, dev=0.04):
    m = MeshPart.meshFromShape(Shape=shape, LinearDeflection=dev, AngularDeflection=0.25, Relative=False)
    pts = np.array([[v.x, v.y, v.z] for v in m.Points])
    f = np.array([list(t.PointIndices) for t in m.Facets])
    return pts[f]


def norm(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def make_view(d, up=(0, 0, 1)):
    d = norm(d)
    up = np.asarray(up, float)
    r = np.cross(-d, up)
    if np.linalg.norm(r) < 1e-6:
        r = np.array([1.0, 0, 0])
    r = norm(r)
    u = norm(np.cross(r, -d))
    return r, u, d


def raster(items, view, ppm=14, bounds=None, margin=4, ss=2, light=None):
    """items: list of (tris(N,3,3), rgb, id). returns rgb image + extent (mm)"""
    r, u, d = view
    allp = []
    T = []
    for tris, rgb, oid in items:
        P2 = np.stack([tris @ r, tris @ u, tris @ d], axis=-1)       # (N,3,3)
        n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
        ln = np.linalg.norm(n, axis=1); ok = ln > 1e-12
        n = n[ok] / ln[ok, None]; P2 = P2[ok]
        front = n @ d > 1e-6
        T.append((P2[front], n[front], rgb, oid))
        allp.append(P2[front].reshape(-1, 3))
    allp = np.concatenate(allp)
    if bounds is None:
        x0, x1 = allp[:, 0].min() - margin, allp[:, 0].max() + margin
        y0, y1 = allp[:, 1].min() - margin, allp[:, 1].max() + margin
    else:
        x0, x1, y0, y1 = bounds
    s = ppm * ss
    W, H = int((x1 - x0) * s) + 1, int((y1 - y0) * s) + 1
    zb = np.full((H, W), -1e9); cb = np.ones((H, W, 3)); ib = np.full((H, W), -1); nb = np.zeros((H, W, 3))
    if light is None:
        light = norm(-0.45 * r + 0.55 * u + 0.75 * d)
    fill = norm(0.6 * r - 0.2 * u + 0.5 * d)
    for P2, n, rgb, oid in T:
        shade = 0.38 + 0.52 * np.clip(n @ light, 0, 1) + 0.18 * np.clip(n @ fill, 0, 1)
        X = (P2[:, :, 0] - x0) * s; Y = (y1 - P2[:, :, 1]) * s; Z = P2[:, :, 2]
        for k in range(len(P2)):
            xs, ys, zs = X[k], Y[k], Z[k]
            ix0 = max(int(math.floor(xs.min())), 0); ix1 = min(int(math.ceil(xs.max())), W - 1)
            iy0 = max(int(math.floor(ys.min())), 0); iy1 = min(int(math.ceil(ys.max())), H - 1)
            if ix1 < ix0 or iy1 < iy0:
                continue
            gx, gy = np.meshgrid(np.arange(ix0, ix1 + 1) + 0.5, np.arange(iy0, iy1 + 1) + 0.5)
            (ax_, bx_, cx_), (ay_, by_, cy_) = xs, ys
            den = (by_ - cy_) * (ax_ - cx_) + (cx_ - bx_) * (ay_ - cy_)
            if abs(den) < 1e-12:
                continue
            w0 = ((by_ - cy_) * (gx - cx_) + (cx_ - bx_) * (gy - cy_)) / den
            w1 = ((cy_ - ay_) * (gx - cx_) + (ax_ - cx_) * (gy - cy_)) / den
            w2 = 1 - w0 - w1
            m = (w0 >= -1e-6) & (w1 >= -1e-6) & (w2 >= -1e-6)
            if not m.any():
                continue
            z = w0 * zs[0] + w1 * zs[1] + w2 * zs[2]
            sub = zb[iy0:iy1 + 1, ix0:ix1 + 1]
            upd = m & (z > sub)
            if not upd.any():
                continue
            sub[upd] = z[upd]
            cb[iy0:iy1 + 1, ix0:ix1 + 1][upd] = np.clip(rgb * shade[k], 0, 1)
            ib[iy0:iy1 + 1, ix0:ix1 + 1][upd] = oid
            nb[iy0:iy1 + 1, ix0:ix1 + 1][upd] = n[k]
    # edges: object boundary, crease, depth jump
    e = np.zeros((H, W), bool)
    for dy, dx in ((0, 1), (1, 0)):
        a_i, b_i = ib[:H - dy, :W - dx], ib[dy:, dx:]
        a_n, b_n = nb[:H - dy, :W - dx], nb[dy:, dx:]
        a_z, b_z = zb[:H - dy, :W - dx], zb[dy:, dx:]
        ed = (a_i != b_i) | ((a_n * b_n).sum(-1) < 0.82) | (np.abs(a_z - b_z) > 0.35)
        ed &= (a_i >= 0) | (b_i >= 0)
        e[:H - dy, :W - dx] |= ed
    cb[e] = cb[e] * 0.25
    img = cb.reshape(H // ss, ss, W // ss, ss, 3)[:, :, :, :, :].mean(axis=(1, 3)) if (H % ss == 0 and W % ss == 0) \
        else cb[:H - H % ss, :W - W % ss].reshape(H // ss, ss, W // ss, ss, 3).mean(axis=(1, 3))
    return img, (x0, x1, y0, y1)


# ---------- annotation helpers ----------------------------------------------------------
def dim(ax, a, b, off, text, horiz=True, fs=7.5, col='#222'):
    """linear dimension between points a,b (2D, mm). horiz: measure x; else measure y. off: offset."""
    (ax0, ay0), (bx0, by0) = a, b
    kw = dict(color=col, lw=0.6)
    if horiz:
        y = off
        ax.plot([ax0, ax0], [ay0, y], **kw); ax.plot([bx0, bx0], [by0, y], **kw)
        ax.annotate('', (ax0, y), (bx0, y), arrowprops=dict(arrowstyle='<|-|>', color=col, lw=0.6,
                                                            shrinkA=0, shrinkB=0, mutation_scale=6))
        ax.text((ax0 + bx0) / 2, y + (0.6 if y >= max(ay0, by0) else -0.6), text, ha='center',
                va='bottom' if y >= max(ay0, by0) else 'top', fontsize=fs, color=col,
                bbox=dict(fc='white', ec='none', pad=0.3, alpha=0.85))
    else:
        x = off
        ax.plot([ax0, x], [ay0, ay0], **kw); ax.plot([bx0, x], [by0, by0], **kw)
        ax.annotate('', (x, ay0), (x, by0), arrowprops=dict(arrowstyle='<|-|>', color=col, lw=0.6,
                                                            shrinkA=0, shrinkB=0, mutation_scale=6))
        right = x >= max(ax0, bx0)
        ax.text(x + (0.6 if right else -0.6), (ay0 + by0) / 2, text, ha='left' if right else 'right',
                va='center', fontsize=fs, color=col, rotation=0, bbox=dict(fc='white', ec='none', pad=0.3, alpha=0.85))


def label(ax, xy, txt, xytext, fs=7.5, num=None):
    ax.annotate(txt, xy, xytext, fontsize=fs, color='#222', ha='center', va='center',
                arrowprops=dict(arrowstyle='-', color='#555', lw=0.5, shrinkA=2, shrinkB=0),
                bbox=dict(fc='white', ec='#bbb', lw=0.4, pad=1.5, boxstyle='round,pad=0.25'))
    ax.plot(*xy, 'o', ms=2.2, color=ACCENT)


def frame(fig, ax, title, sub=''):
    ax.set_aspect('equal'); ax.axis('off')
    fig.text(0.02, 0.965, title, fontsize=13, weight='bold', color='#1b1030', va='top')
    if sub:
        fig.text(0.02, 0.925, sub, fontsize=8.5, color='#555', va='top')
    fig.text(0.98, 0.02, "Agent Dot  |  all dimensions mm  |  lid T = %.1f" % p['LAPTOP_T'],
             fontsize=7, color='#888', ha='right')


def show(img, ext, ax):
    ax.imshow(img, extent=ext, origin='upper', interpolation='lanczos')
    ax.set_xlim(ext[0], ext[1]); ax.set_ylim(ext[2], ext[3])


def save(fig, name):
    fig.savefig(os.path.join(OUT, name), dpi=200)
    PAGES.append(fig)


PAGES = []
cache = {}


def mesh_of(name, shape, dev=0.04):
    if name not in cache:
        cache[name] = tess(shape, dev)
    return cache[name]


def items_from(d, offsets=None, skip=()):
    its = []
    for i, (n, s) in enumerate(d.items()):
        if n in skip:
            continue
        t = mesh_of(n, s)
        if offsets and n in offsets:
            t = t + np.array(offsets[n])
        its.append((t, hex2rgb(pal(n)), i + (100 if n in comps else 0) + (50 if n in pads else 0)))
    return its


PAL.update({'TP4056': '#1f4fa0', 'ESP32_SuperMini_PCB': '#2f7d4f', 'ESP32_SuperMini_USB': '#c9c9cf', 'TP4056_USB': '#c9c9cf'})
from matplotlib.path import Path as MPath
from matplotlib.patches import PathPatch
src = open('render.py').read()
i0 = src.index('def section_polys'); i1 = src.index('lid_sec = rprism')
exec(src[i0:i1])
ALL = {**parts, **pads, **comps}
asm_items = items_from(ALL)
C = c5_layout(p, L)
HT = L['ez1'] - L['ez0']

# 1 front / 2 rear (cover on) / 3 rear cover off
def ortho(items, dv, up=(0, 0, 1), ppm=10):
    return raster(items, make_view(dv, up), ppm=ppm, margin=10)
fig, ax = plt.subplots(figsize=(7, 10)); img, ext = ortho(asm_items, (0, -1, 0)); show(img, ext, ax)
frame(fig, ax, '1  Front view', 'From the keyboard: only the 32 mm light bar and two short fingers show.')
ax.axhline(0, color=ACCENT, lw=0.7, ls='--')
dim(ax, (-16, C['z1']), (16, C['z1']), C['z1'] + 4, '32 light bar')
dim(ax, (16, 0), (16, C['z1']), 20, '%.1f above lid' % C['z1'], horiz=False)
save(fig, '01_front.png')

fig, ax = plt.subplots(figsize=(7, 10)); img, ext = ortho(asm_items, (0, 1, 0)); show(img, ext, ax)
frame(fig, ax, '2  Rear view', 'One-piece body, cover held by 2 x M2x6 countersunk screws.')
dim(ax, (-16, L['ez0']), (16, L['ez0']), L['ez0'] - 4, '32')
dim(ax, (16, L['ez0']), (16, C['z1']), 20, '%.1f' % (C['z1'] - L['ez0']), horiz=False)
save(fig, '02_rear.png')

inner = {k: v for k, v in ALL.items() if k not in ('Enclosure_Cover', 'Pad_Battery') and not k.startswith('Screw')}
img, ext = ortho(items_from(inner), (0, 1, 0), ppm=14)
fig, ax = plt.subplots(figsize=(9, 11)); show(img, ext, ax)
frame(fig, ax, '3  Inside the box (cover off, rear view)', 'Both USB-C ports exit the left wall (right side in this rear view). Switch on the other wall.')
ax.set_xlim(ext[0] - 34, ext[1] + 34)
X = lambda x: -x
for (x, z), t, (tx, tz) in (((0, (L['bat_z0'] + L['bat_z1']) / 2), 'LiPo bay\nup to 6 x 25.5 x 36', (-36, -22)),
                            ((0, (L['tp_z0'] + L['tp_z1']) / 2), 'TP4056 (up to 28 x 17.6)', (-36, -51)),
                            ((0, (L['sm_z0'] + L['sm_z1']) / 2), 'ESP32-S3 SuperMini', (-36, -72)),
                            ((X(L['ex0'] + 0.8), (L['tp_z0'] + L['tp_z1']) / 2), 'USB-C (charge)', (34, -48)),
                            ((X(L['ex0'] + 0.8), (L['sm_z0'] + L['sm_z1']) / 2), 'USB-C (ESP)', (34, -66)),
                            ((X(L['ex1'] - 0.8), L['sw_zc']), 'MSK-12C02 switch', (-36, -84)),
                            ((0, L['iz1'] - 1.5), 'wire band + wire hole\nfrom the LED box', (34, -4))):
    label(ax, (x, z), t, (tx, tz), fs=7.5)
save(fig, '03_internal.png')

# 4 sections
fig, axs = plt.subplots(1, 2, figsize=(12, 11))
lid_sec = rprism(-30, 30, -100, 0, 0, p['LAPTOP_T'], 0, 'y')
for ax, xs, ttl in ((axs[0], 0.0, 'A-A  (X = 0)'), (axs[1], 10.7, 'B-B  (X = +10.7: wire hole)')):
    draw_sec(ax, lid_sec, xs, '#e8e8ee', hatch='////')
    for n, s in ALL.items():
        draw_sec(ax, s, xs, pal(n))
    ax.set_aspect('equal'); ax.set_xlim(L['y_h0'] - 8, L['ey2'] + 14); ax.set_ylim(L['ez0'] - 6, C['z1'] + 6)
    ax.axis('off'); ax.set_title(ttl, fontsize=9, loc='left')
dim(axs[0], (L['ey0'], L['ez0']), (L['ey2'], L['ez0']), L['ez0'] - 3, 'box %.1f' % (L['ey2'] - L['ey0']), fs=7)
dim(axs[0], (L['ey2'], L['ez0']), (L['ey2'], C['z1']), L['ey2'] + 4, '%.1f' % (C['z1'] - L['ez0']), horiz=False, fs=7)
dim(axs[0], (L['y_h0'], C['z1']), (L['ey2'], C['z1']), C['z1'] + 3, '%.1f' % (L['ey2'] - L['y_h0']), fs=7)
for t, xy, xt in (('6 mm LED box', (5, 4), (24, 12)), ('battery', ((L['iy0'] + L['ey1']) / 2, -22), (26, -22)),
                  ('TP4056', ((L['iy0'] + L['ey1']) / 2, -51), (26, -51)), ('SuperMini', ((L['iy0'] + L['ey1']) / 2, -72), (26, -72)),
                  ('cover', (L['ey2'] - 0.8, -30), (26, -36))):
    label(axs[0], xy, t, xt, fs=7)
label(axs[1], ((C['y_s0'] + C['y_s1']) / 2, 3), 'RGB pixel (flat, at the back)', (24, -8), fs=7)
label(axs[1], (L['iy0'] + 2, 0), 'wire hole into the box', (24, 2), fs=7)
fig.text(0.02, 0.965, '4  Section views', fontsize=13, weight='bold', color='#1b1030', va='top')
fig.text(0.02, 0.935, 'LED box, clamp and controller box are one print. The pixel lies flat at the back of the 6 mm box; its wires drop straight into the box.',
         fontsize=8.5, color='#555', va='top')
save(fig, '04_section.png')

# 5 LED box top section
fig, ax = plt.subplots(figsize=(11, 6))
for n in ('Body', 'LED_End_Plug', 'Diffuser_Strip', 'LED_PCB', 'LEDs_WS2812B_2020'):
    draw_sec(ax, ALL[n], (C['zf'] + C['z_led1']) / 2, pal(n), axis='z')
ax.set_aspect('equal'); ax.axis('off'); ax.set_xlim(-22, 22); ax.set_ylim(L['y_h0'] - 3, L['ey2'] + 3)
label(ax, (0, (C['y_s0'] + C['y_s1']) / 2), 'RGB pixel %.0f x %.0f' % (p['PX_L'], p['PX_W']), (-20, L['ey2'] + 2), fs=7.5)
label(ax, (0, -0.6), 'diffuser (slides in from the right)', (0, L['y_h0'] - 2), fs=7.5)
label(ax, (12, 9), 'wire hole', (20, L['ey2'] + 2), fs=7.5)
frame(fig, ax, '5  LED box, cut just above the floor', 'Front of the laptop at the bottom.')
save(fig, '05_led_box_top_section.png')

# 6 exploded
EX = {'LED_End_Plug': (30, 0, 0), 'Diffuser_Strip': (50, 0, 0), 'LED_PCB': (0, 0, 14), 'LEDs_WS2812B_2020': (0, 0, 14),
      'Battery_LiPo': (0, 22, 0), 'TP4056_PCB': (0, 22, 0), 'TP4056_USB_C': (0, 22, 0), 'ESP32_SuperMini_PCB': (0, 22, 0),
      'ESP32_SuperMini_USB_C': (0, 22, 0), 'Switch': (0, 22, 0), 'Switch_actuator': (0, 22, 0), 'Pad_Battery': (0, 32, 0),
      'Enclosure_Cover': (0, 44, 0), 'Screw_M2x6_1': (0, 58, 0), 'Screw_M2x6_2': (0, 58, 0),
      'Pad_Top': (0, -12, 6), 'Pad_Front_L': (0, -14, 0), 'Pad_Front_R': (0, -14, 0), 'Pad_Rear': (0, -10, 0), 'Pad_Rear_Low': (0, -10, 0)}
vw = make_view((-0.8, 1.0, 0.5))
img, ext = raster(items_from(ALL, EX), vw, ppm=7, margin=6)
fig, ax = plt.subplots(figsize=(12, 10)); show(img, ext, ax)
frame(fig, ax, '6  Exploded view', 'Body (one print) + cover + end plug; electronics drop in from the back.')
save(fig, '06_exploded.png')

# 7 mounted
lid, screen, cam = make_laptop(p, L)
mi = asm_items + [(tess(lid, 0.2), hex2rgb(PAL['Lid']), 900), (tess(screen, 0.5), hex2rgb(PAL['Screen']), 901), (tess(cam, 0.05), hex2rgb(PAL['Cam']), 902)]
for nm, dv, sub in (('07_mounted.png', (0.55, -1.0, 0.42), 'Front-right'), ('07b_mounted_rear.png', (-0.6, 1.0, 0.45), 'Rear')):
    vw = make_view(dv); r_, u_, d_ = vw
    c2 = lambda q: (np.array(q) @ r_, np.array(q) @ u_)
    cx, cy = c2((0, 5, -40))
    img, ext = raster(mi, vw, ppm=7, bounds=(cx - 80, cx + 80, cy - 70, cy + 55))
    fig, ax = plt.subplots(figsize=(11, 8)); show(img, ext, ax)
    frame(fig, ax, '7  Mounted on the MacBook', sub)
    save(fig, nm)

with PdfPages('out/AgentDot_Drawings_%s.pdf' % VTAG) as pdf:
    for f in PAGES:
        pdf.savefig(f)
print('RENDER OK', len(PAGES))
