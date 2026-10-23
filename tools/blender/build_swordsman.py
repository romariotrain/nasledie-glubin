"""Build the first modular swordsman study. Run with Blender --background --factory-startup --python."""
import bpy
import math
import json
import hashlib
from pathlib import Path
from mathutils import Vector, Matrix

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'art' / 'characters' / 'swordsman' / 'v001'
OUT.mkdir(parents=True, exist_ok=True)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
for c in list(bpy.data.collections):
    if c.name != 'Collection':
        bpy.data.collections.remove(c)
base = bpy.data.collections.get('Collection')
base.name = 'CHARACTER | Swordsman v001'
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
scene.unit_settings.scale_length = 1.0

def collection(name):
    c = bpy.data.collections.new(name)
    base.children.link(c)
    return c

cols = {k: collection(v) for k, v in {
    'body': '01 | Body visible', 'covered': '02 | Body covered [hidden]',
    'hair': '03 | Hair', 'coat': '10 | TOP - Longcoat [active]',
    'jacket': '11 | TOP - Short jacket [alternative]',
    'pants': '20 | LEGS - Trousers', 'gloves': '30 | HANDS - Gloves',
    'boots': '40 | FEET - Boots', 'sword': '50 | WEAPON - Longsword [active]',
    'sword_alt': '51 | WEAPON - Relic sword [alternative]',
    'rig': '00 | Rig and sockets', 'studio': '90 | Preview studio',
}.items()}

def mat(name, color, metallic=0.0, rough=.65):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*color, 1)
    m.use_nodes = True
    p = m.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value = (*color, 1)
    p.inputs['Roughness'].default_value = rough
    p.inputs['Metallic'].default_value = metallic
    return m

M = {
    'skin': mat('Skin | warm ochre', (.48, .265, .15)),
    'skin_light': mat('Skin | raised planes', (.59, .34, .20)),
    'hair': mat('Hair | dark umber', (.055, .025, .014)),
    'hair_tip': mat('Hair | copper planes', (.12, .052, .022)),
    'coat': mat('Coat | charcoal', (.035, .043, .047)),
    'lapel': mat('Coat | raised lapels', (.075, .083, .084)),
    'lining': mat('Lining | oxblood', (.25, .027, .025)),
    'shirt': mat('Shirt | near black', (.018, .022, .025)),
    'pants': mat('Trousers | slate', (.048, .055, .065)),
    'leather': mat('Leather | warm dark brown', (.065, .033, .019)),
    'trim': mat('Leather | edge piping', (.16, .079, .033)),
    'metal': mat('Steel | cool', (.34, .43, .49), .8, .28),
    'edge': mat('Steel | cutting edge', (.66, .73, .75), .85, .22),
    'gold': mat('Hardware | aged brass', (.42, .26, .08), .7, .36),
    'eye': mat('Eyes | dark', (.012, .009, .007), .0, .28),
    'white': mat('Eyes | warm white', (.63, .57, .45)),
    'alt': mat('Jacket | muted blue green', (.035, .105, .12)),
    'floor': mat('Studio | slate', (.028, .038, .047)),
}

def move(obj, col):
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    col.objects.link(obj)

# One deform rig in Blender coordinates: Z up, front -Y.
arm = bpy.data.armatures.new('Swordsman_Skeleton')
rig = bpy.data.objects.new('Rig_Swordsman', arm)
cols['rig'].objects.link(rig)
bpy.context.view_layer.objects.active = rig
rig.select_set(True)
bpy.ops.object.mode_set(mode='EDIT')
bones = {}
def bone(name, head, tail, parent=None):
    b = arm.edit_bones.new(name)
    b.head, b.tail = head, tail
    if parent:
        b.parent = bones[parent]
    bones[name] = b

