# Morvic — reloj automático modelado 100 % por código para la landing morvic.html.
# Unidades: 1 = 1 cm (caja de 41 mm). La esfera mira a +Z y las piezas se apilan sobre Z,
# así la web puede "explotar" el reloj moviendo cada objeto por su eje.
# Todo lo que gira (agujas, ruedas, volante, rotor) tiene su origen en su propio eje.
import bpy, bmesh, math, os
from mathutils import Matrix, Vector, Euler

TAU = math.tau
SERIF = r'C:\Windows\Fonts\BOD_R.TTF'          # Bodoni MT
SANS = r'C:\Windows\Fonts\bahnschrift.ttf'
if not os.path.exists(SANS):
    SANS = SERIF
Z = Vector((0, 0, 1))
SWAP = Matrix(((0, 0, 1, 0), (1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 0, 1)))   # local (a,b,c) -> mundo (c,a,b)


# ------------------------------------------------------------------ escena limpia
def reset():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.curves, bpy.data.cameras,
                 bpy.data.lights, bpy.data.fonts, bpy.data.actions):
        for b in list(coll):
            if b.users == 0:
                coll.remove(b)


reset()
COL = bpy.context.scene.collection


# ------------------------------------------------------------------ materiales
def sock(node, ident):
    return next(s for s in node.inputs if s.identifier == ident)


def mat(name, color, metal=0.0, rough=0.5, coat=0.0, emit=None, glass=False):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    sock(b, 'Base Color').default_value = (*color, 1)
    sock(b, 'Metallic').default_value = metal
    sock(b, 'Roughness').default_value = rough
    sock(b, 'Coat Weight').default_value = coat
    if emit:
        sock(b, 'Emission Color').default_value = (*emit, 1)
        sock(b, 'Emission Strength').default_value = 0.0      # la web lo enciende en el capítulo del lume
    if glass:
        sock(b, 'Transmission Weight').default_value = 1.0
        sock(b, 'IOR').default_value = 1.77
        if hasattr(m, 'use_raytrace_refraction'):
            m.use_raytrace_refraction = True
    m.diffuse_color = (*color, 0.25 if glass else 1)
    return m


M = dict(
    acero=mat('Acero', (0.80, 0.80, 0.82), 1.0, 0.16),
    oro=mat('Oro', (0.96, 0.76, 0.48), 1.0, 0.22),
    esfera=mat('Esfera', (0.006, 0.014, 0.045), 0.55, 0.32, coat=0.6),
    impresion=mat('Impresion', (0.93, 0.80, 0.58), 0.6, 0.35),
    lume=mat('Lume', (0.78, 0.86, 0.72), 0.0, 0.5, emit=(0.35, 1.0, 0.6)),
    zafiro=mat('Zafiro', (1, 1, 1), 0.0, 0.02, glass=True),
    platina=mat('Platina', (0.42, 0.43, 0.45), 1.0, 0.42),
    rodio=mat('Rodio', (0.82, 0.83, 0.85), 1.0, 0.24),
    ruedas=mat('Ruedas', (0.95, 0.72, 0.42), 1.0, 0.2),
    rubi=mat('Rubi', (0.55, 0.0, 0.03), 0.0, 0.05, coat=1.0),
    azul=mat('AceroAzul', (0.02, 0.07, 0.40), 1.0, 0.22),
    cuero=mat('Cuero', (0.07, 0.03, 0.014), 0.0, 0.55),
    costura=mat('Costura', (0.78, 0.68, 0.52), 0.0, 0.7),
    ojal=mat('Ojal', (0.005, 0.004, 0.003), 0.0, 0.8),
    grabado=mat('Grabado', (0.10, 0.07, 0.04), 0.6, 0.5),
    segundero=mat('Segundero', (0.96, 0.76, 0.48), 1.0, 0.22),
)


# ------------------------------------------------------------------ geometría base
def circ(r, n, cx=0.0, cy=0.0, a0=0.0):
    return [(cx + r * math.cos(a0 + TAU * k / n), cy + r * math.sin(a0 + TAU * k / n)) for k in range(n)]


def face(bm, vs, mi):
    try:
        f = bm.faces.new(vs)
        f.material_index = mi
        return f
    except ValueError:
        return None


def prism(bm, pts, z0, z1, mi=0):
    """Polígono 2D (x, y) extruido entre z0 y z1."""
    bot = [bm.verts.new((x, y, z0)) for x, y in pts]
    top = [bm.verts.new((x, y, z1)) for x, y in pts]
    face(bm, top, mi)
    face(bm, bot[::-1], mi)
    for i in range(len(pts)):
        j = (i + 1) % len(pts)
        face(bm, (bot[i], bot[j], top[j], top[i]), mi)
    return bot + top


