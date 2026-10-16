# Gambito — juego de ajedrez moderno modelado 100 % por código para la landing gambito.html.
# Unidades: 1 = una casilla (55 mm). El tablero está centrado en el origen con la superficie en z = 0;
# las blancas juegan desde y negativa. Cada pieza tiene su origen en el centro de la base.
import bpy, bmesh, math, os
from mathutils import Matrix, Vector

TAU = math.tau
SERIF = r'C:\Windows\Fonts\BOD_R.TTF'          # Bodoni MT
Z = Vector((0, 0, 1))
SWAP = Matrix(((0, 0, 1, 0), (1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 0, 1)))   # local (a,b,c) -> mundo (c,a,b)
OUT_GLB = r'C:\Users\Leia\Documents\GitHub\landings-3d\assets\3d\gambito.glb'


def reset():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.curves, bpy.data.cameras,
                 bpy.data.lights, bpy.data.fonts, bpy.data.actions, bpy.data.collections):
        for b in list(coll):
            if b.users == 0:
                coll.remove(b)


reset()
COL = bpy.context.scene.collection


# ------------------------------------------------------------------ materiales
def sock(node, ident):
    return next(s for s in node.inputs if s.identifier == ident)


def mat(name, color, metal=0.0, rough=0.5, coat=0.0, sheen=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    sock(b, 'Base Color').default_value = (*color, 1)
    sock(b, 'Metallic').default_value = metal
    sock(b, 'Roughness').default_value = rough
    sock(b, 'Coat Weight').default_value = coat
    sock(b, 'Sheen Weight').default_value = sheen
    m.diffuse_color = (*color, 1)
    return m


M = dict(
    blancas=mat('Blancas', (0.80, 0.62, 0.40), 0.0, 0.32, coat=0.5),
    negras=mat('Negras', (0.018, 0.011, 0.008), 0.0, 0.28, coat=0.8),
    clara=mat('CasillaClara', (0.72, 0.52, 0.30), 0.0, 0.38, coat=0.4),
    oscura=mat('CasillaOscura', (0.11, 0.055, 0.028), 0.0, 0.36, coat=0.4),
    marco=mat('Marco', (0.07, 0.04, 0.022), 0.0, 0.4, coat=0.4),
    laton=mat('Laton', (0.86, 0.66, 0.36), 1.0, 0.28),
    grabado=mat('Grabado', (0.92, 0.74, 0.44), 0.8, 0.35),
    fieltro=mat('Fieltro', (0.03, 0.12, 0.07), 0.0, 1.0, sheen=1.0),
    plomo=mat('Contrapeso', (0.30, 0.31, 0.33), 1.0, 0.5),
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
    bot = [bm.verts.new((x, y, z0)) for x, y in pts]
    top = [bm.verts.new((x, y, z1)) for x, y in pts]
    face(bm, top, mi)
    face(bm, bot[::-1], mi)
    for i in range(len(pts)):
        j = (i + 1) % len(pts)
        face(bm, (bot[i], bot[j], top[j], top[i]), mi)
    return bot + top


def ring(bm, outer, inner, z0, z1, mi=0):
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


def lathe(bm, prof, segs=64, mi=0):
    rows = []
    for r, z in prof:
        if r < 1e-6:
            v = bm.verts.new((0, 0, z))
            rows.append([v] * segs)
        else:
            rows.append([bm.verts.new((r * math.cos(TAU * k / segs), r * math.sin(TAU * k / segs), z)) for k in range(segs)])
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


def sphere(r, zc, a0=-90, a1=90, n=12):
    return [(max(0.0, r * math.cos(math.radians(a0 + (a1 - a0) * i / n))), zc + r * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]


def box(bm, c, size, mi=0):
    (cx, cy, cz), (sx, sy, sz) = c, size
    return prism(bm, [(cx - sx / 2, cy - sy / 2), (cx + sx / 2, cy - sy / 2), (cx + sx / 2, cy + sy / 2), (cx - sx / 2, cy + sy / 2)],
                 cz - sz / 2, cz + sz / 2, mi)


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


def text(bm, body, size, Mx, mi=0, extrude=0.003, spacing=1.0, res=4):
    if SERIF not in FONTS:
        FONTS[SERIF] = bpy.data.fonts.load(SERIF, check_existing=True)
    cu = bpy.data.curves.new('tmp_txt', 'FONT')
    cu.body, cu.font, cu.size, cu.extrude = body, FONTS[SERIF], size, extrude
    cu.align_x, cu.align_y, cu.space_character, cu.resolution_u = 'CENTER', 'CENTER', spacing, res
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


def make(name, bm, mats, loc=(0, 0, 0), smooth=35):
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


def cut(ob, cutter_bm):
    """Resta (booleana) la malla del cortador al objeto y deja el resultado aplicado."""
    me = bpy.data.meshes.new('cortador')
    cutter_bm.to_mesh(me)
    cutter_bm.free()
    cutter = bpy.data.objects.new('cortador', me)
    COL.objects.link(cutter)
    mod = ob.modifiers.new('corte', 'BOOLEAN')
    mod.operation, mod.object = 'DIFFERENCE', cutter
    bpy.context.view_layer.update()
    new = bpy.data.meshes.new_from_object(ob.evaluated_get(bpy.context.evaluated_depsgraph_get()))
    old = ob.data
    ob.modifiers.remove(mod)
    ob.data = new
    bpy.data.meshes.remove(old)
    bpy.data.objects.remove(cutter)
    bpy.data.meshes.remove(me)
    new.name = ob.name
    new.validate()
    bm = bmesh.new()                                    # limpia restos del corte booleano
    bm.from_mesh(new)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=1e-5)
    bm.to_mesh(new)
    bm.free()
    new.shade_smooth()
    new.set_sharp_from_angle(angle=math.radians(35))


def weighted(ob):
    """Normales ponderadas por área: las caras planas grandes quedan planas y los biseles suaves."""
    mod = ob.modifiers.new('normales', 'WEIGHTED_NORMAL')
    mod.keep_sharp = True
    mod.weight = 100
    bpy.context.view_layer.update()
    new = bpy.data.meshes.new_from_object(ob.evaluated_get(bpy.context.evaluated_depsgraph_get()))
    old = ob.data
    ob.modifiers.remove(mod)
    ob.data = new
    bpy.data.meshes.remove(old)
    new.name = ob.name


# ================================================================== PIEZAS (perfiles torneados)
BASE = lambda R: [(0, 0), (R, 0), (R, 0.05), (R - 0.015, 0.075), (R - 0.06, 0.09), (R - 0.105, 0.115)]


def build_pawn():
    bm = bmesh.new()
    prof = BASE(0.30) + [(0.175, 0.13), (0.145, 0.19), (0.125, 0.28), (0.112, 0.38), (0.108, 0.44), (0.17, 0.46),
                         (0.175, 0.48), (0.17, 0.50), (0.10, 0.515)] + sphere(0.155, 0.66, -62, 90, 14)
    lathe(bm, prof)
    return make('Peon', bm, [M['blancas']])


def build_rook():
    bm = bmesh.new()
    lathe(bm, BASE(0.33) + [(0.195, 0.16), (0.18, 0.26), (0.17, 0.50), (0.172, 0.66), (0.185, 0.72), (0.235, 0.75), (0.245, 0.78),
                            (0.24, 0.80), (0.23, 0.82), (0.23, 0.96), (0.165, 0.96), (0.165, 0.89), (0, 0.89)])
    ob = make('Torre', bm, [M['blancas']])
    c = bmesh.new()                                     # almenas: dos cortes en cruz
    box(c, (0, 0, 0.96), (0.075, 0.7, 0.14))
    box(c, (0, 0, 0.96), (0.7, 0.075, 0.14))
    cut(ob, c)
    return ob


def build_bishop():
    bm = bmesh.new()
    lathe(bm, BASE(0.32) + [(0.18, 0.16), (0.14, 0.28), (0.115, 0.46), (0.10, 0.60), (0.097, 0.66), (0.175, 0.68), (0.18, 0.70),
                            (0.175, 0.72), (0.10, 0.735), (0.105, 0.75), (0.135, 0.79), (0.158, 0.86), (0.16, 0.92), (0.148, 0.99),
                            (0.12, 1.06), (0.08, 1.12), (0.035, 1.155), (0, 1.16)])
    lathe(bm, sphere(0.05, 1.205, n=10), 32)
    ob = make('Alfil', bm, [M['blancas']])
    c = bmesh.new()                                     # la ranura diagonal de la mitra
    vs = box(c, (0, 0, 0), (0.035, 0.6, 0.34))
    bmesh.ops.transform(c, matrix=Matrix.Translation((0.07, 0, 0.98)) @ Matrix.Rotation(math.radians(-42), 4, 'Y'), verts=vs)
    cut(ob, c)
    return ob


def build_queen():
    bm = bmesh.new()
    lathe(bm, BASE(0.35) + [(0.235, 0.12), (0.195, 0.17), (0.15, 0.32), (0.125, 0.55), (0.112, 0.80), (0.108, 0.90), (0.195, 0.925),
                            (0.2, 0.95), (0.195, 0.97), (0.11, 0.985), (0.115, 1.0), (0.15, 1.06), (0.2, 1.15), (0.225, 1.21),
                            (0.222, 1.245), (0.19, 1.255), (0.15, 1.25), (0.11, 1.235), (0, 1.235)])
    for k in range(8):                                  # corona de perlas
        a = TAU * k / 8
        vs = lathe(bm, sphere(0.042, 0, n=8), 20)
        bmesh.ops.translate(bm, vec=(0.195 * math.cos(a), 0.195 * math.sin(a), 1.262), verts=vs)
    lathe(bm, sphere(0.09, 1.28, 0, 90, 8), 48)
    lathe(bm, sphere(0.04, 1.39, n=8), 24)
    return make('Dama', bm, [M['blancas']])


def build_king():
    bm = bmesh.new()
    lathe(bm, BASE(0.36) + [(0.245, 0.12), (0.205, 0.17), (0.158, 0.34), (0.13, 0.62), (0.118, 0.92), (0.115, 1.0), (0.205, 1.025),
                            (0.21, 1.05), (0.205, 1.07), (0.12, 1.085), (0.125, 1.10), (0.165, 1.17), (0.21, 1.27), (0.225, 1.33),
                            (0.2, 1.355), (0.15, 1.37), (0.1, 1.40), (0.07, 1.43), (0, 1.435)])
    cross = bmesh.new()
    box(cross, (0, 0, 1.565), (0.075, 0.075, 0.30))
    box(cross, (0, 0, 1.60), (0.23, 0.075, 0.075))
    bevel(cross, 0.014, 2, 30)
    merge(bm, cross)
    return make('Rey', bm, [M['blancas']])


def build_knight():
    bm = bmesh.new()
    lathe(bm, BASE(0.33) + [(0.225, 0.115), (0.205, 0.16), (0.2, 0.22), (0, 0.22)])
    head = bmesh.new()                                  # cabeza estilizada: silueta extruida y biselada
    prof = [(-0.26, 0.20), (0.20, 0.20), (0.18, 0.30), (0.10, 0.44), (0.04, 0.56), (0.10, 0.62), (0.26, 0.66), (0.40, 0.70),
            (0.46, 0.76), (0.47, 0.83), (0.42, 0.88), (0.26, 0.95), (0.16, 1.02), (0.12, 1.12), (0.08, 1.20), (0.03, 1.12),
            (-0.06, 1.08), (-0.18, 1.00), (-0.28, 0.86), (-0.34, 0.66), (-0.34, 0.46), (-0.30, 0.30)]
    prism(head, prof, -0.12, 0.12)
    bmesh.ops.transform(head, matrix=SWAP, verts=head.verts)
    bevel(head, 0.035, 3, 25)
    merge(bm, head)
    ob = make('Caballo', bm, [M['blancas']], smooth=50)
    weighted(ob)
    return ob


def build_felt_and_weight():
    bm = bmesh.new()
    lathe(bm, [(0, -0.012), (1.0, -0.012), (1.0, 0.001), (0, 0.001)], 64)
    make('Fieltro', bm, [M['fieltro']], smooth=60)
    bm = bmesh.new()
    lathe(bm, [(0, 0), (1.0, 0), (1.0, 0.07), (0.94, 0.085), (0, 0.085)], 48)
    make('Contrapeso', bm, [M['plomo']])


# ================================================================== TABLERO
def build_board():
    bm = bmesh.new()
    g = 0.004                                           # junta entre casillas taraceadas
    for f in range(8):
        for r in range(8):
            x, y = f - 3.5, r - 3.5
            prism(bm, [(x - 0.5 + g, y - 0.5 + g), (x + 0.5 - g, y - 0.5 + g), (x + 0.5 - g, y + 0.5 - g), (x - 0.5 + g, y + 0.5 - g)],
                  -0.05, 0.0, 1 if (f + r) % 2 == 0 else 0)
    sq = lambda s: [(-s, -s), (s, -s), (s, s), (-s, s)]
    prism(bm, sq(4.0), -0.27, -0.049, 2)
    ring(bm, sq(4.06), sq(4.0), -0.05, 0.004, 3)        # filete de latón
    frame = bmesh.new()
    ring(frame, sq(4.62), sq(4.06), -0.30, 0.018, 2)
    bevel(frame, 0.035, 3, 30)
    merge(bm, frame)
    prism(bm, sq(4.48), -0.40, -0.29, 2)                # zócalo retranqueado
    for i, ch in enumerate('abcdefgh'):                 # notación grabada en oro
        text(bm, ch, 0.2, Matrix.Translation((i - 3.5, -4.34, 0.02)), 4)
        text(bm, ch, 0.2, Matrix.Translation((i - 3.5, 4.34, 0.02)) @ Matrix.Rotation(math.pi, 4, 'Z'), 4)
    for i in range(8):
        text(bm, str(i + 1), 0.2, Matrix.Translation((-4.34, i - 3.5, 0.02)), 4)
        text(bm, str(i + 1), 0.2, Matrix.Translation((4.34, i - 3.5, 0.02)) @ Matrix.Rotation(math.pi, 4, 'Z'), 4)
    front = Matrix(((1, 0, 0, 0), (0, 0, -1, -4.623), (0, 1, 0, -0.14), (0, 0, 0, 1)))   # en el canto, mirando a las blancas
    text(bm, 'GAMBITO', 0.12, front, 4, 0.003, 2.2)
    return make('Tablero', bm, [M['clara'], M['oscura'], M['marco'], M['laton'], M['grabado']])


# ================================================================== escena para verlo en Blender
ORDER = ['Torre', 'Caballo', 'Alfil', 'Dama', 'Rey', 'Alfil', 'Caballo', 'Torre']


def setup_position(protos):
    for f, name in enumerate(ORDER):
        for side, rank, pawn_rank in (('w', 0, 1), ('b', 7, 6)):
            for kind, rk in ((name, rank), ('Peon', pawn_rank)):
                src = protos[kind]
                o = bpy.data.objects.new(f'{kind}_{side}{"abcdefgh"[f]}{rk + 1}', src.data)
                COL.objects.link(o)
                o.location = (f - 3.5, rk - 3.5, 0.012)
                if side == 'b':
                    o.material_slots[0].link = 'OBJECT'
                    o.material_slots[0].material = M['negras']
                    o.rotation_euler.z = math.pi
                if kind == 'Caballo':                   # de perfil, mirando al centro del tablero
                    o.rotation_euler.z = -math.pi / 2 if f < 4 else math.pi / 2


def scene_setup():
    sc = bpy.context.scene
    try:
        sc.render.engine = 'BLENDER_EEVEE'
    except TypeError:
        pass
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
    area('Luz_Clave', (-6, -8, 12), 8, 6000, (1.0, 0.95, 0.88))
    area('Luz_Contra', (4, 10, 7), 6, 3000, (1.0, 0.85, 0.6))
    cam = bpy.data.cameras.new('Camara')
    cam.lens = 50
    co = bpy.data.objects.new('Camara', cam)
    COL.objects.link(co)
    co.location = (9, -13, 10)
    co.rotation_euler = (Vector((0, -0.5, 0)) - co.location).to_track_quat('-Z', 'Y').to_euler()
    sc.camera = co
    for win in bpy.context.window_manager.windows:
        for ar in win.screen.areas:
            if ar.type == 'VIEW_3D':
                sp = ar.spaces.active
                sp.shading.type = 'MATERIAL'
                sp.region_3d.view_perspective = 'PERSP'
                sp.region_3d.view_location = (0, -1.2, 0)
                sp.region_3d.view_distance = 19
                sp.region_3d.view_rotation = (Vector((0.62, -0.62, 0.48)).normalized() * -1).to_track_quat('-Z', 'Z')


def export():
    """GLB con EXT_meshopt_compression: solo los prototipos (la web los clona 32 veces)."""
    bpy.ops.object.select_all(action='DESELECT')
    for n in ('Rey', 'Dama', 'Torre', 'Alfil', 'Caballo', 'Peon', 'Tablero', 'Fieltro', 'Contrapeso'):
        bpy.data.objects[n].select_set(True)
    bpy.ops.export_scene.gltf(filepath=OUT_GLB, export_format='GLB', use_selection=True, export_apply=True,
                              export_yup=True, export_lights=False, export_cameras=False, export_animations=False,
                              export_meshopt_compression_enable=True, export_meshopt_extension='EXT_meshopt_compression')
    bpy.ops.object.select_all(action='DESELECT')


protos = dict(Peon=build_pawn(), Torre=build_rook(), Alfil=build_bishop(), Dama=build_queen(), Rey=build_king(), Caballo=build_knight())
build_felt_and_weight()
build_board()
export()
# prototipos en fila delante del tablero (catálogo) y la posición inicial sobre el tablero
for i, n in enumerate(('Rey', 'Dama', 'Alfil', 'Caballo', 'Torre', 'Peon')):
    protos[n].location = (i * 1.1 - 2.75, -6.6, 0)
for n in ('Fieltro', 'Contrapeso'):
    bpy.data.objects[n].hide_set(True)
    bpy.data.objects[n].hide_render = True
setup_position(protos)
scene_setup()
print('glb KB', os.path.getsize(OUT_GLB) // 1024)
print('caras', sum(len(o.data.polygons) for o in bpy.data.objects if o.type == 'MESH' and o.name in
                   ('Rey', 'Dama', 'Torre', 'Alfil', 'Caballo', 'Peon', 'Tablero', 'Fieltro', 'Contrapeso')))