bone('root', (0, 0, 0), (0, 0, .18))
bone('pelvis', (0, 0, .88), (0, 0, 1.03), 'root')
bone('spine', (0, 0, 1.03), (0, 0, 1.23), 'pelvis')
bone('chest', (0, 0, 1.23), (0, 0, 1.43), 'spine')
bone('neck', (0, 0, 1.43), (0, 0, 1.53), 'chest')
bone('head', (0, 0, 1.53), (0, 0, 1.72), 'neck')
for side, s in [('R', -1), ('L', 1)]:
    bone('clavicle.'+side, (0,0,1.40), (s*.205,0,1.40), 'chest')
    bone('upper_arm.'+side, (s*.205,0,1.40), (s*.335,0,1.205), 'clavicle.'+side)
    bone('forearm.'+side, (s*.335,0,1.205), (s*.435,-.012,1.035), 'upper_arm.'+side)
    bone('hand.'+side, (s*.435,-.012,1.035), (s*.475,-.025,.96), 'forearm.'+side)
    bone('thigh.'+side, (s*.105,0,.98), (s*.12,-.006,.555), 'pelvis')
    bone('shin.'+side, (s*.12,-.006,.555), (s*.14,.01,.135), 'thigh.'+side)
    bone('foot.'+side, (s*.14,.01,.135), (s*.14,-.14,.055), 'shin.'+side)
    bone('coat.'+side, (s*.105,.055,1.035), (s*.15,.07,.78), 'pelvis')
bpy.ops.object.mode_set(mode='OBJECT')
rig.show_in_front = True
rig.display_type = 'WIRE'
rig.select_set(False)

def weights(obj, data):
    groups = {}
    for i, ws in enumerate(data):
        for b, w in ws.items():
            if w > 0:
                if b not in groups:
                    groups[b] = obj.vertex_groups.new(name=b)
                groups[b].add([i], w, 'REPLACE')
    mod = obj.modifiers.new('Shared skeleton', 'ARMATURE')
    mod.object = rig
    obj.parent = rig

def mesh(name, verts, faces, material, col, ws=None, bevel=0):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    ob = bpy.data.objects.new(name, me)
    col.objects.link(ob)
    ob.data.materials.append(M[material])
    if ws:
        weights(ob, ws)
    if bevel:
        m = ob.modifiers.new('Soft manufactured edges', 'BEVEL')
        m.width, m.segments = bevel, 1
    return ob

def ellipsoid(name, center, scale, material, col, b=None, segments=12, rings=8):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=rings, radius=1, location=center)
    ob = bpy.context.object
    ob.name = name
    ob.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    move(ob, col)
    ob.data.materials.append(M[material])
    if b:
        weights(ob, [{b:1} for _ in ob.data.vertices])
    return ob

def loft(name, rings, material, col, n=12, capped=True):
    # rings: center, x radius, y radius, weights. Cross sections in XY.
    verts, faces, ws = [], [], []
    for center, rx, ry, w in rings:
        for j in range(n):
            a = math.tau*j/n
            verts.append((center[0]+rx*math.cos(a), center[1]+ry*math.sin(a), center[2]))
            ws.append(w)
    for k in range(len(rings)-1):
        for j in range(n):
            a=k*n+j; b=k*n+(j+1)%n
            faces.append((a,b,b+n,a+n))
    if capped:
        faces.extend([tuple(reversed(range(n))),tuple((len(rings)-1)*n+j for j in range(n))])
    if rings[-1][0][2] < rings[0][0][2]:
        faces = [tuple(reversed(f)) for f in faces]
    return mesh(name, verts, faces, material, col, ws)

def tube(name, a, b, radii, material, col, bone_name=None, n=10):
    a,b=Vector(a),Vector(b)
    d=(b-a).normalized()
    u=d.cross(Vector((0,1,0))).normalized()
    v=d.cross(u).normalized()
    verts,faces=[],[]
    for k,r in enumerate(radii):
        center=a.lerp(b,k/(len(radii)-1))
        for j in range(n):
            p=center+r*(u*math.cos(math.tau*j/n)+v*math.sin(math.tau*j/n))
            verts.append(tuple(p))
    for k in range(len(radii)-1):
        for j in range(n):
            q=k*n+j;t=k*n+(j+1)%n
            faces.append((q,t,t+n,q+n))
    faces += [tuple(reversed(range(n))),tuple((len(radii)-1)*n+j for j in range(n))]
    return mesh(name,verts,faces,material,col,[{bone_name:1}]*len(verts) if bone_name else None)