def ring(bm, outer, inner, z0, z1, mi=0):
    """Anillo entre dos contornos con la misma cantidad de puntos."""
    ob = [bm.verts.new((x, y, z0)) for x, y in outer]
    ot = [bm.verts.new((x, y, z1)) for x, y in outer]
    ib = [bm.verts.new((x, y, z0)) for x, y in inner]
    it = [bm.verts.new((x, y, z1)) for x, y in inner]
    for i in range(len(outer)):
        j = (i + 1) % len(outer)
        face(bm, (ot[i], ot[j], it[j], it[i]), mi)
        face(bm, (ob[j], ob[i], ib[i], ib[j]), mi)
        face(bm, (ob[i], ob[j], ot[j], ot[i]), mi)
        face(bm, (ib[j], ib[i], it[i], it[j]), mi)
    return ob + ot + ib + it


def lathe(bm, prof, segs=96, mi=0, flute=None):
    """Gira un perfil cerrado [(r, z), ...] alrededor de Z. flute(k, r) deforma el radio por segmento."""
    rows = []
    for r, z in prof:
        if r < 1e-6:
            v = bm.verts.new((0, 0, z))
            rows.append([v] * segs)
        else:
            row = []
            for k in range(segs):
                a = TAU * k / segs
                rr = r * (flute(k, r) if flute else 1.0)
                row.append(bm.verts.new((rr * math.cos(a), rr * math.sin(a), z)))
            rows.append(row)
    for a in range(len(prof)):
        A, B = rows[a], rows[(a + 1) % len(prof)]
        if A[0] is A[1] and B[0] is B[1]:
            continue
        for k in range(segs):
            l = (k + 1) % segs
            vs = []
            for v in (A[k], A[l], B[l], B[k]):
                if v not in vs:
                    vs.append(v)
            if len(vs) >= 3:
                face(bm, vs, mi)
    return list({v for row in rows for v in row})


def box(bm, c, X, Y, Zd, sx, sy, sz, mi=0):
    c = Vector(c)
    X, Y, Zd = Vector(X).normalized() * sx / 2, Vector(Y).normalized() * sy / 2, Vector(Zd).normalized() * sz / 2
    v = [bm.verts.new(c + X * i + Y * j + Zd * k) for i in (-1, 1) for j in (-1, 1) for k in (-1, 1)]
    for f in ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)):
        face(bm, [v[i] for i in f], mi)
    return v


def bar2d(bm, p, q, w, z0, z1, mi=0):
    p, q = Vector(p[:2]), Vector(q[:2])
    d = (q - p).normalized()
    t = Vector((-d.y, d.x)) * w / 2
    return prism(bm, [tuple(p - t), tuple(q - t), tuple(q + t), tuple(p + t)], z0, z1, mi)


def basis(X, Y, Zd, t=(0, 0, 0)):
    m = Matrix.Identity(4)
    for i in range(3):
        m[i][0], m[i][1], m[i][2], m[i][3] = X[i], Y[i], Zd[i], t[i]
    return m


def bevel(bm, off, segs=2, ang=30, verts=None):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    vs = set(verts) if verts is not None else None
    edges = [e for e in bm.edges if e.is_manifold
             and (vs is None or (e.verts[0] in vs and e.verts[1] in vs))
             and e.calc_face_angle(0) > math.radians(ang)]
    if edges:
        bmesh.ops.bevel(bm, geom=edges, offset=off, segments=segs, affect='EDGES', profile=0.5, clamp_overlap=True)


def merge(bm, other):
    me = bpy.data.meshes.new('tmp_merge')
    other.to_mesh(me)
    other.free()
    bm.from_mesh(me)
    bpy.data.meshes.remove(me)


FONTS = {}


def text(bm, body, path, size, Mx, mi=0, extrude=0.003, spacing=1.0, res=3, align_y='CENTER'):
    if path not in FONTS:
        FONTS[path] = bpy.data.fonts.load(path, check_existing=True)
    cu = bpy.data.curves.new('tmp_txt', 'FONT')
    cu.body, cu.font, cu.size, cu.extrude = body, FONTS[path], size, extrude
    cu.align_x, cu.align_y, cu.space_character, cu.resolution_u = 'CENTER', align_y, spacing, res
    ob = bpy.data.objects.new('tmp_txt', cu)
    COL.objects.link(ob)
    bpy.context.view_layer.update()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(bpy.context.evaluated_depsgraph_get()))
    bpy.data.objects.remove(ob)
    bpy.data.curves.remove(cu)
    me.transform(Mx)
    before = set(bm.faces)
    bm.from_mesh(me)
    for f in bm.faces:
        if f not in before:
            f.material_index = mi
    bpy.data.meshes.remove(me)


def make(name, bm, mats, loc=(0, 0, 0), smooth=32):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)
    if smooth:
        me.shade_smooth()
        me.set_sharp_from_angle(angle=math.radians(smooth))
    ob = bpy.data.objects.new(name, me)
    COL.objects.link(ob)
    ob.location = loc
    return ob


