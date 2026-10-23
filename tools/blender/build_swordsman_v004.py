# Наследие глубин — модульный low-poly мечник, v004
# Blender 4.2+ (собрано в 5.2). Скрипт полностью пересобирает сцену и пишет результат в art/characters/swordsman/v004/.
# Запуск в открытом Blender:  exec(open(PATH, encoding='utf-8').read(), {'__file__': PATH, 'STAGE': 'all'})
# Запуск из консоли:          blender --background --python tools/blender/build_swordsman_v004.py
# STAGE: 'build' — только модель; 'all' — модель + превью + экспорт FBX + .blend + отчёт.
import bpy, bmesh, math, os, json
from mathutils import Vector as V, Matrix, Quaternion

STAGE = globals().get('STAGE', 'all')
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
OUT = os.path.join(ROOT, 'art', 'characters', 'swordsman', 'v004')
os.makedirs(OUT, exist_ok=True)
FWD = V((0, -1, 0))
UP = V((0, 0, 1))
rad = math.radians

# ------------------------------------------------------------------ helpers
def lerp(a, b, t): return a + (b - a) * t

def interp(xs, ys, x):
    if x <= xs[0]: return ys[0]
    for i in range(len(xs) - 1):
        if x <= xs[i + 1]:
            return lerp(ys[i], ys[i + 1], (x - xs[i]) / (xs[i + 1] - xs[i]))
    return ys[-1]

def along(pts, t):
    i = max(0, min(int(math.floor(t)), len(pts) - 2))
    return pts[i].lerp(pts[i + 1], t - i)

def tan_at(pts, t):
    k = round(t)
    if abs(t - k) < 1e-6 and 0 < k < len(pts) - 1:
        return ((pts[k] - pts[k - 1]).normalized() + (pts[k + 1] - pts[k]).normalized()).normalized()
    i = max(0, min(int(math.floor(t)), len(pts) - 2))
    return (pts[i + 1] - pts[i]).normalized()

def frame(n, fwd=FWD):
    n = n.normalized()
    f = fwd - n * fwd.dot(n)
    if f.length < 1e-5:
        f = UP - n * n.z
    f.normalize()
    return n.cross(f).normalized(), f

def ring(c, n, a, b, segs, fwd=FWD):
    u, f = frame(n, fwd)
    return [c + u * (a * math.cos(2 * math.pi * i / segs)) + f * (b * math.sin(2 * math.pi * i / segs)) for i in range(segs)]

def ring_axes(c, u, f, a, b, segs):
    return [c + u * (a * math.cos(2 * math.pi * i / segs)) + f * (b * math.sin(2 * math.pi * i / segs)) for i in range(segs)]

def ring_egg(c, a, bf, bb, segs):
    out = []
    for i in range(segs):
        t = 2 * math.pi * i / segs
        s = math.sin(t)
        out.append(c + V((a * math.cos(t), -(bf if s > 0 else bb) * s, 0)))
    return out

def mirror_pts(rings):
    return [[V((-p.x, p.y, p.z)) for p in r] for r in rings]

def mv(v): return V((-v.x, v.y, v.z))

def loft(bm, rings, closed=True, cap0=False, cap1=False, mat=0, band_mats=None, cyclic=False):
    vs = [[bm.verts.new(p) for p in r] for r in rings]
    faces = []
    nb = len(vs) if cyclic else len(vs) - 1
    for i in range(nb):
        A, B = vs[i], vs[(i + 1) % len(vs)]
        m = band_mats[i] if band_mats else mat
        if len(A) == 1 or len(B) == 1:
            rr, pole, rev = (A, B[0], False) if len(B) == 1 else (B, A[0], True)
            n = len(rr)
            for j in range(n if closed else n - 1):
                q = (rr[j], rr[(j + 1) % n], pole)
                f = bm.faces.new(q[::-1] if rev else q); f.material_index = m; faces.append(f)
            continue
        n = len(A)
        for j in range(n if closed else n - 1):
            f = bm.faces.new((A[j], A[(j + 1) % n], B[(j + 1) % n], B[j])); f.material_index = m; faces.append(f)
    if cap0 and len(vs[0]) > 2:
        f = bm.faces.new(vs[0][::-1]); f.material_index = band_mats[0] if band_mats else mat; faces.append(f)
    if cap1 and len(vs[-1]) > 2:
        f = bm.faces.new(vs[-1]); f.material_index = band_mats[-1] if band_mats else mat; faces.append(f)
    return vs, faces

def ellipsoid(bm, c, r, segs=8, rings=5, mat=0, rot=None):
    R = rot or Matrix.Identity(3)
    rs = [[c + R @ V((0, 0, -r[2]))]]
    for k in range(1, rings):
        ph = -math.pi / 2 + math.pi * k / rings
        rs.append([c + R @ V((r[0] * math.cos(ph) * math.cos(2 * math.pi * i / segs),
                              r[1] * math.cos(ph) * math.sin(2 * math.pi * i / segs),
                              r[2] * math.sin(ph))) for i in range(segs)])
    rs.append([c + R @ V((0, 0, r[2]))])
    loft(bm, rs, mat=mat)

def box(bm, c, half, mat=0, rot=None):
    R = (rot or Matrix.Identity(3)).to_4x4()
    m = Matrix.Translation(c) @ R @ Matrix.Diagonal((half[0] * 2, half[1] * 2, half[2] * 2, 1))
    res = bmesh.ops.create_cube(bm, size=1.0, matrix=m)
    for f in {f for v in res['verts'] for f in v.link_faces}:
        f.material_index = mat

def basis_from_normal(nrm):
    x = UP.cross(nrm).normalized()
    z = nrm.cross(x).normalized()
    return Matrix((x, nrm, z)).transposed()

def fix_normals(bm, island=True):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    if not island:
        return
    bm.normal_update()
    seen = set()
    for f0 in bm.faces:
        if f0 in seen: continue
        isl, stack = [], [f0]; seen.add(f0)
        while stack:
            f = stack.pop(); isl.append(f)
            for e in f.edges:
                for g in e.link_faces:
                    if g not in seen:
                        seen.add(g); stack.append(g)
        cen = V()
        for f in isl: cen += f.calc_center_median()
        cen /= len(isl)
        score = sum(f.normal.dot(f.calc_center_median() - cen) * f.calc_area() for f in isl)
        if score < 0:
            bmesh.ops.reverse_faces(bm, faces=isl)
    bm.normal_update()

def shell(bm, th, mat_in, mat_rim):
    bm.normal_update()
    faces, verts = bm.faces[:], bm.verts[:]
    bnd = [e for e in bm.edges if e.is_boundary]
    nv = {v: bm.verts.new(v.co - v.normal * th) for v in verts}
    for f in faces:
        g = bm.faces.new([nv[v] for v in reversed(f.verts)]); g.material_index = mat_in
    for e in bnd:
        f = e.link_faces[0]
        for l in f.loops:
            if l.edge == e:
                a, b = l.vert, l.link_loop_next.vert
                break
        g = bm.faces.new((b, a, nv[a], nv[b])); g.material_index = mat_rim

# ------------------------------------------------------------------ palette
PALETTE = {
    'Skin': (0.86, 0.67, 0.55), 'Hair': (0.22, 0.14, 0.10), 'Coat': (0.17, 0.13, 0.12),
    'Lining': (0.55, 0.09, 0.10), 'Shirt': (0.09, 0.08, 0.08), 'Trousers': (0.12, 0.11, 0.11),
    'Leather': (0.30, 0.19, 0.13), 'Sole': (0.14, 0.10, 0.08), 'Steel': (0.75, 0.77, 0.80),
    'Brass': (0.62, 0.46, 0.24), 'Eye': (0.10, 0.06, 0.05), 'Mouth': (0.50, 0.30, 0.27),
    'Grip': (0.30, 0.17, 0.11),
}
MAT = {}

def srgb2lin(c): return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