def panel(name, points, material, col, b, thick=.004):
    ob=mesh(name,points,[tuple(range(len(points)))],material,col,[{b:1}]*len(points))
    if thick:
        m=ob.modifiers.new('Cloth thickness','SOLIDIFY');m.thickness=thick
    return ob

# Base anatomy, separated where clothing covers it.
loft('Body_Torso', [((0,0,z),x,y,w) for z,x,y,w in [
    (.90,.13,.075,{'pelvis':1}),(1.03,.12,.075,{'pelvis':.6,'spine':.4}),
    (1.16,.11,.075,{'spine':1}),(1.30,.17,.09,{'chest':1}),
    (1.40,.19,.075,{'chest':1}),(1.45,.07,.055,{'neck':1})]],'skin',cols['covered'])
loft('Neck', [((0,0,1.42),.054,.052,{'neck':1}),((0,0,1.54),.048,.045,{'head':.5,'neck':.5})], 'skin',cols['body'])
loft('Head', [((0,y,z),rx,ry,{'head':1}) for z,y,rx,ry in [
    (1.505,-.025,.035,.035),(1.535,-.012,.058,.05),(1.575,0,.073,.062),
    (1.625,.005,.076,.065),(1.67,.01,.068,.058),(1.705,.012,.035,.035)]], 'skin',cols['body'],n=12)
for s in [-1,1]:
    ellipsoid('Ear', (s*.074,.003,1.596),(.014,.019,.029),'skin',cols['body'],'head',10,6)
    ellipsoid('BrowPlane',(s*.031,-.055,1.628),(.030,.012,.011),'skin_light',cols['body'],'head')
    ellipsoid('EyeWhite',(s*.029,-.060,1.615),(.014,.005,.004),'white',cols['body'],'head')
    ellipsoid('Iris',(s*.029,-.064,1.615),(.004,.002,.004),'eye',cols['body'],'head')
    panel('Brow',[(s*.009,-.066,1.63),(s*.050,-.057,1.636),(s*.049,-.061,1.628),(s*.012,-.069,1.624)],'hair',cols['body'],'head')
mesh('Nose', [(-.01,-.059,1.628),(.01,-.059,1.628),(-.012,-.063,1.585),(.012,-.063,1.585),(0,-.084,1.59)], [(0,1,4),(0,4,2),(1,3,4),(2,4,3)], 'skin_light',cols['body'],[{'head':1}]*5)
panel('Mouth',[(-.022,-.057,1.561),(0,-.062,1.558),(.021,-.057,1.561),(.012,-.059,1.556),(-.012,-.059,1.556)],'leather',cols['body'],'head',.001)

# Hair cap and angular locks following a swept silhouette.
loft('HairCap',[((0,.012,z),x,y,{'head':1}) for z,x,y in [(1.63,.078,.064),(1.675,.081,.07),(1.714,.053,.048),(1.731,.015,.015)]],'hair',cols['hair'])
def lock(name,base,tip,width,depth,material='hair'):
    base,tip=Vector(base),Vector(tip)
    mid=base.lerp(tip,.53)+Vector((0,-.006,.008))
    verts=[tuple(base+Vector((-width,0,0))),tuple(base+Vector((0,depth,0))),tuple(base+Vector((width,0,0))),tuple(base+Vector((0,-depth,0))),tuple(mid+Vector((-width*.65,0,0))),tuple(mid+Vector((0,depth*.5,0))),tuple(mid+Vector((width*.65,0,0))),tuple(mid+Vector((0,-depth*.5,0))),tuple(tip)]
    faces=[(3,2,1,0),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7),(4,5,8),(5,6,8),(6,7,8),(7,4,8)]
    mesh(name,verts,faces,material,cols['hair'],[{'head':1}]*len(verts))