def screw(bm, cx, cy, z, r=0.055, mi=0, slot_mi=0, a=0.4):
    vs = lathe(bm, [(0, z), (r, z), (r, z + 0.008), (r * 0.72, z + 0.017), (0, z + 0.02)], 20, mi)
    bmesh.ops.translate(bm, vec=(cx, cy, 0), verts=vs)
    box(bm, (cx, cy, z + 0.018), (math.cos(a), math.sin(a), 0), (-math.sin(a), math.cos(a), 0), Z,
        r * 1.8, 0.014, 0.01, slot_mi)


def jewel(bm, cx, cy, z, chaton_mi, ruby_mi):
    ring(bm, circ(0.078, 24, cx, cy), circ(0.046, 24, cx, cy), z, z + 0.008, chaton_mi)
    vs = lathe(bm, [(0, z), (0.046, z), (0.046, z + 0.006), (0.03, z + 0.011), (0, z + 0.013)], 20, ruby_mi)
    bmesh.ops.translate(bm, vec=(cx, cy, 0), verts=vs)


# ------------------------------------------------------------------ ruedas
def gear_pts(r, teeth, depth, kind='std'):
    rr = r - depth
    shape = {'std': ((0, rr), (0.18, r), (0.47, r), (0.65, rr)),
             'escape': ((0, rr), (0.62, r), (0.70, r - depth * 0.25), (0.78, rr)),
             'ratchet': ((0, rr), (0.88, r), (0.92, rr))}[kind]
    pts = []
    for k in range(teeth):
        for f, rad in shape:
            a = TAU / teeth * (k + f)
            pts.append((rad * math.cos(a), rad * math.sin(a)))
    return pts


def gear(bm, r, teeth, z0, z1, spokes=4, kind='std', mi=0, hub=0.07, depth=None, pinion=True):
    depth = depth or max(0.018, 2.4 * r / teeth)
    outer = gear_pts(r, teeth, depth, kind)
    if spokes:
        rin = r - depth - max(0.05, r * 0.14)
        inner = [(rin * math.cos(math.atan2(y, x)), rin * math.sin(math.atan2(y, x))) for x, y in outer]
        ring(bm, outer, inner, z0, z1, mi)
        prism(bm, circ(hub, 24), z0, z1, mi)
        for s in range(spokes):
            a = TAU * s / spokes + 0.3
            d, t = Vector((math.cos(a), math.sin(a))), Vector((-math.sin(a), math.cos(a)))
            L0, L1 = hub * 0.6, rin + 0.01
            w0, w1 = max(0.03, r * 0.09), max(0.022, r * 0.055)
            pts = [d * L0 - t * w0 / 2, d * L1 - t * w1 / 2, d * L1 + t * w1 / 2, d * L0 + t * w0 / 2]
            prism(bm, [tuple(p) for p in pts], z0 + 0.002, z1 - 0.002, mi)
    else:
        prism(bm, outer, z0, z1, mi)
    if pinion:
        prism(bm, gear_pts(max(0.06, r * 0.2), 10, 0.025), z0 - 0.05, z0, mi)
        prism(bm, circ(0.025, 12), z0 - 0.12, z1 + 0.07, mi)


# ================================================================== CAJA
def build_case():
    bm = bmesh.new()
    lathe(bm, [(1.80, -0.30), (1.97, -0.30), (2.03, -0.275), (2.07, -0.19), (2.09, -0.03), (2.085, 0.15),
               (2.065, 0.27), (2.02, 0.345), (1.97, 0.36), (1.80, 0.36)], 128, 0)
    # asas: perfil lateral (y, z) que baja hacia la muñeca, extruido en X
    N, y0, y1 = 10, 1.55, 2.72
    top = [(y0 + (y1 - y0) * i / N, 0.33 - 0.27 * (i / N) ** 2) for i in range(N + 1)]
    bot = [(y0 + (y1 - y0) * i / N, -0.25 - 0.10 * (i / N) ** 2) for i in range(N + 1)]
    tip = [(2.775, -0.30), (2.80, -0.14), (2.775, 0.01)]
    prof = bot + tip + top[::-1]
    for sx in (1, -1):
        for sy in (1, -1):
            lug = bmesh.new()
            prism(lug, prof, 0.98, 1.42)
            bmesh.ops.transform(lug, matrix=SWAP, verts=lug.verts)
            for v in lug.verts:                         # se afinan hacia la punta
                t = min(1.0, max(0.0, (v.co.y - 1.55) / 1.25))
                v.co.x = 1.20 + (v.co.x - 1.20) * (1 - 0.24 * t)
            bevel(lug, 0.055, 3, 25)
            bmesh.ops.transform(lug, matrix=Matrix.Diagonal((sx, sy, 1, 1)), verts=lug.verts)
            merge(bm, lug)
    # pasadores de la correa
    for sy in (1, -1):
        vs = lathe(bm, [(0, -0.98), (0.045, -0.98), (0.045, 0.98), (0, 0.98)], 12, 0)
        bmesh.ops.transform(bm, matrix=Matrix.Translation((0, sy * 2.52, -0.10)) @ SWAP, verts=vs)
    # réhaut: aro inclinado entre esfera y cristal con la minutería
    lathe(bm, [(1.64, 0.215), (1.80, 0.215), (1.80, 0.40), (1.775, 0.40)], 128, 1)
    p0, p1 = Vector((1.64, 0.215)), Vector((1.775, 0.40))
    S2 = (p1 - p0).normalized()
    mid = p0 + (p1 - p0) * 0.5
    for k in range(60):
        a = math.pi / 2 - TAU * k / 60
        R = Vector((math.cos(a), math.sin(a), 0))
        T = Vector((-R.y, R.x, 0))
        S = (R * S2.x + Z * S2.y).normalized()
        Nn = (-R * S2.y + Z * S2.x).normalized()
        major = k % 5 == 0
        c = R * mid.x + Z * mid.y + Nn * 0.0015
        box(bm, c, T, S, Nn, 0.018 if major else 0.008, 0.11 if major else 0.06, 0.003, 2)
    return make('Caja', bm, [M['acero'], M['esfera'], M['impresion']])


