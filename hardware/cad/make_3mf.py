# 3MF helpers (read_stl, write_3mf) used by make_3mf_v12.py.
# Plain 3MF core spec: opens in Bambu Studio / OrcaSlicer / PrusaSlicer with parts
# already laid out on a 256 x 256 mm A1 bed.
import numpy as np, zipfile, os, sys, glob
from xml.sax.saxutils import escape

STL = 'out/STL'
OUT = sys.argv[1] if len(sys.argv) > 1 else 'out/Bambu_A1_3MF'
os.makedirs(OUT, exist_ok=True)
BED = 256.0
GAP = 8.0


def read_stl(path):
    d = open(path, 'rb').read()
    n = int(np.frombuffer(d, '<u4', 1, 80)[0])
    rec = np.frombuffer(d, dtype=np.dtype([('n', '<f4', 3), ('v', '<f4', (3, 3)), ('a', '<u2')]), count=n, offset=84)
    tri = rec['v'].reshape(-1, 3).astype(np.float64)
    key = np.round(tri, 4)
    verts, inv = np.unique(key, axis=0, return_inverse=True)
    faces = inv.reshape(-1, 3)
    faces = faces[(faces[:, 0] != faces[:, 1]) & (faces[:, 1] != faces[:, 2]) & (faces[:, 0] != faces[:, 2])]
    verts -= [verts[:, 0].min(), verts[:, 1].min(), verts[:, 2].min()]   # local origin at bbox min corner
    return verts, faces


def pack(items):
    """simple shelf packing, then centre the whole group on the bed"""
    x = y = shelf = 0.0
    pos = []
    maxw = 0
    for name, v, f in items:
        w, h = v[:, 0].max(), v[:, 1].max()
        if x + w > BED - 20 and x > 0:
            x = 0; y += shelf + GAP; shelf = 0
        pos.append((x, y)); x += w + GAP; shelf = max(shelf, h); maxw = max(maxw, x - GAP)
    toth = y + shelf
    ox, oy = (BED - maxw) / 2, (BED - toth) / 2
    return [(px + ox, py + oy) for px, py in pos]


def write_3mf(fname, items, title):
    pos = pack(items)
    objs, build = [], []
    for i, ((name, v, f), (px, py)) in enumerate(zip(items, pos), start=1):
        vs = '\n'.join('<vertex x="%.4f" y="%.4f" z="%.4f"/>' % tuple(p) for p in v)
        ts = '\n'.join('<triangle v1="%d" v2="%d" v3="%d"/>' % tuple(t) for t in f)
        objs.append('<object id="%d" name="%s" type="model"><mesh><vertices>\n%s\n</vertices><triangles>\n%s\n'
                    '</triangles></mesh></object>' % (i, escape(name), vs, ts))
        build.append('<item objectid="%d" transform="1 0 0 0 1 0 0 0 1 %.3f %.3f 0" printable="1"/>' % (i, px, py))
    model = ('<?xml version="1.0" encoding="UTF-8"?>\n'
             '<model unit="millimeter" xml:lang="en-US" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">\n'
             '<metadata name="Title">%s</metadata>\n'
             '<metadata name="Application">AgentDot CAD generator</metadata>\n'
             '<resources>\n%s\n</resources>\n<build>\n%s\n</build>\n</model>\n') % (escape(title), '\n'.join(objs), '\n'.join(build))
    ct = ('<?xml version="1.0" encoding="UTF-8"?>\n<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
          '<Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>')
    rels = ('<?xml version="1.0" encoding="UTF-8"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>'
            '</Relationships>')
    path = os.path.join(OUT, fname)
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml', ct)
        z.writestr('_rels/.rels', rels)
        z.writestr('3D/3dmodel.model', model)
    # sanity: everything inside the bed
    for (name, v, f), (px, py) in zip(items, pos):
        assert px >= 0 and py >= 0 and px + v[:, 0].max() <= BED and py + v[:, 1].max() <= BED, name
    print('%-45s %2d objects  %6.0f KB' % (fname, len(items), os.path.getsize(path) / 1024))


def load(names, folder=STL, copies=1, label=None):
    out = []
    for n in names:
        v, f = read_stl(os.path.join(folder, n))
        for c in range(copies):
            base = (label or {}).get(n, n.replace('.stl', ''))
            out.append((base + ('' if copies == 1 else '_%d' % (c + 1)), v, f))
    return out


# ---------------------------------------------------------------------------
# (end of helpers - make_3mf_v12.py loads everything above this line)