for i,(a,b,w,d) in enumerate([
    ((-.045,-.027,1.701),(-.087,-.068,1.633),.022,.021),
    ((-.015,-.038,1.714),(-.048,-.082,1.622),.025,.022),
    ((.017,-.037,1.717),(-.005,-.091,1.644),.025,.021),
    ((.045,-.026,1.703),(.029,-.081,1.653),.023,.019),
    ((.062,-.005,1.686),(.081,-.057,1.618),.018,.022),
    ((-.065,.013,1.672),(-.091,-.017,1.594),.018,.025),
    ((.063,.027,1.67),(.09,.004,1.60),.02,.02),
    ((-.043,.035,1.709),(-.08,.066,1.746),.024,.022),
    ((-.007,.041,1.727),(-.018,.079,1.766),.025,.025),
    ((.027,.035,1.721),(.058,.078,1.748),.026,.024),
    ((0,.055,1.675),(.012,.091,1.613),.044,.018),
]): lock('HairLock_%02d'%i,a,b,w,d,'hair_tip' if i%3==0 else 'hair')

for side,s in [('R',-1),('L',1)]:
    arm_top=(s*.218,0,1.395); elbow=(s*.335,0,1.205); wrist=(s*.435,-.012,1.035)
    tube('UpperArm.'+side,arm_top,elbow,[.055,.061,.044],'skin',cols['covered'],'upper_arm.'+side)
    tube('Forearm.'+side,elbow,wrist,[.043,.046,.029],'skin',cols['body'],'forearm.'+side)
    ellipsoid('Elbow.'+side,elbow,(.044,.043,.044),'skin',cols['body'],'forearm.'+side)
    ellipsoid('Hand.'+side,(s*.458,-.02,.997),(.035,.032,.057),'skin',cols['covered'],'hand.'+side)
    loft('Leg.'+side,[((s*x,0,z),rx,ry,{b+'.'+side:1}) for z,x,rx,ry,b in [(.98,.10,.08,.075,'thigh'),(.76,.11,.072,.067,'thigh'),(.56,.12,.049,.05,'shin'),(.36,.13,.048,.047,'shin'),(.14,.14,.032,.035,'foot')]],'skin',cols['covered'])