def build_bezel():
    bm = bmesh.new()
    lathe(bm, [(1.745, 0.36), (2.01, 0.36), (2.02, 0.41), (1.985, 0.495), (1.91, 0.552), (1.80, 0.575),
               (1.75, 0.565)], 128, 0)
    return make('Bisel', bm, [M['acero']])


def build_crystal():
    bm = bmesh.new()
    lathe(bm, [(0, 0.50), (1.765, 0.50), (1.765, 0.585), (1.62, 0.612), (1.25, 0.640), (0.7, 0.660),
               (0, 0.667)], 96, 0)
    return make('Cristal', bm, [M['zafiro']], smooth=60)


# ================================================================== ESFERA
def baton(bm, a, r0, r1, w, h, z, mi, off=0.0):
    R = Vector((math.cos(a), math.sin(a), 0))
    T = Vector((-R.y, R.x, 0))
    vs = prism(bm, [(-w / 2, 0), (w / 2, 0), (w / 2, h * 0.55), (0, h), (-w / 2, h * 0.55)], r0, r1, mi)
    bmesh.ops.transform(bm, matrix=basis(T, Z, R, T * off + Z * z), verts=vs)


def build_dial():
    bm = bmesh.new()
    lathe(bm, [(0, 0.17), (1.70, 0.17), (1.70, 0.215), (0, 0.215)], 128, 0)
    for h in range(12):
        a = math.pi / 2 - h * TAU / 12
        if h == 0:
            for off in (-0.062, 0.062):
                baton(bm, a, 1.06, 1.42, 0.07, 0.07, 0.215, 1, off)
        else:
            baton(bm, a, 1.06, 1.42, 0.085, 0.07, 0.215, 1)
        prism(bm, circ(0.038, 18, 1.52 * math.cos(a), 1.52 * math.sin(a)), 0.215, 0.222, 2)
    text(bm, 'MORVIC', SERIF, 0.30, Matrix.Translation((0, 0.64, 0.219)), 3, 0.004, 1.2, res=6)
    text(bm, 'LIMA', SANS, 0.062, Matrix.Translation((0, 0.42, 0.217)), 3, 0.002, 2.2)
    text(bm, 'AUTOMATIC', SANS, 0.075, Matrix.Translation((0, -0.60, 0.217)), 3, 0.002, 1.6)
    return make('Esfera', bm, [M['esfera'], M['oro'], M['lume'], M['impresion']])


# ================================================================== AGUJAS (apuntan a las 12)
def hand(name, outline, lume, z0, th, hub_r, mats, extra=None):
    bm = bmesh.new()
    prism(bm, outline, z0, z0 + th, 0)
    prism(bm, circ(hub_r, 32), z0, z0 + th, 0)
    if lume:
        prism(bm, lume, z0 + th, z0 + th + 0.005, 1)
    if extra:
        extra(bm)
    return make(name, bm, mats, smooth=30)


def build_hands():
    hand('Aguja_Horas',
         [(0.065, -0.05), (0.07, 0.70), (0, 0.98), (-0.07, 0.70), (-0.065, -0.05)],
         [(0.04, 0.25), (0.042, 0.68), (0, 0.88), (-0.042, 0.68), (-0.04, 0.25)],
         0.30, 0.02, 0.12, [M['oro'], M['lume']])
    hand('Aguja_Minutos',
         [(0.05, -0.05), (0.052, 1.15), (0, 1.45), (-0.052, 1.15), (-0.05, -0.05)],
         [(0.028, 0.30), (0.03, 1.12), (0, 1.36), (-0.03, 1.12), (-0.028, 0.30)],
         0.335, 0.02, 0.10, [M['oro'], M['lume']])

    def sec_extra(bm):
        prism(bm, circ(0.065, 24, 0, -0.32), 0.37, 0.38, 0)
        prism(bm, circ(0.045, 20, 0, 1.25), 0.37, 0.38, 0)
        prism(bm, circ(0.03, 16, 0, 1.25), 0.38, 0.384, 1)
        lathe(bm, [(0, 0.38), (0.045, 0.38), (0.045, 0.39), (0.03, 0.40), (0, 0.403)], 20, 0)
    hand('Aguja_Segundos',
         [(0.012, -0.42), (0.008, 1.62), (-0.008, 1.62), (-0.012, -0.42)], None,
         0.37, 0.01, 0.07, [M['segundero'], M['lume']], sec_extra)