def principled(m):
    try: m.use_nodes = True
    except Exception: pass
    nt = m.node_tree
    p = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    out = next((n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL'), None)
    if out is None: out = nt.nodes.new('ShaderNodeOutputMaterial')
    if p is None:
        p = nt.nodes.new('ShaderNodeBsdfPrincipled')
        nt.links.new(p.outputs[0], out.inputs['Surface'])
    return p

def make_material(name, srgb, metal=False):
    m = bpy.data.materials.new(name)
    lin = tuple(srgb2lin(x) for x in srgb) + (1.0,)
    m.diffuse_color = lin
    p = principled(m)
    p.inputs['Base Color'].default_value = lin
    p.inputs['Roughness'].default_value = 0.45 if metal else 0.85
    p.inputs['Metallic'].default_value = 0.8 if metal else 0.0
    return m

def make_materials():
    for k, c in PALETTE.items():
        MAT[k] = make_material('M_SW_' + k, c, metal=k in ('Steel', 'Brass'))

# ------------------------------------------------------------------ proportions (A-pose, +X = character's left, faces -Y)
ARM_A = rad(40)
SH = V((0.200, 0.01, 1.42))
HAND_S = 1.25
DUA = V((math.sin(ARM_A), 0, -math.cos(ARM_A)))
EL = SH + DUA * 0.28 + V((0, 0.012, 0))
DFA = V((math.sin(ARM_A + rad(3)), 0, -math.cos(ARM_A + rad(3))))
WR = EL + DFA * 0.25 + V((0, -0.025, 0))
HDIR = (WR - EL).normalized()
HE = WR + HDIR * (0.11 * HAND_S)
TTH = (FWD - HDIR * FWD.dot(HDIR)).normalized()   # thumb direction
PALM = HDIR.cross(TTH).normalized()                # palm normal (towards body)
GRIP = WR + HDIR * (0.080 * HAND_S) + PALM * (0.018 * HAND_S)            # fist centre = weapon socket
BDIR = (TTH * math.cos(rad(15)) + HDIR * math.sin(rad(15))).normalized()
GX = (HDIR - BDIR * HDIR.dot(BDIR)).normalized()
ARM = [SH, EL, WR]

HIP = V((0.100, 0.0, 0.915)); KNEE = V((0.112, -0.012, 0.49)); ANK = V((0.124, 0.02, 0.085))
BALL = V((0.127, -0.10, 0.03)); TOE = V((0.13, -0.175, 0.03))
LEG = [HIP + V((0, 0, 0.05)), HIP, KNEE, ANK]
FOOT_X = 0.126

def leg_axis(z):
    t = (z - ANK.z) / (KNEE.z - ANK.z)
    return ANK.lerp(KNEE, t)

# ------------------------------------------------------------------ skeleton
BONES = {}
def bone(name, h, t, parent=None, connect=False, deform=True):
    BONES[name] = (V(h), V(t), parent, connect, deform)

def define_bones():
    BONES.clear()
    bone('Root', (0, 0, 0), (0, 0.25, 0), deform=False)
    bone('Hips', (0, 0.005, 0.915), (0, 0.005, 1.03), 'Root')
    bone('Spine', (0, 0.005, 1.03), (0, 0.0, 1.18), 'Hips', True)
    bone('Chest', (0, 0.0, 1.18), (0, 0.01, 1.44), 'Spine', True)
    bone('Neck', (0, 0.01, 1.44), (0, 0.012, 1.53), 'Chest', True)
    bone('Head', (0, 0.012, 1.53), (0, 0.012, 1.795), 'Neck', True)
    for s, sx in (('L', 1), ('R', -1)):
        f = (lambda v: V(v)) if sx > 0 else (lambda v: mv(V(v)))
        bone('Shoulder.' + s, f((0.025, 0.005, 1.405)), f(SH), 'Chest')
        bone('UpperArm.' + s, f(SH), f(EL), 'Shoulder.' + s, True)
        bone('LowerArm.' + s, f(EL), f(WR), 'UpperArm.' + s, True)
        bone('Hand.' + s, f(WR), f(HE), 'LowerArm.' + s, True)
        bone('UpperLeg.' + s, f(HIP), f(KNEE), 'Hips')
        bone('LowerLeg.' + s, f(KNEE), f(ANK), 'UpperLeg.' + s, True)
        bone('Foot.' + s, f(ANK), f(BALL), 'LowerLeg.' + s, True)
        bone('Toes.' + s, f(BALL), f(TOE), 'Foot.' + s, True)
        bone('CoatFront1.' + s, f((0.115, -0.125, 0.975)), f((0.15, -0.135, 0.70)), 'Hips')
        bone('CoatFront2.' + s, f((0.15, -0.135, 0.70)), f((0.175, -0.155, 0.43)), 'CoatFront1.' + s, True)
        bone('CoatBack1.' + s, f((0.085, 0.135, 0.975)), f((0.11, 0.15, 0.70)), 'Hips')
        bone('CoatBack2.' + s, f((0.11, 0.15, 0.70)), f((0.13, 0.17, 0.43)), 'CoatBack1.' + s, True)
    bone('WeaponSocket.R', mv(GRIP), mv(GRIP + BDIR * 0.12), 'Hand.R', deform=False)

RADIUS = {'Hips': .16, 'Spine': .16, 'Chest': .17, 'Neck': .05, 'Head': .07, 'Shoulder': .06,
          'UpperArm': .055, 'LowerArm': .045, 'Hand': .04, 'UpperLeg': .085, 'LowerLeg': .06,
          'Foot': .05, 'Toes': .04, 'CoatFront1': .10, 'CoatFront2': .10, 'CoatBack1': .10, 'CoatBack2': .10}

def build_rig(coll):
    arm = bpy.data.armatures.new('Swordsman_Rig')
    ob = bpy.data.objects.new('Swordsman_Rig', arm)
    coll.objects.link(ob)
    arm.display_type = 'STICK'
    ob.show_in_front = True
    for o in bpy.context.selected_objects: o.select_set(False)
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    eb = arm.edit_bones
    for name, (h, t, parent, connect, deform) in BONES.items():
        b = eb.new(name); b.head = h; b.tail = t; b.use_deform = deform
        if parent:
            b.parent = eb[parent]; b.use_connect = connect
        b.align_roll(-FWD if abs((t - h).normalized().dot(FWD)) < 0.9 else UP)
    bpy.ops.object.mode_set(mode='OBJECT')
    return ob

def segdist(p, a, b):
    ab = b - a
    t = max(0.0, min(1.0, (p - a).dot(ab) / ab.length_squared))
    return (p - (a + ab * t)).length

def skin(ob, cands, rad_over=None, force=None):
    rad_over = rad_over or {}
    for nm in cands:
        if nm not in ob.vertex_groups: ob.vertex_groups.new(name=nm)
    for v in ob.data.vertices:
        p = v.co
        fw = force(p) if force else None
        if fw:
            ws = list(fw.items())
        else:
            ws = []
            for nm in cands:
                if nm.endswith('.L') and p.x < -0.02: continue
                if nm.endswith('.R') and p.x > 0.02: continue
                h, t = BONES[nm][0], BONES[nm][1]
                base = nm.split('.')[0]
                r = rad_over.get(base, RADIUS[base])
                d = max(segdist(p, h, t), 0.008)
                ws.append((nm, (r / d) ** 4))
            ws.sort(key=lambda x: -x[1]); ws = ws[:4]
            s = sum(w for _, w in ws); ws = [(n, w / s) for n, w in ws if w / s > 0.015]
        s = sum(w for _, w in ws)
        for nm, w in ws:
            ob.vertex_groups[nm].add([v.index], w / s, 'REPLACE')

# ------------------------------------------------------------------ objects
PARTS = {}
def make_obj(name, bm, mats, coll, slot, hides=(), sharp=None, island=True):
    fix_normals(bm, island)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me); bm.free()
    for m in mats: me.materials.append(MAT[m] if isinstance(m, str) else m)
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    me.shade_smooth()
    if sharp is not None and hasattr(me, 'set_sharp_from_angle'):
        me.set_sharp_from_angle(angle=rad(sharp))
    ob['sw_part'] = True; ob['sw_slot'] = slot; ob['sw_hides'] = ','.join(hides)
    PARTS[name] = ob
    return ob

def both(bm, rings_l, **kw):
    loft(bm, rings_l, **kw)
    loft(bm, mirror_pts(rings_l), **kw)

# --- body
TORSO = [(0.835, 0.00, 0.085, 0.065), (0.87, 0.00, 0.145, 0.090), (0.93, 0.005, 0.170, 0.105),
         (1.00, 0.005, 0.160, 0.102), (1.06, 0.005, 0.150, 0.096), (1.14, 0.0, 0.160, 0.102),
         (1.22, -0.005, 0.178, 0.110), (1.30, -0.005, 0.190, 0.114), (1.37, 0.0, 0.192, 0.106),
         (1.42, 0.005, 0.170, 0.090), (1.455, 0.01, 0.105, 0.068), (1.48, 0.012, 0.058, 0.055)]
ARM_ST = [(-0.05, .062, .060), (0.0, .068, .065), (.3, .060, .056), (.6, .054, .051), (.9, .047, .045),
          (1.0, .044, .044), (1.2, .047, .045), (1.5, .042, .040), (1.8, .035, .031), (2.0, .031, .026), (2.04, .023, .019)]
LEG_ST = [(0.0, .085), (1.0, .090), (1.15, .090), (1.4, .083), (1.65, .072), (1.85, .062), (2.0, .057),
          (2.12, .062), (2.35, .064), (2.6, .054), (2.85, .044), (3.0, .040), (3.05, .032)]
FOOT = [(0.13, 0.020, 0.046, 0.048, 0.046), (0.10, 0.000, 0.050, 0.082, 0.066), (0.07, -0.020, 0.055, 0.135, 0.086),
        (0.045, -0.030, 0.057, 0.152, 0.094), (0.022, -0.030, 0.056, 0.155, 0.094), (0.0, -0.030, 0.054, 0.150, 0.090)]
FIST = [(-0.012, .025, .019, 0), (0.020, .036, .021, 0), (0.050, .041, .023, .001), (0.075, .043, .028, .006),
        (0.095, .040, .030, .010), (0.110, .031, .025, .012), (0.118, .014, .012, .010)]
GLOVE = [(-0.046, .040, .036, 0), (-0.036, .043, .039, 0), (-0.012, .031, .025, 0), (0.020, .040, .025, 0),
         (0.050, .045, .027, .001), (0.072, .047, .032, .005), (0.080, .040, .028, .006)]

def tube_on(pts, stations, segs, ofs=0.0):
    return [ring(along(pts, t), tan_at(pts, t), a + ofs, b + ofs, segs) for t, a, b in stations]

def thumb_pts():
    b0 = WR + HDIR * 0.022 + TTH * 0.024 + PALM * 0.006
    b1 = WR + HDIR * 0.058 + TTH * 0.034 + PALM * 0.026
    b2 = WR + HDIR * 0.085 + TTH * 0.026 + PALM * 0.036
    return [WR + (b - WR) * HAND_S for b in (b0, b1, b2)]

def fist_rings(rows, segs):
    k = HAND_S
    return [ring_axes(WR + HDIR * (s * k) + PALM * (c * k), TTH, PALM, wt * k, th * k, segs) for s, wt, th, c in rows]

def build_body(C):
    bm = bmesh.new()
    loft(bm, [ring(V((0, cy, z)), UP, a, b, 28) for z, cy, a, b in TORSO], cap0=True, cap1=True)
    make_obj('Body_Torso', bm, ['Skin'], C['body'], 'body')

    # руки разделены по локтю: плечо закрывается рукавами кафтана, предплечье остаётся открытым
    bm = bmesh.new()
    both(bm, tube_on(ARM, [s for s in ARM_ST if s[0] <= 1.0] + [(1.06, .044, .044)], 14), cap0=True, cap1=True)
    make_obj('Body_UpperArms', bm, ['Skin'], C['body'], 'body')
    bm = bmesh.new()
    both(bm, tube_on(ARM, [(0.94, .044, .044)] + [s for s in ARM_ST if s[0] >= 1.0], 14), cap0=True, cap1=True)
    make_obj('Body_Forearms', bm, ['Skin'], C['body'], 'body')

    bm = bmesh.new()
    for mir in (False, True):
        rs = fist_rings(FIST, 10)
        tp = thumb_pts()
        th = [ring(tp[0], tp[1] - tp[0], .015, .014, 6), ring(tp[1], tp[2] - tp[0], .014, .0125, 6),
              ring(tp[2], tp[2] - tp[1], .012, .011, 6), [tp[2] + (tp[2] - tp[1]).normalized() * 0.014]]
        if mir: rs, th = mirror_pts(rs), mirror_pts(th)
        loft(bm, rs, cap0=True, cap1=True)
        loft(bm, th, cap0=True)
    make_obj('Body_Hands', bm, ['Skin'], C['body'], 'body')

    bm = bmesh.new()
    rs = [ring(along(LEG, t), tan_at(LEG, t), r, r * 0.95, 16) for t, r in LEG_ST]
    both(bm, rs, cap0=True, cap1=True)
    make_obj('Body_Legs', bm, ['Skin'], C['body'], 'body')

    bm = bmesh.new()
    rs = [ring(V((leg_axis(0.16).x, leg_axis(0.16).y, 0.16)), UP, .055, .055, 14)]
    rs += [ring_egg(V((FOOT_X, cy, z)), a - .004, bf - .004, bb - .004, 14) for z, cy, a, bf, bb in FOOT]
    both(bm, rs, cap0=True, cap1=True)
    make_obj('Body_Feet', bm, ['Skin'], C['body'], 'body')

# --- head
HS = [0.00, 0.06, 0.13, 0.22, 0.32, 0.45, 0.60, 0.75, 0.88, 0.96, 1.0]
HA = [0.024, 0.044, 0.061, 0.073, 0.079, 0.085, 0.087, 0.084, 0.069, 0.044, 0.0]
HBF = [0.064, 0.077, 0.085, 0.090, 0.095, 0.097, 0.097, 0.092, 0.077, 0.046, 0.0]
HBB = [0.000, 0.022, 0.050, 0.077, 0.099, 0.114, 0.121, 0.116, 0.097, 0.060, 0.0]
HZ0, HZ1 = 1.51, 1.795
HY = 0.012
HC = V((0, HY, 1.65))

def head_pt(s, th):
    a, bf, bb = interp(HS, HA, s), interp(HS, HBF, s), interp(HS, HBB, s)
    sn = math.sin(th)
    return V((a * math.cos(th), HY - (bf if sn > 0 else bb) * sn, HZ0 + s * (HZ1 - HZ0)))

def face_pt(s, x, side=1):
    a = interp(HS, HA, s)
    th = math.acos(max(-1, min(1, x / a)))
    p = head_pt(s, th if side > 0 else math.pi - th)
    nrm = (p - V((0, HY, p.z))).normalized()
    return p, nrm

def build_head(C):
    bm = bmesh.new()
    SEG = 32
    ss = [0, .03, .06, .10, .14, .19, .25, .32, .39, .46, .53, .60, .67, .74, .81, .87, .92, .96, .985]
    rs = [[head_pt(s, 2 * math.pi * i / SEG) for i in range(SEG)] for s in ss] + [[head_pt(1.0, 0)]]
    loft(bm, rs, cap0=True, mat=0)
    # neck
    nk = [ring(V((0, 0.02, z)), UP, r, r, 16) for z, r in ((1.40, .056), (1.46, .052), (1.53, .050), (1.58, .047))]
    loft(bm, nk, cap0=True, cap1=True, mat=0)
    # nose
    T = head_pt(0.52, math.pi / 2) + V((0, -0.002, 0))
    P = head_pt(0.37, math.pi / 2) + V((0, -0.016, 0))
    B = head_pt(0.34, math.pi / 2) + V((0, 0.002, 0))
    L = head_pt(0.36, math.pi / 2) + V((0.011, 0.004, 0))
    R = head_pt(0.36, math.pi / 2) + V((-0.011, 0.004, 0))
    vt = [bm.verts.new(x) for x in (T, P, B, L, R)]
    for q in ((0, 3, 1), (0, 1, 4), (1, 3, 2), (1, 2, 4), (0, 4, 2, 3)):
        bm.faces.new([vt[i] for i in q]).material_index = 0
    for side in (1, -1):
        p, n = face_pt(0.47, 0.035, side)
        ellipsoid(bm, p + n * 0.0005, (0.0145, 0.0045, 0.0085), 10, 5, mat=2, rot=basis_from_normal(n))
        p, n = face_pt(0.565, 0.037, side)
        box(bm, p + n * 0.002, (0.021, 0.004, 0.0048), mat=1, rot=basis_from_normal(n) @ Matrix.Rotation(rad(-14 * side), 3, 'Y'))
        ec = V((interp(HS, HA, 0.42) * 0.98 * side, 0.022, HZ0 + 0.42 * (HZ1 - HZ0)))
        ellipsoid(bm, ec, (0.010, 0.018, 0.028), 8, 5, mat=0, rot=Matrix.Rotation(rad(-12 * side), 3, 'Z'))
    p, n = face_pt(0.21, 0.0001, 1)
    box(bm, p + n * 0.001, (0.014, 0.0022, 0.0018), mat=3, rot=basis_from_normal(n))
    make_obj('Head', bm, ['Skin', 'Hair', 'Eye', 'Mouth'], C['head'], 'head')

# --- hair
HAIR = [
    # (угол, высота на голове, направление, длина, ширина, толщина, выгиб, отгиб кончика)
    # чёлка
    (100, .90, (-0.30, -0.40, -0.87), .105, .042, .015, .020, .006), (75, .90, (-0.05, -0.45, -0.89), .095, .040, .015, .020, .006),
    (128, .87, (-0.55, -0.30, -0.78), .100, .040, .014, .018, .008), (50, .87, (0.35, -0.35, -0.87), .090, .038, .014, .018, .008),
    (152, .82, (-0.70, -0.10, -0.70), .095, .038, .014, .016, .012), (25, .82, (0.66, -0.12, -0.74), .090, .036, .014, .016, .012),
    # виски
    (5, .72, (0.40, 0.05, -0.92), .100, .042, .015, .014, .018), (-30, .68, (0.35, 0.35, -0.87), .100, .042, .015, .014, .020),
    (175, .72, (-0.40, 0.05, -0.92), .100, .042, .015, .014, .018), (210, .68, (-0.35, 0.35, -0.87), .100, .042, .015, .014, .020),
    # затылок
    (235, .55, (-0.30, 0.45, -0.84), .110, .046, .016, .016, .024), (270, .58, (0.00, 0.50, -0.87), .115, .048, .016, .016, .026),
    (305, .55, (0.30, 0.45, -0.84), .110, .046, .016, .016, .024), (250, .30, (-0.15, 0.35, -0.92), .075, .036, .013, .008, .016),
    (290, .30, (0.15, 0.35, -0.92), .075, .036, .013, .008, .016),
    # макушка
    (120, .97, (-0.45, -0.70, -0.40), .110, .048, .017, .016, .010), (60, .97, (0.40, -0.75, -0.40), .105, .048, .017, .016, .010),
    (270, .93, (0.05, 0.70, -0.65), .110, .050, .017, .012, .022), (215, .88, (-0.70, 0.45, -0.45), .100, .046, .016, .014, .022),
    (325, .88, (0.70, 0.45, -0.45), .100, .046, .016, .014, .022), (0, .96, (0.80, -0.15, -0.35), .095, .046, .016, .014, .018),
    (180, .96, (-0.80, -0.15, -0.35), .095, .046, .016, .014, .018), (300, .97, (0.45, 0.70, -0.25), .095, .044, .016, .012, .020),
    (240, .97, (-0.45, 0.70, -0.25), .095, .044, .016, .012, .020),
]
HAIR_OFS = 0.017

def cap_pt(s, th, off):
    p = head_pt(s, th)
    return p + (p - HC).normalized() * off

def s_low(th):
    sn = math.sin(th)
    return lerp(0.56, 0.70, sn) if sn >= 0 else lerp(0.56, 0.15, -sn)

def build_hair(C):
    bm = bmesh.new()
    SEG = 32
    rs = []
    for k in (0, 1, 2, 3, 4, 5, 6, 7, 7.6):
        r = []
        for i in range(SEG):
            th = 2 * math.pi * i / SEG
            sl = s_low(th)
            r.append(cap_pt(sl + (1 - sl) * (1 - (1 - k / 8) ** 1.3), th, HAIR_OFS))
        rs.append(r)
    rs.append([cap_pt(1.0, 0, HAIR_OFS)])
    loft(bm, rs)
    for hd in HAIR:
        thd, s, d, L, W, T, bulge = hd[:7]
        flick = hd[7] if len(hd) > 7 else 0.0
        th = rad(thd)
        root = cap_pt(s, th, HAIR_OFS * 0.4)
        n = (root - HC).normalized()
        D = V(d).normalized()
        wax = n.cross(D)
        if wax.length < 1e-4: wax = V((1, 0, 0))
        wax.normalize()
        tax = D.cross(wax).normalized()
        rings = []
        for t, k in ((0, 1.0), (.33, .9), (.66, .62), (.88, .32)):
            c = root + D * (L * t) + n * (bulge * math.sin(math.pi * t) + flick * t * t)
            rings.append([c + wax * (W * k * math.cos(2 * math.pi * i / 6)) + tax * (T * k * math.sin(2 * math.pi * i / 6)) for i in range(6)])
        rings.append([root + D * L + n * (bulge * 0.2 + flick)])
        loft(bm, rings)
    make_obj('Hair_Messy', bm, ['Hair'], C['hair'], 'hair')

# --- coat (+ collar, sleeves) and shirt
COAT = [(1.470, 0.012, 0.085, 0.075, 40), (1.455, 0.010, 0.130, 0.088, 36), (1.435, 0.008, 0.190, 0.104, 32),
        (1.405, 0.005, 0.232, 0.118, 30), (1.345, 0.000, 0.220, 0.130, 28), (1.265, -0.005, 0.198, 0.130, 24),
        (1.170, 0.000, 0.180, 0.121, 16), (1.090, 0.005, 0.168, 0.114, 11), (1.040, 0.005, 0.166, 0.113, 10),
        (0.980, 0.005, 0.192, 0.130, 12), (0.900, 0.005, 0.218, 0.146, 15), (0.800, 0.005, 0.228, 0.155, 20),
        (0.680, 0.005, 0.236, 0.163, 25), (0.580, 0.005, 0.243, 0.168, 29), (0.500, 0.005, 0.248, 0.172, 32),
        (0.470, 0.005, 0.250, 0.173, 33)]
COAT_VENT_Z = 0.90

def coat_ab(z):
    zs = [r[0] for r in COAT][::-1]
    col = lambda i: [r[i] for r in COAT][::-1]
    return interp(zs, col(2), z), interp(zs, col(3), z), interp(zs, col(1), z), interp(zs, col(4), z)

def coat_pt(z, thd, ofs):
    a, b, cy, _ = coat_ab(z)
    t = rad(thd)
    return V(((a + ofs) * math.cos(t), cy - (b + ofs) * math.sin(t), z))
COLLAR = [(1.455, 0.012, 0.092, 0.084), (1.505, 0.016, 0.096, 0.088), (1.495, 0.018, 0.130, 0.116), (1.445, 0.016, 0.160, 0.136)]
SLEEVE = [(-0.20, .036, .034, 0), (-0.12, .058, .055, 0), (-0.05, .070, .066, 0), (0.0, .075, .070, 0), (.35, .069, .065, 0),
          (.7, .064, .061, 0), (1.0, .062, .060, 0), (1.15, .061, .059, 0), (1.22, .061, .059, 1), (1.23, .074, .071, 1),
          (1.42, .072, .069, 1), (1.43, .056, .054, 1), (1.41, .036, .036, 1)]

def coat_half(N=16):
    rows = []
    for z, cy, a, b, g in COAT:
        t0, t1 = rad(90 - g), rad(-90)
        amp = 0.03 * max(0.0, (0.98 - z) / 0.56)
        row = []
        for k in range(N + 1):
            t = lerp(t0, t1, k / N)
            kf = 1 + amp * math.sin(6 * t)
            row.append(V((a * math.cos(t) * kf, cy - b * math.sin(t) * kf, z)))
        rows.append(row)
    return rows

def build_coat(C):
    bm = bmesh.new()
    left = coat_half()
    vl, _ = loft(bm, left, closed=False)
    vr, _ = loft(bm, mirror_pts(left), closed=False)
    tm = {vr[i][-1]: vl[i][-1] for i, row in enumerate(COAT) if row[0] >= COAT_VENT_Z - 1e-4}
    bmesh.ops.weld_verts(bm, targetmap=tm)
    g = rad(54)
    col = [[V((a * math.cos(t), cy - b * math.sin(t), z)) for t in [lerp(math.pi / 2 + g, 2.5 * math.pi - g, k / 20) for k in range(21)]]
           for z, cy, a, b in COLLAR]
    loft(bm, col, closed=False)
    # лацканы: отвороты на груди, изнанка красная после shell
    lap = []
    for z, w in ((1.45, 30), (1.41, 26), (1.35, 19), (1.29, 11), (1.23, 3)):
        g = coat_ab(z)[3]
        lap.append([coat_pt(z, 90 - g + 0.5, 0.004), coat_pt(z, 90 - g - w * 0.5, 0.010), coat_pt(z, 90 - g - w, 0.006)])
    loft(bm, lap, closed=False)
    loft(bm, mirror_pts(lap), closed=False)
    fix_normals(bm, True)
    shell(bm, 0.010, 1, 1)
    sl = [ring(along(ARM, t), tan_at(ARM, min(t, 1.999)), a, b, 12) for t, a, b, m in SLEEVE]
    bm_ = [m for _, _, _, m in SLEEVE][:-1]
    loft(bm, sl, cap0=True, cap1=True, band_mats=bm_ + [1])
    loft(bm, mirror_pts(sl), cap0=True, cap1=True, band_mats=bm_ + [1])
    make_obj('Top_Coat', bm, ['Coat', 'Lining'], C['top'], 'top', hides=('Body_Torso', 'Body_UpperArms'), island=False)

SHIRT = [(0.975, .005, .162, .106), (1.06, .005, .158, .103), (1.14, 0, .168, .110), (1.22, -.005, .186, .118),
         (1.30, -.005, .198, .121), (1.37, 0, .200, .113), (1.42, .005, .178, .096), (1.455, .01, .110, .074),
         (1.48, .012, .064, .060), (1.51, .012, .060, .058)]

def build_shirt(C):
    bm = bmesh.new()
    loft(bm, [ring(V((0, cy, z)), UP, a, b, 24) for z, cy, a, b in SHIRT])
    st = [(-0.10, .058, .055), (0.0, .062, .058), (0.3, .057, .054), (0.5, .055, .052), (0.52, .045, .043)]
    both(bm, tube_on(ARM, st, 12), cap0=True, cap1=True)
    make_obj('Under_Shirt', bm, ['Shirt'], C['under'], 'under', hides=('Body_Torso',))

# --- trousers
PELVIS = [(1.075, .005, .150, .098), (1.02, .005, .160, .104), (0.95, .005, .172, .110), (0.89, 0.0, .140, .098), (0.86, 0.0, .080, .065)]
BOOT_SHAFT = [(0.16, .060), (0.22, .064), (0.30, .070), (0.38, .074), (0.44, .076)]

def boot_r(z): return interp([z for z, _ in BOOT_SHAFT], [r for _, r in BOOT_SHAFT], z)

def build_trousers(C):
    bm = bmesh.new()
    loft(bm, [ring(V((0, cy, z)), UP, a, b, 24) for z, cy, a, b in PELVIS], cap1=True)
    rs = []
    for t, r in LEG_ST[1:-3] + [(2.72, .046)]:
        c = along(LEG, t)
        rr = r + 0.010
        if c.z < 0.50: rr = min(rr, boot_r(c.z) - 0.005)
        rs.append(ring(c, tan_at(LEG, t), rr, rr * 0.95, 16))
    both(bm, rs, cap0=True, cap1=True)
    make_obj('Legs_Trousers', bm, ['Trousers'], C['legs'], 'legs', hides=('Body_Legs',))

# --- boots & gloves
def boot_rings(segs=16):
    rows, mats = [], []
    shaft = [(0.500, .066, 0), (0.515, .078, 0), (0.510, .086, 0), (0.450, .084, 0), (0.445, .076, 0), (0.380, .074, 0),
             (0.312, .071, 0), (0.308, .077, 1), (0.272, .076, 1), (0.268, .069, 0), (0.220, .064, 0), (0.160, .060, 0)]
    for z, r, m in shaft:
        c = leg_axis(z); rows.append(ring(V((c.x, c.y, z)), UP, r, r, segs)); mats.append(m)
    for z, cy, a, bf, bb in FOOT[:-2]:
        rows.append(ring_egg(V((FOOT_X, cy, z)), a + .007, bf + .007, bb + .007, segs)); mats.append(0)
    z, cy, a, bf, bb = FOOT[-2]
    rows.append(ring_egg(V((FOOT_X, cy, 0.044)), a + .007, bf + .007, bb + .007, segs)); mats.append(1)
    rows.append(ring_egg(V((FOOT_X, cy, 0.038)), a + .011, bf + .011, bb + .011, segs)); mats.append(1)
    z, cy, a, bf, bb = FOOT[-1]
    rows.append(ring_egg(V((FOOT_X, cy, 0.0)), a + .010, bf + .010, bb + .010, segs)); mats.append(1)
    return rows, mats[:-1]

def build_boots(C):
    bm = bmesh.new()
    rows, mats = boot_rings()
    loft(bm, rows, cap0=True, cap1=True, band_mats=mats + [1])
    loft(bm, mirror_pts(rows), cap0=True, cap1=True, band_mats=mats + [1])
    make_obj('Feet_Boots', bm, ['Leather', 'Sole'], C['feet'], 'feet', hides=('Body_Feet',))

def build_gloves(C):
    bm = bmesh.new()
    for mir in (False, True):
        rs = fist_rings(GLOVE, 10)
        tp = thumb_pts()
        th = [ring(tp[0] - (tp[1] - tp[0]) * 0.3, tp[1] - tp[0], .019, .018, 6), ring(tp[0].lerp(tp[1], 0.55), tp[1] - tp[0], .018, .017, 6)]
        if mir: rs, th = mirror_pts(rs), mirror_pts(th)
        loft(bm, rs, cap0=True, cap1=True)
        loft(bm, th, cap0=True, cap1=True)
    make_obj('Hands_Gloves', bm, ['Leather'], C['hands'], 'hands')

# --- accessories
def build_belt(C):
    bm = bmesh.new()
    a, b, z0, z1, th = 0.180, 0.126, 1.020, 1.068, 0.007
    rows = [ring(V((0, 0.005, z0)), UP, a, b, 28), ring(V((0, 0.005, z1)), UP, a, b, 28),
            ring(V((0, 0.005, z1)), UP, a - th, b - th, 28), ring(V((0, 0.005, z0)), UP, a - th, b - th, 28)]
    loft(bm, rows, cyclic=True, mat=0)
    box(bm, V((0, 0.005 - b - 0.004, (z0 + z1) / 2)), (0.026, 0.005, 0.031), mat=1)
    make_obj('Acc_Belt', bm, ['Leather', 'Brass'], C['acc'], 'belt', sharp=40)

def build_scarf(C):
    bm = bmesh.new()
    N = 18
    path = []
    for i in range(N):
        t = 2 * math.pi * i / N
        path.append(V((0.074 * math.cos(t), 0.014 - 0.072 * math.sin(t), 1.492 - 0.018 * max(0.0, math.sin(t)))))
    rs = [ring(path[i], path[(i + 1) % N] - path[i - 1], 0.026, 0.034, 6, fwd=UP) for i in range(N)]
    loft(bm, rs, cyclic=True)
    tail = [(V((0.012, -0.072, 1.475)), .034, .014), (V((0.022, -0.100, 1.425)), .043, .014),
            (V((0.030, -0.114, 1.370)), .044, .012), (V((0.034, -0.119, 1.325)), .030, .008), (V((0.036, -0.121, 1.300)), .012, .005)]
    pts = [p for p, _, _ in tail]
    loft(bm, [ring(p, tan_at(pts, i), a, b, 6) for i, (p, a, b) in enumerate(tail)], cap0=True, cap1=True)
    make_obj('Acc_Scarf', bm, ['Lining'], C['acc'], 'neck')

# --- перевязь через грудь (единственный ремень кроме пояса)
def build_strap(C):
    bm = bmesh.new()
    N, k, z0, w = 32, 0.80, 1.21, 0.018
    def pt(phi, ofs, dz):
        z = z0
        for _ in range(4):
            a, b, cy, _ = coat_ab(z)
            x = (a + ofs) * math.cos(phi)
            z = z0 + k * x
        return V((x, cy - (b + ofs) * math.sin(phi), z + dz))
    rows = [[pt(2 * math.pi * i / N, o, dz) for i in range(N)] for o, dz in ((0.017, -w), (0.017, w), (0.011, w), (0.011, -w))]
    loft(bm, rows, cyclic=True)
    make_obj('Acc_Strap', bm, ['Leather'], C['acc'], 'strap')

# --- sword (local space: grip centre at origin, blade +Z, edges along X)
def build_sword(C):
    bm = bmesh.new()
    grip = [ring(V((0, 0, z)), UP, r, r, 8) for z, r in ((-0.085, .0135), (-0.04, .015), (0.0, .0155), (0.04, .015), (0.085, .0135))]
    loft(bm, grip, cap0=True, cap1=True, mat=2)
    pom = [[V((0, 0, -0.128))]] + [ring(V((0, 0, z)), UP, r, r, 8) for z, r in ((-0.124, .012), (-0.116, .022), (-0.104, .025), (-0.093, .021), (-0.086, .011))]
    loft(bm, pom, cap1=True, mat=1)
    gd = []
    for x in (-0.12, -0.10, -0.05, 0.0, 0.05, 0.10, 0.12):
        zc = 0.097
        gd.append(ring(V((x, 0, zc)), V((1, 0, 0)), 0.013, 0.016, 6, fwd=V((0, -1, 0))))
    loft(bm, gd, cap0=True, cap1=True, mat=1)
    bl = []
    for z, w, t in ((0.104, .036, .0072), (0.14, .035, .0072), (0.55, .031, .0068), (0.82, .024, .006), (0.93, .012, .0045)):
        bl.append([V((w, 0, z)), V((0, -t, z)), V((-w, 0, z)), V((0, t, z))])
    bl.append([V((0, 0, 0.975))])
    loft(bm, bl, cap0=True, mat=0)
    ob = make_obj('Weapon_Longsword', bm, ['Steel', 'Brass', 'Grip'], C['weapon'], 'weapon', sharp=35)
    return ob

def sword_matrix():
    X, Z = mv(GX), mv(BDIR)
    Y = Z.cross(X)
    m = Matrix((X, Y, Z)).transposed().to_4x4()
    m.translation = mv(GRIP)
    return m

# ------------------------------------------------------------------ assembly
def reset():
    if bpy.context.object and bpy.context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    for ob in list(bpy.data.objects): bpy.data.objects.remove(ob, do_unlink=True)
    for c in list(bpy.data.collections): bpy.data.collections.remove(c)
    for blocks in (bpy.data.meshes, bpy.data.armatures, bpy.data.materials, bpy.data.cameras, bpy.data.lights, bpy.data.curves):
        for b in list(blocks):
            if b.users == 0: blocks.remove(b)
    for t in list(bpy.data.texts):
        if t.name.startswith('SW_'): bpy.data.texts.remove(t)
    PARTS.clear(); MAT.clear()

def new_coll(name, parent=None):
    c = bpy.data.collections.new(name)
    (parent.children if parent else bpy.context.scene.collection.children).link(c)
    return c

SKIN_SETS = {
    'Body_Torso': (['Hips', 'Spine', 'Chest', 'Neck', 'Shoulder.L', 'Shoulder.R', 'UpperArm.L', 'UpperArm.R', 'UpperLeg.L', 'UpperLeg.R'], None),
    'Under_Shirt': (['Hips', 'Spine', 'Chest', 'Neck', 'Shoulder.L', 'Shoulder.R', 'UpperArm.L', 'UpperArm.R', 'LowerArm.L', 'LowerArm.R'], None),
    'Body_UpperArms': (['Chest', 'Shoulder.L', 'Shoulder.R', 'UpperArm.L', 'UpperArm.R', 'LowerArm.L', 'LowerArm.R', 'Hand.L', 'Hand.R'], None),
    'Body_Forearms': (['UpperArm.L', 'UpperArm.R', 'LowerArm.L', 'LowerArm.R', 'Hand.L', 'Hand.R'], None),
    'Body_Hands': (['LowerArm.L', 'LowerArm.R', 'Hand.L', 'Hand.R'], None),
    'Hands_Gloves': (['LowerArm.L', 'LowerArm.R', 'Hand.L', 'Hand.R'], None),
    'Body_Legs': (['Hips', 'UpperLeg.L', 'UpperLeg.R', 'LowerLeg.L', 'LowerLeg.R', 'Foot.L', 'Foot.R'], None),
    'Legs_Trousers': (['Hips', 'Spine', 'UpperLeg.L', 'UpperLeg.R', 'LowerLeg.L', 'LowerLeg.R'], None),
    'Body_Feet': (['LowerLeg.L', 'LowerLeg.R', 'Foot.L', 'Foot.R', 'Toes.L', 'Toes.R'], None),
    'Feet_Boots': (['LowerLeg.L', 'LowerLeg.R', 'Foot.L', 'Foot.R', 'Toes.L', 'Toes.R'], None),
    'Top_Coat': (['Hips', 'Spine', 'Chest', 'Neck', 'Shoulder.L', 'Shoulder.R', 'UpperArm.L', 'UpperArm.R', 'LowerArm.L', 'LowerArm.R',
                  'UpperLeg.L', 'UpperLeg.R', 'CoatFront1.L', 'CoatFront2.L', 'CoatBack1.L', 'CoatBack2.L',
                  'CoatFront1.R', 'CoatFront2.R', 'CoatBack1.R', 'CoatBack2.R'], {'UpperLeg': 0.12}),
    'Acc_Belt': (['Hips', 'Spine'], None),
    'Acc_Strap': (['Hips', 'Spine', 'Chest', 'Shoulder.L', 'Shoulder.R'], None),
    'Acc_Scarf': (['Neck', 'Chest', 'Head'], None),
}

def build():
    reset()
    make_materials()
    define_bones()
    top = new_coll('Swordsman_v004')
    C = {k: new_coll(n, top) for k, n in (('rig', '00_Rig'), ('body', '01_Body'), ('head', '02_Head'), ('hair', '03_Hair'),
                                          ('top', '10_Top'), ('under', '11_Under'), ('legs', '20_Legs'), ('feet', '30_Feet'),
                                          ('hands', '31_Hands'), ('acc', '40_Accessories'), ('weapon', '50_Weapon'))}
    rig = build_rig(C['rig'])
    build_body(C); build_head(C); build_hair(C); build_coat(C); build_shirt(C); build_trousers(C)
    build_boots(C); build_gloves(C); build_belt(C); build_scarf(C); build_strap(C)
    sword = build_sword(C)
    for name, ob in PARTS.items():
        if ob is sword: continue
        if name == 'Head':
            skin(ob, ['Chest', 'Neck', 'Head'], force=lambda p: {'Head': 1.0} if p.z >= 1.545 else None)
        elif name == 'Hair_Messy':
            skin(ob, ['Head'], force=lambda p: {'Head': 1.0})
        elif name == 'Legs_Trousers':
            c, ro = SKIN_SETS[name]
            skin(ob, c, ro, force=lambda p: {('LowerLeg.L' if p.x > 0 else 'LowerLeg.R'): 1.0} if p.z < 0.52 else None)
        else:
            c, ro = SKIN_SETS[name]
            skin(ob, c, ro)
        ob.parent = rig
        md = ob.modifiers.new('Armature', 'ARMATURE'); md.object = rig
    sword.parent = rig; sword.parent_type = 'BONE'; sword.parent_bone = 'WeaponSocket.R'
    bpy.context.view_layer.update()
    sword.matrix_world = sword_matrix()
    for nm in ('Body_Torso', 'Body_UpperArms', 'Body_Legs', 'Body_Feet'):
        PARTS[nm].hide_set(True); PARTS[nm].hide_render = True
    unwrap()
    add_swap_text()
    print('BUILD OK', {n: tris(o) for n, o in PARTS.items()}, 'TOTAL', total_visible())
    return rig

def tris(ob): return sum(len(p.vertices) - 2 for p in ob.data.polygons)

def total_visible():
    return sum(tris(o) for o in PARTS.values() if not o.hide_render)

def unwrap():
    for ob in PARTS.values():
        hid = ob.hide_get(); ob.hide_set(False)
        try:
            for o in bpy.context.selected_objects: o.select_set(False)
            ob.select_set(True); bpy.context.view_layer.objects.active = ob
            bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
            bpy.ops.uv.smart_project(angle_limit=rad(66), island_margin=0.01)
        except Exception as e:
            print('UV fail', ob.name, e)
        finally:
            if bpy.context.object and bpy.context.object.mode != 'OBJECT': bpy.ops.object.mode_set(mode='OBJECT')
            ob.select_set(False); ob.hide_set(hid)

def add_swap_text():
    lines = [
        '# SW_SWAP_EQUIPMENT: укажите предмет для каждого слота и нажмите Run Script.',
        '# Предмет = объект с custom property sw_slot; sw_hides перечисляет части тела, которые он закрывает.',
        'import bpy',
        "EQUIP = {'top': 'Top_Coat', 'under': 'Under_Shirt', 'legs': 'Legs_Trousers', 'feet': 'Feet_Boots',",
        "         'hands': 'Hands_Gloves', 'hair': 'Hair_Messy', 'belt': 'Acc_Belt', 'strap': 'Acc_Strap', 'neck': 'Acc_Scarf', 'weapon': 'Weapon_Longsword'}",
        "items = [o for o in bpy.data.objects if o.get('sw_part')]",
        "hidden_body = set()",
        "for o in items:",
        "    slot = o.get('sw_slot')",
        "    if slot in ('body', 'head'): continue",
        "    on = EQUIP.get(slot) == o.name",
        "    o.hide_set(not on); o.hide_render = not on",
        "    if on and o.get('sw_hides'): hidden_body |= set(o['sw_hides'].split(','))",
        "for o in items:",
        "    if o.get('sw_slot') == 'body':",
        "        o.hide_set(o.name in hidden_body); o.hide_render = o.name in hidden_body",
        "print('equipped:', EQUIP, 'hidden body:', sorted(hidden_body))",
    ]
    t = bpy.data.texts.new('SW_SWAP_EQUIPMENT.py')
    t.write('\n'.join(lines) + '\n')


# ------------------------------------------------------------------ poses
def rot_about(p, q):
    return Matrix.Translation(p) @ q.to_matrix().to_4x4() @ Matrix.Translation(-p)

def clear_pose(rig):
    for pb in rig.pose.bones:
        pb.location = (0, 0, 0); pb.rotation_quaternion = (1, 0, 0, 0); pb.rotation_euler = (0, 0, 0); pb.scale = (1, 1, 1)
    bpy.context.view_layer.update()

def set_idle(rig):
    # тестовая поза: руки опущены, меч в правой руке смотрит вперёд-вниз (только для превью и проверки весов)
    clear_pose(rig)
    pbs = rig.pose.bones
    for s, sx in (('L', 1), ('R', -1)):
        ua, la, hd = pbs['UpperArm.' + s], pbs['LowerArm.' + s], pbs['Hand.' + s]
        sh, el, wr = ua.bone.head_local.copy(), la.bone.head_local.copy(), hd.bone.head_local.copy()
        T1 = rot_about(sh, Quaternion(V((0, 1, 0)), rad(30) * sx))
        T2 = T1 @ rot_about(el, Quaternion(V((1, 0, 0)), rad(-16)))
        T3 = T2
        if s == 'R':
            palm, bd, hdv = mv(PALM), mv(BDIR), mv(HDIR)
            q3 = max((Quaternion(palm, rad(35) * sg) for sg in (1, -1)), key=lambda q: (q @ bd).dot(hdv))
            T3 = T2 @ rot_about(wr, q3)
        ua.matrix = T1 @ ua.bone.matrix_local; bpy.context.view_layer.update()
        la.matrix = T2 @ la.bone.matrix_local; bpy.context.view_layer.update()
        hd.matrix = T3 @ hd.bone.matrix_local; bpy.context.view_layer.update()

def set_stride(rig):
    # стресс-тест: шаг вперёд правой ногой (проверка пол кафтана и штанов)
    clear_pose(rig)
    pbs = rig.pose.bones
    for name, ang in (('UpperLeg.R', -35), ('LowerLeg.R', 30), ('UpperLeg.L', 22), ('LowerLeg.L', 15)):
        pb = pbs[name]
        T = rot_about(pb.bone.head_local, Quaternion(V((1, 0, 0)), rad(ang)))
        par = pb.parent
        base = (par.matrix @ par.bone.matrix_local.inverted()) if par and not par.name.startswith('Hips') else Matrix.Identity(4)
        pb.matrix = base @ T @ pb.bone.matrix_local
        bpy.context.view_layer.update()

# ------------------------------------------------------------------ preview (toon look is preview-only, materials stay Principled for export)
def outline_on(th=0.006):
    # обводка «inverted hull» только для превью; в FBX не попадает
    om = bpy.data.materials.get('M_PV_Outline') or make_material('M_PV_Outline', (0.02, 0.015, 0.015))
    om.use_backface_culling = True
    PMAT['Outline'] = om
    for ob in PARTS.values():
        ob.data.materials.append(om)
        md = ob.modifiers.new('PV_Outline', 'SOLIDIFY')
        md.thickness = th; md.offset = 1.0; md.use_flip_normals = True; md.use_rim = False; md.material_offset = 64

def outline_off():
    for ob in PARTS.values():
        md = ob.modifiers.get('PV_Outline')
        if md: ob.modifiers.remove(md)
        if len(ob.data.materials) and ob.data.materials[-1] and ob.data.materials[-1].name == 'M_PV_Outline':
            ob.data.materials.pop()
PMAT = {}
def toon_on():
    for m in list(MAT.values()) + list(PMAT.values()):
        nt = m.node_tree
        out = next(n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL')
        p = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
        col = tuple(p.inputs['Base Color'].default_value)
        d = nt.nodes.new('ShaderNodeBsdfDiffuse'); d.name = 'TOON_d'
        s = nt.nodes.new('ShaderNodeShaderToRGB'); s.name = 'TOON_s'
        r = nt.nodes.new('ShaderNodeValToRGB'); r.name = 'TOON_r'
        r.color_ramp.interpolation = 'CONSTANT'
        el = r.color_ramp.elements
        el[0].position = 0.0; el[0].color = (0.30, 0.29, 0.36, 1)
        el[1].position = 0.16; el[1].color = (1, 1, 1, 1)
        c = nt.nodes.new('ShaderNodeRGB'); c.name = 'TOON_c'; c.outputs[0].default_value = col
        mul = nt.nodes.new('ShaderNodeVectorMath'); mul.name = 'TOON_m'; mul.operation = 'MULTIPLY'
        em = nt.nodes.new('ShaderNodeEmission'); em.name = 'TOON_e'
        L = nt.links
        L.new(d.outputs[0], s.inputs[0]); L.new(s.outputs[0], r.inputs[0])
        L.new(r.outputs[0], mul.inputs[0]); L.new(c.outputs[0], mul.inputs[1])
        L.new(mul.outputs[0], em.inputs[0]); L.new(em.outputs[0], out.inputs['Surface'])

def toon_off():
    for m in list(MAT.values()) + list(PMAT.values()):
        nt = m.node_tree
        for n in [n for n in nt.nodes if n.name.startswith('TOON_')]: nt.nodes.remove(n)
        out = next(n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL')
        p = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
        if p: nt.links.new(p.outputs[0], out.inputs['Surface'])

def setup_preview():
    sc = bpy.context.scene
    old = bpy.data.collections.get('90_Preview')
    if old:
        for o in list(old.objects): bpy.data.objects.remove(o, do_unlink=True)
        bpy.data.collections.remove(old)
    for k in ('Floor', 'Label'):
        m = bpy.data.materials.get('M_PV_' + k)
        if m: bpy.data.materials.remove(m)
    P = new_coll('90_Preview')
    PMAT['Floor'] = make_material('M_PV_Floor', (0.21, 0.20, 0.20))
    PMAT['Label'] = make_material('M_PV_Label', (0.90, 0.86, 0.80))
    bm = bmesh.new(); bmesh.ops.create_circle(bm, cap_ends=True, radius=40.0, segments=64)
    me = bpy.data.meshes.new('PV_Floor'); bm.to_mesh(me); bm.free(); me.materials.append(PMAT['Floor'])
    P.objects.link(bpy.data.objects.new('PV_Floor', me))
    def light(name, typ, energy, color, rot=None, loc=None, **kw):
        ld = bpy.data.lights.new(name, typ); ld.energy = energy; ld.color = color
        for k, v in kw.items(): setattr(ld, k, v)
        ob = bpy.data.objects.new(name, ld); P.objects.link(ob)
        if rot: ob.rotation_euler = rot
        if loc: ob.location = loc
    light('PV_Key', 'SUN', 3.0, (1.0, 0.88, 0.74), rot=(rad(50), 0, rad(-35)), angle=rad(1.5))
    light('PV_Rim', 'SUN', 1.2, (0.62, 0.72, 1.0), rot=(rad(65), 0, rad(170)), angle=rad(3))
    cam = bpy.data.cameras.new('PV_Cam'); co = bpy.data.objects.new('PV_Cam', cam); P.objects.link(co); sc.camera = co
    cam.clip_end = 100
    w = sc.world or bpy.data.worlds.new('World'); sc.world = w
    try: w.use_nodes = True
    except Exception: pass
    bg = w.node_tree.nodes.get('Background') if w.node_tree else None
    if bg: bg.inputs[0].default_value = (0.016, 0.018, 0.024, 1)
    else: w.color = (0.016, 0.018, 0.024)
    for eng in ('BLENDER_EEVEE_NEXT', 'BLENDER_EEVEE'):
        try:
            sc.render.engine = eng; break
        except Exception: pass
    sc.view_settings.view_transform = 'Standard'
    try: sc.eevee.taa_render_samples = 32
    except Exception: pass
    try:
        sc.render.use_freestyle = False
        sc.render.line_thickness_mode = 'ABSOLUTE'
        fs = bpy.context.view_layer.freestyle_settings
        ls = fs.linesets[0] if len(fs.linesets) else fs.linesets.new('Ink')
        ls.select_by_visibility = True; ls.select_by_edge_types = True
        ls.select_silhouette = True; ls.select_border = True; ls.select_crease = False
        ls.linestyle.color = (0.03, 0.025, 0.025); ls.linestyle.thickness = 1.8
    except Exception as e:
        print('freestyle unavailable:', e)
    return P

def shoot(name, loc, target, ortho=None, lens=50, res=(1000, 1200), line=1.8):
    sc = bpy.context.scene
    co = bpy.data.objects['PV_Cam']; cam = co.data
    co.location = V(loc)
    co.rotation_euler = (V(target) - V(loc)).to_track_quat('-Z', 'Y').to_euler()
    if ortho: cam.type = 'ORTHO'; cam.ortho_scale = ortho
    else: cam.type = 'PERSP'; cam.lens = lens
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    try: bpy.context.view_layer.freestyle_settings.linesets[0].linestyle.thickness = line
    except Exception: pass
    sc.render.filepath = os.path.join(OUT, name)
    bpy.ops.render.render(write_still=True)

LINEUP = [(['Body_Torso', 'Body_UpperArms', 'Body_Forearms', 'Body_Hands', 'Body_Legs', 'Body_Feet', 'Head'], 0.0, 'BODY + HEAD'),
          (['Hair_Messy'], 0.8, 'HAIR'), (['Acc_Scarf'], 1.25, 'SCARF'), (['Under_Shirt'], 1.85, 'SHIRT'),
          (['Top_Coat'], 2.8, 'COAT'), (['Acc_Belt', 'Acc_Strap'], 3.6, 'BELT + STRAP'), (['Legs_Trousers'], 4.15, 'TROUSERS'),
          (['Feet_Boots'], 4.65, 'BOOTS'), (['Hands_Gloves'], 5.6, 'GLOVES'), (['Weapon_Longsword'], 6.65, 'SWORD')]

def lineup(P):
    saved = {}
    for names, dx, label in LINEUP:
        for n in names:
            ob = PARTS[n]
            saved[n] = (ob.matrix_world.copy(), ob.hide_render)
            ob.hide_render = False
            if n == 'Weapon_Longsword': ob.matrix_world = Matrix.Translation((dx, 0, 0.14))
            else: ob.location.x += dx
        cu = bpy.data.curves.new('PV_L_' + label, 'FONT'); cu.body = label; cu.size = 0.085; cu.align_x = 'CENTER'
        cu.materials.append(PMAT['Label'])
        t = bpy.data.objects.new('PV_L_' + label, cu); P.objects.link(t)
        t.location = (dx, -0.6, 0.03); t.rotation_euler = (rad(90), 0, 0)
    bpy.context.view_layer.update()
    shoot('preview_parts.png', (3.25, -10, 0.9), (3.25, 0, 0.9), ortho=8.1, res=(2400, 1050), line=1.2)
    for n, (mw, hr) in saved.items():
        PARTS[n].matrix_world = mw; PARTS[n].hide_render = hr
    for o in [o for o in P.objects if o.name.startswith('PV_L_')]: bpy.data.objects.remove(o, do_unlink=True)
    bpy.context.view_layer.update()

def previews(rig):
    P = setup_preview()
    outline_on()
    toon_on()
    try:
        set_idle(rig)
        shoot('preview_front.png', (1.15, -3.3, 1.35), (0, 0, 0.88), ortho=2.15, res=(1000, 1250))
        shoot('preview_back.png', (-1.15, 3.3, 1.35), (0, 0, 0.88), ortho=2.15, res=(1000, 1250))
        tgt = V((0, 0, 0.85))
        for nm, D, line in (('preview_game_camera_close.png', 5.5, 1.6), ('preview_game_camera.png', 15.0, 1.0)):
            pitch, yaw = rad(55), rad(25)
            loc = tgt + V((-math.sin(yaw) * math.cos(pitch), -math.cos(yaw) * math.cos(pitch), math.sin(pitch))) * D
            shoot(nm, loc, tgt, lens=35, res=(1280, 720), line=line)
        set_stride(rig)
        shoot('preview_stride_test.png', (1.6, -2.9, 1.2), (0, 0, 0.8), ortho=2.15, res=(1000, 1250))
        clear_pose(rig)
        shoot('preview_apose.png', (0, -4, 0.9), (0, 0, 0.9), ortho=2.0, res=(1100, 1100))
        lineup(P)
    finally:
        toon_off(); outline_off(); clear_pose(rig)

# ------------------------------------------------------------------ validation / export / report
BUDGET = [('Тело', ['Body_Torso', 'Body_UpperArms', 'Body_Forearms', 'Body_Hands', 'Body_Legs', 'Body_Feet'], '3–5k'),
          ('Голова', ['Head'], '1.5–3k'), ('Волосы', ['Hair_Messy'], '1–2k'),
          ('Кафтан + рубашка', ['Top_Coat', 'Under_Shirt'], '3–6k'), ('Штаны', ['Legs_Trousers'], '1–2k'),
          ('Сапоги + перчатки', ['Feet_Boots', 'Hands_Gloves'], '1–2k'), ('Меч', ['Weapon_Longsword'], '<1k'),
          ('Аксессуары (пояс, перевязь, шарф)', ['Acc_Belt', 'Acc_Strap', 'Acc_Scarf'], 'вне таблицы')]

def validate(rig):
    rep = {'version': 'v004', 'blender': bpy.app.version_string, 'modules': {}, 'budget': [], 'checks': {}}
    for n, o in PARTS.items():
        d = {'tris': tris(o), 'verts': len(o.data.vertices), 'materials': [m.name for m in o.data.materials],
             'slot': o['sw_slot'], 'hides_body': o['sw_hides'], 'visible_in_default_outfit': not o.hide_render}
        if n != 'Weapon_Longsword':
            d['bad_weight_verts'] = sum(1 for v in o.data.vertices if abs(sum(g.weight for g in v.groups) - 1) > 0.02)
            d['max_influences'] = max(len(v.groups) for v in o.data.vertices)
        rep['modules'][n] = d
    for label, names, target in BUDGET:
        rep['budget'].append({'group': label, 'tris': sum(tris(PARTS[n]) for n in names), 'target': target})
    rep['tris_all_parts'] = sum(tris(o) for o in PARTS.values())
    rep['tris_visible_default_outfit'] = total_visible()
    sw = PARTS['Weapon_Longsword']; pb = rig.pose.bones['Hand.R']
    clear_pose(rig)
    rel0 = (rig.matrix_world @ pb.matrix).inverted() @ sw.matrix_world
    pos0 = sw.matrix_world.translation.copy()
    pb.rotation_mode = 'XYZ'; pb.rotation_euler = (0.6, 0.3, 0.2); bpy.context.view_layer.update()
    rel1 = (rig.matrix_world @ pb.matrix).inverted() @ sw.matrix_world
    err = max(abs(a - b) for r0, r1 in zip(rel0, rel1) for a, b in zip(r0, r1))
    moved = (sw.matrix_world.translation - pos0).length
    pb.rotation_mode = 'QUATERNION'; clear_pose(rig)
    rep['checks']['sword_follows_hand'] = bool(err < 1e-4 and moved > 1e-3)
    rep['checks']['bones'] = len(rig.data.bones)
    rep['checks']['deform_bones'] = sum(1 for b in rig.data.bones if b.use_deform)
    rep['checks']['all_weights_normalized'] = all(m.get('bad_weight_verts', 0) == 0 for m in rep['modules'].values())
    rep['checks']['max_influences_le_4'] = all(m.get('max_influences', 0) <= 4 for m in rep['modules'].values())
    rep['checks']['all_skinned_parts_on_one_rig'] = all(o.parent == rig for o in PARTS.values())
    rep['checks']['uv_maps'] = all(len(o.data.uv_layers) > 0 for o in PARTS.values())
    return rep

def export_fbx(rig):
    common = dict(use_selection=True, apply_unit_scale=True, apply_scale_options='FBX_SCALE_ALL',
                  axis_forward='-Z', axis_up='Y', add_leaf_bones=False, use_armature_deform_only=False,
                  bake_anim=False, mesh_smooth_type='FACE', use_custom_props=True,
                  primary_bone_axis='Y', secondary_bone_axis='X', use_mesh_modifiers=True)
    state = {n: o.hide_get() for n, o in PARTS.items()}
    for o in PARTS.values(): o.hide_set(False)
    try:
        for o in bpy.context.selected_objects: o.select_set(False)
        rig.select_set(True)
        for o in PARTS.values(): o.select_set(True)
        bpy.context.view_layer.objects.active = rig
        bpy.ops.export_scene.fbx(filepath=os.path.join(OUT, 'SK_Swordsman_v004.fbx'), object_types={'ARMATURE', 'MESH'}, **common)
        sw = PARTS['Weapon_Longsword']
        mw = sw.matrix_world.copy()
        sw.parent = None; sw.matrix_world = Matrix.Identity(4)
        for o in bpy.context.selected_objects: o.select_set(False)
        sw.select_set(True); bpy.context.view_layer.objects.active = sw
        bpy.ops.export_scene.fbx(filepath=os.path.join(OUT, 'SM_Longsword_v004.fbx'), object_types={'MESH'}, **common)
        sw.parent = rig; sw.parent_type = 'BONE'; sw.parent_bone = 'WeaponSocket.R'
        bpy.context.view_layer.update(); sw.matrix_world = mw
    finally:
        for o in bpy.context.selected_objects: o.select_set(False)
        for n, o in PARTS.items(): o.hide_set(state[n])

def adopt():
    PARTS.clear(); MAT.clear(); define_bones()
    for o in bpy.data.objects:
        if o.get('sw_part'): PARTS[o.name] = o
    for m in bpy.data.materials:
        if m.name.startswith('M_SW_'): MAT[m.name[5:]] = m
    return bpy.data.objects['Swordsman_Rig']

def finish(rig):
    previews(rig)
    rep = validate(rig)
    export_fbx(rig)
    rep['files'] = sorted(f for f in os.listdir(OUT) if not f.endswith('.blend1'))
    with open(os.path.join(OUT, 'build_report.json'), 'w', encoding='utf-8') as fh:
        json.dump(rep, fh, ensure_ascii=False, indent=2)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'swordsman_modular_v004.blend'))
    print('FINISH', json.dumps(rep['budget'], ensure_ascii=False), rep['checks'])

if STAGE in ('build', 'all'):
    RIG = build()
else:
    RIG = adopt()
if STAGE == 'idle': set_idle(RIG)
if STAGE == 'stride': set_stride(RIG)
if STAGE == 'all': finish(RIG)