# Shirt and scarf are part of each top variant; coat is an open-front shell.
def make_top(col, short=False):
    fabric='alt' if short else 'coat'
    loft('Undershirt', [((0,0,z),rx,ry,{b:1}) for z,rx,ry,b in [(1.00,.127,.082,'pelvis'),(1.16,.123,.084,'spine'),(1.31,.179,.093,'chest'),(1.415,.15,.064,'chest')]],'shirt',col)
    # Angular open front: angles -68 .. 248 pass across right side and back to left.
    angles=[math.radians(-68+i*316/18) for i in range(19)]
    levels=[(1.025,.142,.096),(1.16,.142,.10),(1.31,.19,.11),(1.405,.215,.086),(1.449,.072,.067)]
    verts=[];ws=[];faces=[]
    for z,rx,ry in levels:
        for a in angles:
            verts.append((rx*math.cos(a),ry*math.sin(a),z))
            ws.append({'pelvis':1} if z<1.06 else {'spine':1} if z<1.25 else {'chest':1})
    for k in range(len(levels)-1):
        for j in range(18):
            a=k*19+j;faces.append((a,a+1,a+20,a+19))
    coat=mesh('JacketShell' if short else 'CoatShell',verts,faces,fabric,col,ws)
    coat.data.materials.append(M['lining'])
    mod=coat.modifiers.new('Red lining thickness','SOLIDIFY');mod.thickness=.007;mod.material_offset=1
    # Long split panels left and right, attached to dedicated coat bones.
    for side,s in [('R',-1),('L',1)]:
        if not short:
            verts=[];ww=[];ff=[]
            # Side-specific panels wrap from front opening toward split back.
            aa=[math.radians(-65+i*151/9) for i in range(10)]
            for k,(z,rx,ry) in enumerate([(1.032,.143,.097),(.90,.175,.112),(.745,.209,.14)]):
                for j,a in enumerate(aa):
                    zz=z+(.045 if k==2 and j in (0,9) else 0)
                    verts.append((s*rx*math.cos(a),ry*math.sin(a),zz))
                    ww.append({'pelvis':1} if k==0 else {'coat.'+side:1})
            for k in range(2):
                for j in range(9):
                    a=k*10+j;ff.append((a,a+1,a+11,a+10))
            if s == 1:
                ff = [tuple(reversed(f)) for f in ff]
            ob=mesh('CoatTail.'+side,verts,ff,fabric,col,ww)
            ob.data.materials.append(M['lining'])
            mod=ob.modifiers.new('Visible red lining','SOLIDIFY');mod.thickness=.009;mod.material_offset=1
            panel('RedTailFlash.'+side,[(s*.076,-.094,1.025),(s*.09,-.118,.895),(s*.107,-.132,.785),(s*.125,-.12,.80),(s*.11,-.105,.92)],'lining',col,'coat.'+side)
        panel('Lapel.'+side,[(s*.052,-.058,1.447),(s*.13,-.095,1.367),(s*.065,-.111,1.235),(s*.032,-.091,1.335)],'lapel' if not short else 'leather',col,'chest')
        # Sleeves terminate above the elbow to expose the forearms.
        ellipsoid('ShoulderCap.'+side,(s*.211,0,1.383),(.071,.075,.071),fabric,col,'upper_arm.'+side)
        tube('Sleeve.'+side,(s*.216,0,1.391),(s*.317,0,1.235),[.066,.071,.057],fabric,col,'upper_arm.'+side)
        tube('RolledCuff.'+side,(s*.303,0,1.255),(s*.326,0,1.22),[.060,.061,.056],'lining',col,'upper_arm.'+side)
        panel('ShoulderSeam.'+side,[(s*.145,-.06,1.412),(s*.22,-.049,1.411),(s*.267,-.039,1.36),(s*.252,-.047,1.351)],'trim',col,'upper_arm.'+side)
    # Scarf makes the red accent visible from a high camera.
    loft('RedCollar',[((0,-.003,1.427),.068,.062,{'neck':1}),((0,-.003,1.478),.061,.057,{'neck':1})],'lining',col,n=10)
    panel('ScarfFold',[(-.048,-.066,1.44),(0,-.09,1.386),(.043,-.068,1.44),(.018,-.081,1.46)],'lining',col,'chest')
    loft('Belt',[((0,0,1.037),.149,.104,{'pelvis':1}),((0,0,1.083),.147,.103,{'pelvis':1})],'leather',col)
    # Buckle ring with visible dark center.
    for a,b in [((-.026,-.111,1.043),(.026,-.111,1.043)),((-.026,-.111,1.079),(.026,-.111,1.079)),((-.026,-.111,1.043),(-.026,-.111,1.079)),((.026,-.111,1.043),(.026,-.111,1.079))]:
        tube('Buckle',a,b,[.004,.004],'gold',col,'pelvis',6)
    for z in [1.17,1.25,1.32]:
        ellipsoid('CoatStud',(.072,-.107,z),(.005,.004,.005),'gold',col,'spine' if z<1.25 else 'chest',8,4)
    # Sleeve insignia: compact brass diamond shape, not a copied logo.
    panel('GuildInsignia',[(.27,-.059,1.36),(.294,-.059,1.334),(.284,-.059,1.305),(.26,-.059,1.331)],'gold',col,'upper_arm.L')