# ================================================================== MOVIMIENTO
PIV = dict(centro=(0.0, 0.0), tercera=(0.55, 0.30), segundos=(0.75, -0.15), escape=(0.45, -0.46),
           barril=(-0.55, 0.50), volante=(-0.25, -0.95), ancora=(0.12, -0.72))


def build_movement():
    bm = bmesh.new()
    lathe(bm, [(0, -0.20), (1.62, -0.20), (1.62, -0.06), (1.60, -0.04), (0, -0.04)], 128, 0)
    make('Platina', bm, [M['platina']])

    for name, key, r, teeth, z0, z1, spokes, kind in (
            ('Rueda_Centro', 'centro', 0.52, 80, -0.035, -0.015, 4, 'std'),
            ('Rueda_Tercera', 'tercera', 0.40, 70, -0.010, 0.010, 4, 'std'),
            ('Rueda_Segundos', 'segundos', 0.36, 64, 0.015, 0.035, 5, 'std'),
            ('Rueda_Escape', 'escape', 0.24, 20, 0.040, 0.058, 4, 'escape')):
        bm = bmesh.new()
        gear(bm, r, teeth, z0, z1, spokes, kind, depth=0.055 if kind == 'escape' else None)
        make(name, bm, [M['ruedas']], (*PIV[key], 0))

    bm = bmesh.new()                                     # barrilete (muelle real)
    gear(bm, 0.62, 90, 0.0, 0.05, 0, pinion=False)
    lathe(bm, [(0.50, 0.05), (0.56, 0.05), (0.56, 0.054), (0.50, 0.054)], 96, 0)
    make('Barrilete', bm, [M['ruedas']], (*PIV['barril'], 0))

    bm = bmesh.new()                                     # trinquete: gira al dar cuerda con la corona
    gear(bm, 0.40, 36, 0.054, 0.078, 0, 'ratchet', pinion=False)
    screw(bm, 0, 0, 0.078, 0.07, 1, 2)
    make('Trinquete', bm, [M['rodio'], M['azul'], M['ojal']], (*PIV['barril'], 0))

    bm = bmesh.new()                                     # áncora
    prism(bm, circ(0.04, 16), 0.06, 0.075, 0)
    bx, by = PIV['volante'][0] - PIV['ancora'][0], PIV['volante'][1] - PIV['ancora'][1]
    dB = Vector((bx, by)).normalized()
    tB = Vector((-dB.y, dB.x))
    end = dB * 0.30
    bar2d(bm, (0, 0), end, 0.03, 0.06, 0.075, 0)
    for sgn in (1, -1):
        bar2d(bm, end + tB * 0.028 * sgn, end + tB * 0.028 * sgn + dB * 0.06, 0.016, 0.06, 0.075, 0)
    ex, ey = PIV['escape'][0] - PIV['ancora'][0], PIV['escape'][1] - PIV['ancora'][1]
    aE = math.atan2(ey, ex)
    for sgn in (1, -1):
        dA = Vector((math.cos(aE + 0.55 * sgn), math.sin(aE + 0.55 * sgn)))
        tip = dA * 0.24
        bar2d(bm, (0, 0), tip, 0.03, 0.06, 0.075, 0)
        box(bm, (tip.x, tip.y, 0.067), (dA.x, dA.y, 0), (-dA.y, dA.x, 0), Z, 0.07, 0.024, 0.02, 1)
    make('Ancora', bm, [M['rodio'], M['rubi']], (*PIV['ancora'], 0))

    bm = bmesh.new()                                     # volante + espiral: el corazón que late
    ring(bm, circ(0.48, 96), circ(0.41, 96), 0.02, 0.05, 0)
    prism(bm, circ(0.06, 24), 0.02, 0.05, 0)
    for s in range(3):
        a = TAU * s / 3 + 0.5
        bar2d(bm, (0, 0), (0.42 * math.cos(a), 0.42 * math.sin(a)), 0.04, 0.025, 0.045, 0)
    for s in range(8):
        a = TAU * s / 8
        prism(bm, circ(0.022, 10, 0.445 * math.cos(a), 0.445 * math.sin(a)), 0.05, 0.066, 0)
    n, turns, r0, r1, w, z0, z1 = 576, 9, 0.09, 0.36, 0.006, -0.012, 0.004
    rows = []
    for i in range(n + 1):
        t = i / n
        a, r = TAU * turns * t, r0 + (r1 - r0) * t
        c, s = math.cos(a), math.sin(a)
        rows.append([bm.verts.new((c * (r - w / 2), s * (r - w / 2), z0)), bm.verts.new((c * (r + w / 2), s * (r + w / 2), z0)),
                     bm.verts.new((c * (r + w / 2), s * (r + w / 2), z1)), bm.verts.new((c * (r - w / 2), s * (r - w / 2), z1))])
    for i in range(n):
        A, B = rows[i], rows[i + 1]
        for k in range(4):
            l = (k + 1) % 4
            face(bm, (A[k], A[l], B[l], B[k]), 1)
    face(bm, rows[0][::-1], 1)
    face(bm, rows[-1], 1)
    prism(bm, circ(0.025, 12), -0.03, 0.12, 0)
    make('Volante', bm, [M['ruedas'], M['rodio']], (*PIV['volante'], 0))

    # puente de tren: brazos de rodio con rubíes y tornillos azulados
    bm = bmesh.new()
    pts = [PIV[k] for k in ('centro', 'tercera', 'segundos', 'escape')]
    feet = [(1.10, 1.05), (1.50, -0.35)]
    for a, b in zip(pts, pts[1:]):
        bar2d(bm, a, b, 0.14, 0.08, 0.118, 0)
    bar2d(bm, PIV['tercera'], feet[0], 0.16, 0.08, 0.118, 0)
    bar2d(bm, PIV['segundos'], feet[1], 0.16, 0.08, 0.118, 0)
    for p in pts + feet:
        prism(bm, circ(0.13, 32, *p), 0.08, 0.12, 0)
    bevel(bm, 0.008, 1, 30)
    for p in pts:
        jewel(bm, *p, 0.12, 1, 2)
    for p in feet:
        screw(bm, *p, 0.12, 0.06, 3, 4)
    make('Puente', bm, [M['rodio'], M['ruedas'], M['rubi'], M['azul'], M['ojal']])

    # puente del volante (gallo)
    bm = bmesh.new()
    vx, vy = PIV['volante']
    base = [(-1.38, -0.80), (-1.58, -0.30)]
    dm = Vector((vx + 1.48, vy + 0.55)).normalized()
    pm = Vector((-dm.y, dm.x)) * 0.09
    prism(bm, [base[0], (vx - pm.x, vy - pm.y), (vx + pm.x, vy + pm.y), base[1]], 0.085, 0.117, 0)
    prism(bm, circ(0.14, 32, vx, vy), 0.085, 0.12, 0)
    prism(bm, circ(0.16, 32, -1.45, -0.55), 0.085, 0.12, 0)
    bevel(bm, 0.008, 1, 30)
    jewel(bm, vx, vy, 0.12, 1, 2)
    screw(bm, -1.45, -0.55, 0.12, 0.065, 3, 4)
    make('Puente_Volante', bm, [M['rodio'], M['ruedas'], M['rubi'], M['azul'], M['ojal']])


def build_rotor():
    bm = bmesh.new()
    n = 64
    half = lambda r: [(r * math.cos(math.pi + math.pi * k / n), r * math.sin(math.pi + math.pi * k / n)) for k in range(n + 1)]
    prism(bm, half(1.52) + half(0.22)[::-1], -0.275, -0.245, 0)
    prism(bm, half(1.52) + half(1.30)[::-1], -0.29, -0.235, 0)
    lathe(bm, [(0, -0.292), (0.26, -0.292), (0.26, -0.232), (0, -0.232)], 48, 1)
    ring(bm, circ(0.20, 32), circ(0.12, 32), -0.297, -0.29, 0)
    back = lambda x, y, z: Matrix(((-1, 0, 0, x), (0, 1, 0, y), (0, 0, -1, z), (0, 0, 0, 1)))
    text(bm, 'MORVIC', SERIF, 0.26, back(0, -0.80, -0.279), 2, 0.004, 1.25, res=5)
    text(bm, 'AUTOMATIC  ·  28 800 A/H', SANS, 0.062, back(0, -1.04, -0.277), 2, 0.002, 1.5)
    return make('Rotor', bm, [M['oro'], M['rodio'], M['grabado']])


def build_caseback():
    bm = bmesh.new()
    lathe(bm, [(1.30, -0.30), (1.975, -0.30), (1.995, -0.33), (1.955, -0.41), (1.87, -0.455), (1.36, -0.455),
               (1.30, -0.445)], 128, 0)
    lathe(bm, [(0, -0.445), (1.31, -0.445), (1.31, -0.31), (0, -0.31)], 96, 1)
    # leyenda grabada alrededor, legible mirando el fondo
    s, size, r = 'MORVIC  ·  LIMA  ·  AUTOMATIC  ·  SAPPHIRE  ·  100 M  ·  N° 0001', 0.085, 1.615
    gw = lambda ch: size * 1.12 * (0.38 if ch in ' ·.' else 0.36 if ch in 'I1' else 0.84 if ch in 'MW' else 0.62)
    total = sum(gw(c) for c in s) - (gw(s[0]) + gw(s[-1])) / 2
    phi = math.pi / 2 - total / r / 2
    for i, ch in enumerate(s):
        if i:
            phi += (gw(s[i - 1]) + gw(ch)) / 2 / r
        if ch == ' ':
            continue
        T = Vector((-math.sin(phi), math.cos(phi), 0))
        R = Vector((math.cos(phi), math.sin(phi), 0))
        text(bm, ch, SANS, size, basis(T, R, -Z, R * r + Z * -0.455), 2, 0.003)
    return make('Fondo', bm, [M['acero'], M['zafiro'], M['grabado']])