make_top(cols['coat'])
make_top(cols['jacket'],True)
loft('TrouserWaist',[((0,0,.87),.142,.084,{'pelvis':1}),((0,0,.955),.177,.096,{'pelvis':1}),((0,0,1.058),.137,.087,{'pelvis':1})],'pants',cols['pants'])
for side,s in [('R',-1),('L',1)]:
    loft('TrouserLeg.'+side,[((s*x,y,z),rx,ry,ws) for z,x,y,rx,ry,ws in [
        (.96,.098,0,.075,.084,{'pelvis':.25,'thigh.'+side:.75}),
        (.82,.107,0,.086,.088,{'thigh.'+side:1}),
        (.66,.115,-.003,.069,.068,{'thigh.'+side:1}),
        (.565,.12,-.006,.054,.055,{'thigh.'+side:.5,'shin.'+side:.5}),
        (.48,.124,0,.051,.050,{'shin.'+side:1}),
        (.39,.13,.005,.046,.045,{'shin.'+side:1})]],'pants',cols['pants'])
    # Front knee planes, no separate hard armor in the starter outfit.
    ellipsoid('KneeFold.'+side,(s*.12,-.049,.56),(.047,.012,.038),'lapel',cols['pants'],'shin.'+side,8,6)
    loft('BootShaft.'+side,[((s*x,y,z),rx,ry,ws) for z,x,y,rx,ry,ws in [
        (.10,.14,.01,.046,.052,{'foot.'+side:1}),
        (.20,.138,.012,.047,.046,{'shin.'+side:1}),
        (.34,.132,.005,.060,.057,{'shin.'+side:1}),
        (.45,.126,0,.058,.056,{'shin.'+side:1})]],'leather',cols['boots'])
    ellipsoid('BootToe.'+side,(s*.14,-.067,.075),(.057,.122,.062),'leather',cols['boots'],'foot.'+side)
    ellipsoid('BootSole.'+side,(s*.14,-.065,.032),(.06,.126,.025),'shirt',cols['boots'],'foot.'+side)
    for z,rx,ry in [(.215,.051,.05),(.34,.064,.061),(.44,.062,.060)]:
        loft('BootStrap.'+side,[((s*(.14-(z-.14)*.04),.005,z-.012),rx,ry,{'shin.'+side:1}),((s*(.14-(z-.14)*.04),.005,z+.012),rx,ry,{'shin.'+side:1})],'trim',cols['boots'])
        ellipsoid('BootBuckle.'+side,(s*.164,-ry+.003,z),(.012,.006,.009),'gold',cols['boots'],'shin.'+side,8,4)
    # Fingerless glove, shaped palm, knuckles and thumb.
    tube('GloveCuff.'+side,(s*.411,-.01,1.079),(s*.439,-.013,1.03),[.035,.038,.034],'leather',cols['gloves'],'forearm.'+side)
    ob=ellipsoid('GlovePalm.'+side,(s*.458,-.023,1.001),(.034,.032,.052),'leather',cols['gloves'],'hand.'+side)
    ob.rotation_euler[1]=s*.42
    for i in range(4):
        ellipsoid('Finger.'+side,(s*(.457+i*.009),-.042+i*.011,.966),(.010,.011,.021),'skin',cols['gloves'],'hand.'+side,8,6)
    ellipsoid('Thumb.'+side,(s*.43,-.048,.99),(.015,.017,.026),'skin',cols['gloves'],'hand.'+side,8,6)
    tube('GloveStrap.'+side,(s*.419,-.01,1.068),(s*.426,-.011,1.056),[.039,.039],'trim',cols['gloves'],'forearm.'+side)

# Join each module, applying geometric modifiers while keeping the shared rig modifier.
def join_module(col, name, skinned=True):
    objs=[o for o in col.objects if o.type=='MESH']
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        bpy.context.view_layer.objects.active=o
        for m in list(o.modifiers):
            if m.type!='ARMATURE':
                bpy.ops.object.modifier_apply(modifier=m.name)
        o.select_set(True)
    bpy.context.view_layer.objects.active=objs[0]
    bpy.ops.object.join()
    ob=objs[0];ob.name=name
    ob['module_id']=name
    ob['stage']='v001 silhouette and modularity study'
    return ob

modules={}
for key,name in [('body','Body_Exposed'),('covered','Body_Covered'),('hair','Hair_Starter'),('coat','Top_Longcoat'),('jacket','Top_ShortJacket'),('pants','Legs_Trousers'),('gloves','Hands_Gloves'),('boots','Feet_Boots')]:
    modules[key]=join_module(cols[key],name)

# Weapons authored along local -Z and rigidly attached to the right-hand socket.
bpy.context.view_layer.update()
socket=bpy.data.objects.new('Socket_Weapon_R',None)
cols['rig'].objects.link(socket)
socket.empty_display_type='ARROWS';socket.empty_display_size=.07
socket.parent=rig;socket.parent_type='BONE';socket.parent_bone='hand.R'
socket.matrix_world=Matrix.Translation(Vector((-.47,-.034,.982))) @ Matrix.Rotation(math.radians(16),4,'Y')
bpy.context.view_layer.update()