def build_crown():
    bm = bmesh.new()
    flute = lambda k, r: 0.94 if (r > 0.29 and k % 2) else 1.0
    lathe(bm, [(0, 2.18), (0.26, 2.18), (0.30, 2.21), (0.30, 2.45), (0.27, 2.50), (0.20, 2.515), (0, 2.52)], 48, 0, flute)
    lathe(bm, [(0, 2.00), (0.13, 2.00), (0.13, 2.19), (0, 2.19)], 32, 0)
    lathe(bm, [(0, 1.50), (0.045, 1.50), (0.045, 2.05), (0, 2.05)], 12, 0)
    text(bm, 'M', SERIF, 0.26, Matrix.Translation((0, 0, 2.52)), 1, 0.006, res=4)
    bmesh.ops.transform(bm, matrix=Matrix.Translation((0, 0, 0.03)) @ SWAP, verts=bm.verts)
    return make('Corona', bm, [M['acero'], M['oro']])


# ================================================================== CORREAS
def catmull(pts, n):
    P = [Vector(p) for p in pts]
    P = [P[0] * 2 - P[1]] + P + [P[-1] * 2 - P[-2]]
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for k in range(n):
            t = k / n
            out.append(0.5 * (2 * p1 + (p2 - p0) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (3 * p1 - p0 - 3 * p2 + p3) * t ** 3))
    out.append(P[-2])
    return out


def build_strap(name, ctrl, side, holes):
    bm = bmesh.new()
    path = catmull(ctrl, 14)
    L = [0.0]
    for i in range(1, len(path)):
        L.append(L[-1] + (path[i] - path[i - 1]).length)
    total = L[-1]
    sec = []
    for k in range(28):
        a = TAU * k / 28
        c, s = math.cos(a), math.sin(a)
        u, v = math.copysign(abs(c) ** 0.35, c), math.copysign(abs(s) ** 0.35, s)
        if v > 0:
            v += 0.18 * (1 - u * u) * v                 # lomo acolchado
        sec.append((u, v))
    X = Vector((side, 0, 0))

    def frame(i):
        p = path[i]
        t2 = (path[min(i + 1, len(path) - 1)] - path[max(i - 1, 0)]).normalized()
        T = Vector((0, t2.x, t2.y))
        Nn = X.cross(T).normalized()
        f = L[i] / total
        hw, ht = 0.96 - 0.16 * f, 0.16 - 0.03 * f
        rem = total - L[i]
        if rem < hw:                                    # punta redondeada
            hw *= max(0.12, math.sqrt(max(0.0, 1 - (1 - rem / hw) ** 2)))
        return Vector((0, p.x, p.y)), T, Nn, hw, ht

    rows = []
    for i in range(len(path)):
        P3, T, Nn, hw, ht = frame(i)
        rows.append([bm.verts.new(P3 + X * (u * hw) + Nn * (v * ht)) for u, v in sec])
    for i in range(len(rows) - 1):
        A, B = rows[i], rows[i + 1]
        for k in range(len(sec)):
            l = (k + 1) % len(sec)
            face(bm, (A[k], A[l], B[l], B[k]), 0)
    face(bm, rows[0], 0)
    face(bm, rows[-1][::-1], 0)

    def at(s):
        i = max(1, min(len(L) - 1, next((j for j, l in enumerate(L) if l >= s), len(L) - 1)))
        return frame(i)

    s = 0.35
    while s < total - 0.75:                             # pespunte en ambos bordes
        P3, T, Nn, hw, ht = at(s)
        for sg in (1, -1):
            box(bm, P3 + X * (sg * (hw - 0.12)) + Nn * (ht * 1.04 + 0.004), T, X, Nn, 0.10, 0.022, 0.012, 1)
        s += 0.17
    if holes:
        for j in range(5):
            P3, T, Nn, hw, ht = at(total - 1.15 - j * 0.42)
            vs = prism(bm, circ(0.065, 18), 0, 0.006, 2)
            bmesh.ops.transform(bm, matrix=basis(X, T, Nn, P3 + Nn * (ht * 1.16)), verts=vs)
    return make(name, bm, [M['cuero'], M['costura'], M['ojal']], smooth=40)


def build_straps():
    top = [(2.30, -0.08), (2.85, -0.20), (3.40, -0.48), (3.82, -0.92), (4.08, -1.50), (4.16, -2.15), (4.06, -2.80), (3.84, -3.35)]
    build_strap('Correa_Superior', top, 1, True)
    bot = [(-y, z) for y, z in top[:-1]]
    build_strap('Correa_Inferior', bot, -1, False)


# ================================================================== luces, cámara y despiece animado
EXPLODE = {
    'Cristal': (0, 0, 4.6), 'Bisel': (0, 0, 3.8),
    'Aguja_Segundos': (0, 0, 3.25), 'Aguja_Minutos': (0, 0, 2.95), 'Aguja_Horas': (0, 0, 2.65),
    'Esfera': (0, 0, 2.0), 'Corona': (1.6, 0, 0),
    'Puente': (0, 0, 1.3), 'Puente_Volante': (0, 0, 1.3),
    'Trinquete': (0, 0, 1.0), 'Ancora': (0, 0, 0.95), 'Rueda_Escape': (0, 0, 0.9), 'Volante': (0, 0, 0.85),
    'Rueda_Segundos': (0, 0, 0.8), 'Rueda_Tercera': (0, 0, 0.7), 'Barrilete': (0, 0, 0.65), 'Rueda_Centro': (0, 0, 0.55),
    'Rotor': (0, 0, -1.5), 'Fondo': (0, 0, -2.5),
    'Correa_Superior': (0, 0.6, 0), 'Correa_Inferior': (0, -0.6, 0),
}


def scene_setup():
    sc = bpy.context.scene
    try:
        sc.render.engine = 'BLENDER_EEVEE'
    except TypeError:
        pass
    if hasattr(sc.eevee, 'use_raytracing'):
        sc.eevee.use_raytracing = True
    w = sc.world or bpy.data.worlds.new('World')
    sc.world = w
    w.use_nodes = True
    bg = next(n for n in w.node_tree.nodes if n.type == 'BACKGROUND')
    bg.inputs[0].default_value = (0.012, 0.011, 0.010, 1)

    def area(name, loc, size, energy, color):
        L = bpy.data.lights.new(name, 'AREA')
        L.size, L.energy, L.color = size, energy, color
        o = bpy.data.objects.new(name, L)
        COL.objects.link(o)
        o.location = loc
        o.rotation_euler = (-Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    area('Luz_Clave', (-5, -6, 9), 6, 2500, (1.0, 0.95, 0.88))
    area('Luz_Relleno', (8, -3, 4), 8, 900, (0.85, 0.9, 1.0))
    area('Luz_Contra', (0, 8, 6), 5, 1800, (1.0, 0.85, 0.6))
    cam = bpy.data.cameras.new('Camara')
    cam.lens = 85
    co = bpy.data.objects.new('Camara', cam)
    COL.objects.link(co)
    co.location = (7.0, -10.5, 11.0)
    co.rotation_euler = (Vector((0, 0, -0.4)) - co.location).to_track_quat('-Z', 'Y').to_euler()
    sc.camera = co


def animate():
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 1, 160
    for name, off in EXPLODE.items():
        o = bpy.data.objects[name]
        base = o.location.copy()
        for f, k in ((1, 0), (20, 0), (70, 1), (110, 1), (150, 0), (160, 0)):
            o.location = base + Vector(off) * k
            o.keyframe_insert('location', frame=f)
        o.location = base
    sc.frame_set(1)


def viewport():
    for win in bpy.context.window_manager.windows:
        for area in win.screen.areas:
            if area.type == 'VIEW_3D':
                sp = area.spaces.active
                sp.shading.type = 'MATERIAL'
                sp.region_3d.view_perspective = 'PERSP'
                sp.region_3d.view_location = (0, 0, -0.3)
                sp.region_3d.view_distance = 15
                sp.region_3d.view_rotation = Euler((math.radians(55), 0, math.radians(32))).to_quaternion()


build_case()
build_bezel()
build_crystal()
build_dial()
build_hands()
build_movement()
build_rotor()
build_caseback()
build_crown()
build_straps()
scene_setup()
animate()
viewport()

# la hora clásica de catálogo: 10:10:38 (en la web marcan la hora real)
for name, deg in (('Aguja_Horas', 305), ('Aguja_Minutos', 60), ('Aguja_Segundos', 228)):
    bpy.data.objects[name].rotation_euler.z = -math.radians(deg)

def export(path=r'C:\Users\Leia\Documents\GitHub\landings-3d\assets\3d\morvic.glb'):
    """GLB con EXT_meshopt_compression (la web lo decodifica sin Workers). Luego se incrusta en morvic-data.js."""
    bpy.context.scene.frame_set(1)
    bpy.ops.object.select_all(action='DESELECT')
    for o in bpy.data.objects:
        o.select_set(o.type == 'MESH')
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', use_selection=True, export_apply=True,
                              export_yup=True, export_lights=False, export_cameras=False, export_animations=False,
                              export_meshopt_compression_enable=True, export_meshopt_extension='EXT_meshopt_compression')
    bpy.ops.object.select_all(action='DESELECT')


tris = sum(len(o.data.polygons) for o in bpy.data.objects if o.type == 'MESH')
print('objetos', sorted(o.name for o in bpy.data.objects if o.type == 'MESH'))
print('caras', tris)