def weapon(col,alt=False):
    # Model coordinates relative to the grip, with a long diamond-section blade.
    width=.037 if alt else .027
    stations=[(-.095,width*.65),(-.145,width),(-.70,width*.82),(-.82,width*.52),(-.92,0)]
    verts=[]
    for z,w in stations:
        verts += [(-w,0,z),(0,-.008,z),(w,0,z),(0,.008,z)]
    faces=[]
    for k in range(len(stations)-1):
        for j in range(4):
            a=k*4+j;b=k*4+(j+1)%4;faces.append((a,b,b+4,a+4))
    blade=mesh('Blade',verts,faces,'metal',col)
    blade.data.materials.append(M['edge'])
    for p in blade.data.polygons:p.material_index=p.index%2
    tube('Grip',(0,0,-.075),(0,0,.065),[.016,.019,.016],'leather',col,None,10)
    for z in [-.058,-.036,-.014,.008,.030,.052]:
        tube('GripWrap',(0,0,z-.003),(0,0,z+.003),[.0195,.0195],'trim',col,None,10)
    tube('Pommel',(0,0,.062),(0,0,.1),[.021,.025,.012],'gold',col,None,8)
    points=[(-.115,0,-.055),(-.065,0,-.082),(0,0,-.09),(.065,0,-.082),(.115,0,-.055)]
    for a,b in zip(points,points[1:]):tube('Guard',a,b,[.012,.014],'gold',col,None,8)
    if alt:
        ellipsoid('RelicGem',(0,-.016,-.101),(.018,.009,.024),'lining',col,None,8,6)
        panel('BladeInlay',[(-.008,-.009,-.17),(.008,-.009,-.17),(.004,-.009,-.58),(0,-.009,-.64),(-.004,-.009,-.58)],'gold',col,'hand.R',.001)
        # Inlay is rigid with the weapon, not separately skinned.
        ob=bpy.context.object
        for o in col.objects:
            for m in list(o.modifiers):
                if m.type=='ARMATURE':o.modifiers.remove(m)
            o.parent=None
    ob=join_module(col,'Weapon_RelicSword' if alt else 'Weapon_Longsword',False)
    # Joined coordinates keep local origin at world origin; explicitly reset to socket local space.
    bpy.context.view_layer.objects.active=ob
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
    ob.parent=socket
    ob.matrix_parent_inverse=Matrix.Identity(4)
    ob.location=(0,0,0);ob.rotation_euler=(0,0,0);ob.scale=(1,1,1)
    return ob
modules['sword']=weapon(cols['sword'])
modules['sword_alt']=weapon(cols['sword_alt'],True)

for key in ['covered','jacket','sword_alt']:
    cols[key].hide_render=True
    cols[key].hide_viewport=True
rig['visual_front']='-Y; Z up; meters'
rig['shared_skeleton']='All clothing binds to this armature. Weapons use Socket_Weapon_R.'
rig['next_stage']='Refine topology and weights; test in Unity; author combat animations.'

# Embedded toggle helper, usable directly from Blender Text Editor.
toggle="""import bpy
# Set 'longcoat' / 'jacket' and 'longsword' / 'relic', then Run Script.
TOP = 'longcoat'
WEAPON = 'longsword'
for name, active in {
 '10 | TOP - Longcoat [active]': TOP == 'longcoat',
 '11 | TOP - Short jacket [alternative]': TOP == 'jacket',
 '50 | WEAPON - Longsword [active]': WEAPON == 'longsword',
 '51 | WEAPON - Relic sword [alternative]': WEAPON == 'relic',
}.items():
 c=bpy.data.collections[name]
 c.hide_viewport = not active
 c.hide_render = not active
"""
bpy.data.texts.new('SWAP_EQUIPMENT.py').write(toggle)
bpy.data.texts.new('README_FIRST').write('SWORDSMAN v001\nModular silhouette study, 2026-10-15.\nFront = -Y, Z up, meters.\nCollections 10/11: choose one top. Collections 50/51: choose one sword.\nSWAP_EQUIPMENT.py switches both viewport and render visibility.\nBody_Covered is a fitting reference and remains hidden under both tops.\nOne shared deform skeleton; no final combat animations or Unity import yet.\nMaterials are flat color placeholders; UV painting and production topology are future work.\n')

# Neutral preview studio; not part of character export.
bpy.ops.mesh.primitive_cylinder_add(vertices=96, radius=.88, depth=.035, location=(0,0,-.025))
ground=bpy.context.object;ground.name='Preview_Platform';move(ground,cols['studio']);ground.data.materials.append(M['floor'])
bev=ground.modifiers.new('Platform edge','BEVEL');bev.width=.015;bev.segments=3
scene.world.color=(.08,.08,.08)
scene.world.use_nodes=True
scene.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.09,.12,.16,1)
scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.35
def point_at(o,point):o.rotation_euler=(Vector(point)-o.location).to_track_quat('-Z','Y').to_euler()
def light(name,location,energy,color,size):
    data=bpy.data.lights.new(name,'AREA');data.energy=energy;data.color=color;data.shape='DISK';data.size=size
    o=bpy.data.objects.new(name,data);cols['studio'].objects.link(o);o.location=location;point_at(o,(0,0,1))
light('Key | warm',(-3,-4,5),450,(1,.78,.58),4)
light('Fill | cool',(3,-2,2.6),280,(.55,.73,1),3)
light('Rim',(1,3,3.2),650,(1,.44,.18),2.5)
camdata=bpy.data.cameras.new('Preview_Camera');cam=bpy.data.objects.new('Preview_Camera',camdata);cols['studio'].objects.link(cam)
camdata.type='ORTHO';camdata.ortho_scale=2.22
cam.location=(2.9,-5.4,2.75);point_at(cam,(0,0,.86));scene.camera=cam
scene.render.engine='CYCLES';scene.cycles.samples=32
scene.cycles.use_denoising=True
scene.render.resolution_x=1000;scene.render.resolution_y=1200;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'
scene.view_settings.view_transform='AgX'
scene.render.film_transparent=False

# Useful viewport when the blend is opened interactively.
bpy.ops.object.select_all(action='DESELECT')
modules['coat'].select_set(True);bpy.context.view_layer.objects.active=modules['coat']
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            space=area.spaces.active
            space.shading.type='MATERIAL'
            space.overlay.show_floor=False
            space.region_3d.view_distance=2.8
            space.region_3d.view_location=(0,0,.88)
            space.region_3d.view_rotation=cam.rotation_euler.to_quaternion()

blend=OUT/'swordsman_modular_v001.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(blend))
scene.render.filepath=str(OUT/'preview_front.png');bpy.ops.render.render(write_still=True)
cam.location=(-2.9,5.4,2.6);point_at(cam,(0,0,.86))
scene.render.filepath=str(OUT/'preview_back.png');bpy.ops.render.render(write_still=True)
cam.location=(2.9,-5.4,2.75);point_at(cam,(0,0,.86))
cols['coat'].hide_render=True;cols['jacket'].hide_render=False
cols['sword'].hide_render=True;cols['sword_alt'].hide_render=False
scene.render.filepath=str(OUT/'preview_alternative.png');bpy.ops.render.render(write_still=True)
cols['coat'].hide_render=False;cols['jacket'].hide_render=True
cols['sword'].hide_render=False;cols['sword_alt'].hide_render=True
scene.render.filepath=str(OUT/'preview_front.png')

report={'stage':'v001 modular silhouette study','blender':bpy.app.version_string,'shared_rig':rig.name,'bone_count':len(arm.bones),'modules':{},'limitations':['No Unity import/export verification','No final combat animations','Provisional deformation weights and disconnected mesh patches','Flat materials, no painted UV textures','No claim of final game readiness']}
for key,o in modules.items():
    o.data.calc_loop_triangles()
    report['modules'][key]={'object':o.name,'vertices':len(o.data.vertices),'triangles':len(o.data.loop_triangles),'armature_modifiers':sum(m.type=='ARMATURE' for m in o.modifiers),'vertex_groups':len(o.vertex_groups)}
(OUT/'build_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
bpy.ops.wm.save_as_mainfile(filepath=str(blend))
print('SWORDSMAN_BUILD_COMPLETE',str(blend))
