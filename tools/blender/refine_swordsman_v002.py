"""Refine v001 as a new, compatible v002 .blend. Blender Python; no external assets."""
import bpy, bmesh, math, json, random, hashlib
from pathlib import Path
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'art/characters/swordsman/v001/swordsman_modular_v001.blend'
OUT=ROOT/'art/characters/swordsman/v002'
OUT.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
scene=bpy.context.scene
rig=bpy.data.objects['Rig_Swordsman']
source_hash=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
source_bones={b.name:[list(b.head_local),list(b.tail_local)] for b in rig.data.bones}
random.seed(23)

def material(name,color,rough=.7,metal=0):
    m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);m.use_nodes=True
    bs=m.node_tree.nodes.get('Principled BSDF')
    bs.inputs['Base Color'].default_value=(*color,1)
    bs.inputs['Roughness'].default_value=rough;bs.inputs['Metallic'].default_value=metal
    return m

skin=material('v002 | warm skin',(.39,.22,.137),.72)
lip=material('v002 | subtle lip',(.22,.09,.065),.75)
crease=material('v002 | facial crease',(.085,.035,.023),.8)
eye_white=material('v002 | ivory sclera',(.40,.36,.29),.4)
iris=material('v002 | brown iris',(.042,.023,.012),.3)
black=material('v002 | pupil',(.006,.004,.003),.32)
hair_mats=[material('v002 | hair umber '+str(i),c,.72) for i,c in enumerate([(.035,.015,.007),(.048,.021,.010),(.063,.027,.012),(.042,.018,.009)])]
coatmat=material('v002 | charcoal cloth',(.022,.026,.029),.85)
lapelmat=material('v002 | charcoal lapels',(.033,.035,.036),.8)
lining=material('v002 | burgundy lining',(.15,.016,.021),.87)
seammat=material('v002 | muted cloth seams',(.06,.048,.037),.86)
shirtmat=material('v002 | inner shirt',(.012,.014,.016),.9)
leather=material('v002 | worn leather',(.045,.023,.013),.66)
brass=material('v002 | aged brass',(.24,.135,.048),.4,.65)
altmat=material('v002 | slate blue jacket',(.023,.065,.073),.83)

def col(key):
    return next(c for c in bpy.data.collections if c.name.startswith(key+' |'))

def weights(obj,values):
    groups={}
    for i,d in enumerate(values):
        total=sum(d.values())
        for name,w in d.items():
            if w>1e-8:
                if name not in groups:groups[name]=obj.vertex_groups.new(name=name)
                groups[name].add([i],w/total,'REPLACE')
    obj.parent=rig
    mod=obj.modifiers.new('Shared skeleton','ARMATURE');mod.object=rig

def mesh(name,vs,fs,mat,collection,ws=None,smooth=True):
    me=bpy.data.meshes.new(name);me.from_pydata(vs,[],fs);me.update()
    o=bpy.data.objects.new(name,me);collection.objects.link(o);me.materials.append(mat)
    for p in me.polygons:p.use_smooth=smooth
    if ws:weights(o,ws)
    return o

def normalise_mesh(o):
    bm=bmesh.new();bm.from_mesh(o.data)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    bm.to_mesh(o.data);bm.free()

def apply(o,mod):
    bpy.context.view_layer.objects.active=o
    # Geometry is refined in rest space before skin deformation.
    idx=list(o.modifiers).index(mod)
    bpy.ops.object.modifier_move_to_index(modifier=mod.name,index=0)
    bpy.ops.object.modifier_apply(modifier=mod.name)

def ellipsoid(name,center,scale,mat,collection,bone='head',n=24,rings=16):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=n,ring_count=rings,radius=1,location=center)
    o=bpy.context.object;o.name=name;o.scale=scale
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    for c in list(o.users_collection):c.objects.unlink(o)
    collection.objects.link(o);o.data.materials.append(mat)
    for p in o.data.polygons:p.use_smooth=True
    if bone:weights(o,[{bone:1}]*len(o.data.vertices))
    return o

def path_tube(name,points,radii,mat,collection,ws=None,n=12,depth_ratio=1):
    vs=[];fs=[];ww=[]
    points=[Vector(p) for p in points]
    previous_u=None
    for i,p in enumerate(points):
        tangent=(points[min(i+1,len(points)-1)]-points[max(i-1,0)]).normalized()
        axis=previous_u.copy() if previous_u else Vector((1,0,0))
        if abs(tangent.dot(axis))>.98:axis=Vector((0,1,0))
        u=(axis-tangent*tangent.dot(axis)).normalized();v=tangent.cross(u).normalized()
        previous_u=u
        for j in range(n):
            a=math.tau*j/n
            vs.append(tuple(p+radii[i]*(u*math.cos(a)+v*math.sin(a)*depth_ratio)))
            if ws:ww.append(ws[i] if isinstance(ws,list) else ws)
    for i in range(len(points)-1):
        for j in range(n):
            q=i*n+j;r=i*n+(j+1)%n;fs.append((q,r,r+n,q+n))
    fs.extend([tuple(reversed(range(n))),tuple((len(points)-1)*n+j for j in range(n))])
    o=mesh(name,vs,fs,mat,collection,ww or None)
    normalise_mesh(o)
    return o

def bezier(points,t):
    a,b,c,d=[Vector(p) for p in points]
    return (1-t)**3*a+3*(1-t)**2*t*b+3*(1-t)*t*t*c+t**3*d

def line(name,points,radius,mat,collection,bone):
    return path_tube(name,points,[radius]*len(points),mat,collection,{bone:1},n=8)

def join(collection,name):
    objects=[o for o in collection.objects if o.type=='MESH']
    bpy.ops.object.select_all(action='DESELECT')
    for o in objects:o.select_set(True)
    bpy.context.view_layer.objects.active=objects[0]
    bpy.ops.object.join();o=objects[0];o.name=name
    o['module_id']=name;o['stage']='v002 face hair coat refinement'
    # Blender interpolates weights during subdivision; renormalize explicitly.
    for v in o.data.vertices:
        total=sum(g.weight for g in v.groups)
        if total:
            for g in list(v.groups):o.vertex_groups[g.group].add([v.index],g.weight/total,'REPLACE')
    return o

# Replace exposed anatomy while keeping the module identity and shared skeleton.
body=bpy.data.objects['Body_Exposed']
bpy.data.objects.remove(body,do_unlink=True)
ellipsoid('Neck',(0,.009,1.48),(.049,.047,.083),skin,col('01'),'neck',32,24)
for side,s in [('R',-1),('L',1)]:
    points=[(s*x,y,z) for x,y,z in [(.314,0,1.24),(.328,0,1.216),(.349,-.002,1.18),(.382,-.005,1.126),(.413,-.009,1.074),(.437,-.013,1.032)]]
    path_tube('Forearm',points,[.043,.044,.045,.041,.033,.028],skin,col('01'),{'forearm.'+side:1},n=32)
for key in ['03','10','11']:
    c=col(key);c.hide_viewport=False
    for o in list(c.objects):bpy.data.objects.remove(o,do_unlink=True)

# Anatomical ring profile: tapered jaw, cheeks, temples and domed skull.
profile=[(1.505,.022,.037,.039),(1.52,.039,.051,.044),(1.54,.054,.057,.050),
 (1.565,.066,.059,.058),(1.59,.075,.062,.066),(1.615,.075,.063,.070),
 (1.64,.073,.064,.071),(1.67,.071,.061,.069),(1.695,.062,.052,.058),
 (1.715,.039,.032,.037),(1.726,.003,.003,.003)]

def profile_at(z):
    for i in range(len(profile)-1):
        if z<=profile[i+1][0]:
            a,b=profile[i],profile[i+1];t=max(0,min(1,(z-a[0])/(b[0]-a[0])))
            prev=profile[max(0,i-1)];nxt=profile[min(len(profile)-1,i+2)]
            dz=b[0]-a[0]
            values=[]
            for j in [1,2,3]:
                m0=(b[j]-prev[j])/(b[0]-prev[0])*dz
                m1=(nxt[j]-a[j])/(nxt[0]-a[0])*dz
                values.append((2*t**3-3*t*t+1)*a[j]+(t**3-2*t*t+t)*m0+(-2*t**3+3*t*t)*b[j]+(t**3-t*t)*m1)
            return tuple(values)
    return profile[-1][1:]

def gauss(v,center,width):return math.exp(-((v-center)/width)**2)

def face_y(x,z):
    rx,front,back=profile_at(z)
    xn=min(.99999,abs(x)/rx)
    y=.007-front*(1-xn**2.8)**(1/2.8)
    # Features are part of the same surface, not a separate triangular nose.
    y-=.015*gauss(x,0,.010)*gauss(z,1.612,.032)
    y-=.016*gauss(x,0,.014)*gauss(z,1.593,.012)
    y-=.004*(gauss(x,.012,.006)+gauss(x,-.012,.006))*gauss(z,1.588,.007)
    y+=.007*(gauss(x,.032,.020)+gauss(x,-.032,.020))*gauss(z,1.627,.011)
    y-=.004*(gauss(x,.044,.019)+gauss(x,-.044,.019))*gauss(z,1.601,.014)
    y-=.003*gauss(x,0,.026)*gauss(z,1.56,.010)
    return y

vs=[];fs=[];N=80;R=74
for k in range(R):
    z=profile[0][0]+(profile[-1][0]-profile[0][0])*k/(R-1)
    rx,front,back=profile_at(z)
    for j in range(N):
        a=math.tau*j/N;x=rx*math.cos(a)
        y=face_y(x,z) if math.sin(a)<0 else .007+back*math.sin(a)
        vs.append((x,y,z))
for k in range(R-1):
    for j in range(N):
        a=k*N+j;b=k*N+(j+1)%N;fs.append((a,b,b+N,a+N))
fs += [tuple(reversed(range(N))),tuple((R-1)*N+j for j in range(N))]
head=mesh('SculptedHead',vs,fs,skin,col('01'),[{'head':1}]*len(vs))
normalise_mesh(head)

for s in [-1,1]:
    ellipsoid('Ear',(s*.074,.008,1.605),(.012,.018,.026),skin,col('01'))
    ellipsoid('EarConcha',(s*.081,-.003,1.606),(.004,.011,.016),lip,col('01'))
    # Almond-shaped eye surface inset into the sculpted socket.
    cx=s*.032;cz=1.627;ev=[];ef=[]
    for row in range(7):
        q=row/6
        for j in range(25):
            t=j/24;x=cx+(t-.5)*.034
            curve=math.sin(math.pi*t)**.8
            slant=s*(x-cx)*.10
            z=cz+slant+(2*q-1)*(.0048 if q>=.5 else .0037)*curve
            y=face_y(x,z)-.0015-.003*curve*math.sin(math.pi*q)
            ev.append((x,y,z))
    for row in range(6):
        for j in range(24):
            a=row*25+j;ef.append((a,a+1,a+26,a+25))
    mesh('EyeAlmond',ev,ef,eye_white,col('01'),[{'head':1}]*len(ev))
    ey=face_y(cx,cz)-.005
    ellipsoid('Iris',(cx,ey,cz),(.0046,.0012,.0048),iris,col('01'),n=24,rings=12)
    ellipsoid('Pupil',(cx,ey-.001,cz),(.0022,.0006,.0030),black,col('01'),n=16,rings=12)
    for upper in [True,False]:
        pp=[]
        for j in range(21):
            t=j/20;x=cx+(t-.5)*.035
            z=cz+s*(x-cx)*.1+(.0053 if upper else -.0042)*math.sin(math.pi*t)**.8
            pp.append((x,face_y(x,z)-.002,z))
        line('Eyelid',pp,.00135 if upper else .001,skin,col('01'),'head')
    # Tapered eyebrow: raised outer corner, lower inner corner, serious expression.
    pp=[]
    for i in range(13):
        t=i/12;x=s*(.012+.044*t);z=1.638+.007*math.sin(math.pi*t*.9)
        pp.append((x,face_y(x,z)-.0017,z))
    path_tube('Eyebrow',pp,[.0015+.0022*math.sin(math.pi*i/12) for i in range(13)],hair_mats[0],col('01'),{'head':1},n=8,depth_ratio=.55)
    # Small nostril, following the skin surface.
    x=s*.009;z=1.588
    ellipsoid('Nostril',(x,face_y(x,z)-.0008,z),(.0034,.001,.0017),crease,col('01'),n=16,rings=10)

mouth=[]
for i in range(25):
    x=-.022+.044*i/24;z=1.567+.0017*math.cos(x/.022*math.pi*.5)
    mouth.append((x,face_y(x,z)-.001,z))
path_tube('MouthLine',mouth,[.00045+.00055*math.sin(math.pi*i/24) for i in range(25)],crease,col('01'),{'head':1},n=8)
lipline=[(x,y+.0001,z-.0025) for x,y,z in mouth[3:-3]]
path_tube('LowerLip',lipline,[.0008+.0006*math.sin(math.pi*i/(len(lipline)-1)) for i in range(len(lipline))],lip,col('01'),{'head':1},n=8)
body=join(col('01'),'Body_Exposed')

# Hair is a continuous cap covered by curved tapered locks, with asymmetry.
hv=[];hf=[];H=48;V=18
for k in range(V):
    for j in range(H):
        a=math.tau*j/H
        # Front hairline higher, sides/back wrap lower around the skull.
        front=max(0,-math.sin(a))
        bottom=1.615+.062*front-.02*max(0,math.sin(a))
        z=bottom+(1.748-bottom)*k/(V-1)
        rx,fd,bd=profile_at(min(z,1.695))
        if z>1.695:
            radius=math.sqrt(max(.0001,1-((z-1.68)/.069)**2))
            rx=.082*radius;fd=.077*radius;bd=.087*radius
        else:
            rx+=.009;fd+=.012;bd+=.009
        x=rx*math.cos(a)
        y=.007-fd*(max(.00001,1-abs(math.cos(a))**2.8))**(1/2.8) if math.sin(a)<0 else .007+bd*math.sin(a)
        hv.append((x,y,z))
for k in range(V-1):
    for j in range(H):
        a=k*H+j;b=k*H+(j+1)%H;hf.append((a,b,b+H,a+H))
hf.append(tuple((V-1)*H+j for j in range(H)))
cap=mesh('HairCap',hv,hf,hair_mats[0],col('03'),[{'head':1}]*len(hv));normalise_mesh(cap)

def lock(name,control,width,depth,index):
    pts=[bezier(control,i/14) for i in range(15)]
    radii=[]
    for i in range(15):
        t=i/14
        radii.append(max(.00035,width*(.65+.55*math.sin(math.pi*t))*(1-t)**.65))
    return path_tube(name,pts,radii,hair_mats[index%4],col('03'),{'head':1},n=12,depth_ratio=depth/width)

# Swept fringe: overlapping locks with a few shorter breaks over the brow.
fringe=[
 ((-.049,-.003,1.721),(-.052,-.042,1.721),(-.075,-.072,1.677),(-.08,-.061,1.635),.018,.012),
 ((-.025,-.017,1.74),(-.024,-.055,1.735),(-.056,-.085,1.683),(-.06,-.071,1.646),.022,.013),
 ((.006,-.012,1.745),(.015,-.056,1.738),(-.026,-.091,1.683),(-.035,-.077,1.651),.022,.013),
 ((.035,-.003,1.732),(.05,-.044,1.734),(.012,-.085,1.691),(.003,-.077,1.663),.020,.012),
 ((.059,.011,1.713),(.078,-.022,1.713),(.052,-.081,1.681),(.043,-.066,1.648),.019,.012),
 ((.072,.028,1.685),(.086,-.008,1.691),(.079,-.047,1.653),(.072,-.037,1.618),.015,.009),
]
for i,values in enumerate(fringe):lock('SweptFringe_%02d'%i,values[:4],values[4],values[5]*.6,i)
for i in range(14):
    a=math.radians(5+i*170/13)
    x=.065*math.cos(a);y=.012+.058*math.sin(a)
    layer=i%2;lean=-.018 if x<0 else .018
    control=[(x*.65,y*.6,1.731-layer*.024), (x*1.10+lean,y*1.1,1.733-layer*.025),
             (x*1.38+lean,y*1.5,1.684-layer*.028), (x*1.40+lean,y*1.56,1.647-layer*.044+random.uniform(-.008,.008))]
    lock('LayeredBack_%02d'%i,control,.020+random.random()*.005,.006,i+1)
# The fringe and staggered rear layers meet over the crown.
hair=join(col('03'),'Hair_Starter')

def body_weights(z):
    if z<1.065:return {'pelvis':1}
    if z<1.19:
        t=(z-1.065)/.125;return {'pelvis':1-t,'spine':t}
    if z<1.30:
        t=(z-1.19)/.11;return {'spine':1-t,'chest':t}
    return {'chest':1}

def cloth_shell(name,rings,mat,collection,n=48,start=-68,end=248,lining_mat=None):
    vs=[];fs=[];ww=[]
    for k,(z,rx,ry) in enumerate(rings):
        for j in range(n+1):
            a=math.radians(start+(end-start)*j/n)
            # Small low-frequency cloth ridges, not noisy surface bumps.
            wrinkle=.002*math.sin(5*a+z*25)*math.sin(math.pi*k/(len(rings)-1))
            vs.append(((rx+wrinkle)*math.cos(a),(ry+wrinkle*.4)*math.sin(a),z))
            ww.append(body_weights(z))
    for k in range(len(rings)-1):
        for j in range(n):
            a=k*(n+1)+j;fs.append((a,a+1,a+n+2,a+n+1))
    ob=mesh(name,vs,fs,mat,collection,ww)
    sub=ob.modifiers.new('Cloth contour refinement','SUBSURF');sub.levels=1;apply(ob,sub)
    if lining_mat:ob.data.materials.append(lining_mat)
    sol=ob.modifiers.new('Cloth thickness','SOLIDIFY');sol.thickness=.004;sol.offset=0
    if lining_mat:sol.material_offset=1
    apply(ob,sol)
    return ob

def fabric_patch(name,left,right,mat,collection,bone,thickness=.003):
    vs=[];fs=[]
    for k in range(17):
        t=k/16;a=bezier(left,t);b=bezier(right,t)
        for j in range(7):
            q=j/6;p=a.lerp(b,q)
            p.y-=.003*math.sin(math.pi*q)*math.sin(math.pi*t)
            vs.append(tuple(p))
    for k in range(16):
        for j in range(6):
            a=k*7+j;fs.append((a,a+1,a+8,a+7))
    ob=mesh(name,vs,fs,mat,collection,[{bone:1}]*len(vs))
    so=ob.modifiers.new('Fold thickness','SOLIDIFY');so.thickness=thickness;apply(ob,so)
    return ob

def top(collection,short=False):
    fabric=altmat if short else coatmat
    # Chest and rolled sleeves are shaped volumes, replacing the shoulder balls.
    cloth_shell('FittedCoatBody',[(1.025,.142,.099),(1.06,.145,.101),(1.12,.142,.098),(1.19,.15,.104),
      (1.27,.175,.109),(1.33,.187,.105),(1.38,.200,.092),(1.405,.19,.078),(1.43,.118,.065),(1.455,.065,.053)],fabric,collection,lining_mat=lining)
    cloth_shell('InnerShirt',[(1.025,.133,.092),(1.16,.13,.089),(1.30,.174,.098),(1.39,.148,.072),(1.44,.059,.05)],shirtmat,collection,start=0,end=360)
    for side,s in [('R',-1),('L',1)]:
        # Anatomical sleeve path intersects the shoulder naturally, without a spherical cap.
        ellipsoid('ShoulderUnderlap',(s*.17,0,1.389),(.052,.064,.043),fabric,collection,'upper_arm.'+side,32,20)
        points=[(s*x,0,z) for x,z in [(.15,1.38),(.205,1.39),(.239,1.363),(.27,1.324),(.297,1.279),(.32,1.239)]]
        ws=[{'chest':.35,'upper_arm.'+side:.65},{'chest':.15,'upper_arm.'+side:.85}]+[{'upper_arm.'+side:1}]*4
        sleeve=path_tube('TailoredSleeve',points,[.050,.071,.070,.067,.062,.057],fabric,collection,ws,n=32)
        bm=bmesh.new();bm.from_mesh(sleeve.data)
        bmesh.ops.delete(bm,geom=[f for f in bm.faces if len(f.verts)>4],context='FACES_ONLY')
        bm.to_mesh(sleeve.data);bm.free()
        sub=sleeve.modifiers.new('Sleeve contour','SUBSURF');sub.levels=1;apply(sleeve,sub)
        for k in range(3):
            points=[(s*(.304+k*.006+t*.010),0,1.266-k*.010-t*.015) for t in [0,.25,.5,.75,1]]
            path_tube('RolledCuff',points,[.059,.063,.064,.062,.058],lining if k==1 else fabric,collection,{'upper_arm.'+side:1},n=32)
        # Curved lapels lie close to the chest instead of floating triangular plates.
        left=[(s*.049,-.055,1.455),(s*.066,-.086,1.398),(s*.049,-.110,1.31),(s*.038,-.101,1.205)]
        right=[(s*.072,-.052,1.455),(s*.137,-.103,1.39),(s*.109,-.114,1.32),(s*.038,-.101,1.205)]
        fabric_patch('SoftLapel',left,right,lapelmat if not short else leather,collection,'chest')
        pp=[bezier(right,i/24)+Vector((0,-.0015,0)) for i in range(25)]
        line('LapelPiping',pp,.0011,seammat,collection,'chest')
        # Tall folded collar framing the scarf.
        collarL=[(s*.028,-.043,1.455),(s*.036,-.033,1.49),(s*.06,.002,1.485),(s*.06,.046,1.458)]
        collarR=[(s*.071,-.052,1.441),(s*.083,-.023,1.48),(s*.083,.028,1.479),(s*.042,.061,1.448)]
        fabric_patch('CoatCollar',collarL,collarR,fabric,collection,'chest')
        if not short:
            vs=[];fs=[];ww=[];rows=19;segments=32
            for k in range(rows):
                t=k/(rows-1)
                for j in range(segments+1):
                    u=j/segments;a=math.radians(-66+151*u)
                    # Hem reaches near the knee at the back; open corners taper upward.
                    hem=.645+.095*(1-u)**3+.035*u**8
                    z=1.041*(1-t)+hem*t
                    rx=.144+(.202-.144)*math.sqrt(t)+.010*math.sin(math.pi*t)
                    ry=.099+(.145-.099)*math.sqrt(t)
                    fold=.006*math.sin(a*6+.4)*t**1.4+.003*math.sin(a*11)*t
                    x=s*(rx+fold)*math.cos(a);y=(ry+fold*.7)*math.sin(a)+.022*t*t
                    # slight turned-out edges reveal a narrow red lining
                    y-=.013*(1-u)**8*t
                    vs.append((x,y,z))
                    w=t*t*(3-2*t);ww.append({'pelvis':1-w,'coat.'+side:w})
            for k in range(rows-1):
                for j in range(segments):
                    a=k*(segments+1)+j;f=(a,a+1,a+segments+2,a+segments+1)
                    fs.append(tuple(reversed(f)) if s==1 else f)
            tail=mesh('DrapedTail',vs,fs,fabric,collection,ww)
            tail.data.materials.append(lining)
            sol=tail.modifiers.new('Red silk lining','SOLIDIFY');sol.thickness=.005;sol.offset=0;sol.material_offset=1;apply(tail,sol)
            # Modest red facing at open front edge, attached to same tail bone.
            left=[(s*.058,-.089,1.037),(s*.063,-.101,.92),(s*.078,-.113,.80),(s*.087,-.12,.741)]
            right=[(s*.067,-.09,1.037),(s*.074,-.103,.92),(s*.092,-.116,.80),(s*.100,-.121,.75)]
            fabric_patch('RedFrontFacing',left,right,lining,collection,'coat.'+side,.002)
    # Continuous scarf with shallow folds rather than separate tubular necklaces.
    for k in range(1):
        vs=[];fs=[];n=48
        for row in range(17):
            t=row/16
            for j in range(n):
                a=math.tau*j/n
                front=max(0,-math.sin(a))
                z=1.447+.044*t-.038*front**3
                fold=.0018*math.sin(math.pi*t*5)
                vs.append(((.061+fold)*math.cos(a),(.063+fold)*math.sin(a)+.002,z))
        for row in range(16):
            for j in range(n):
                a=row*n+j;b=row*n+(j+1)%n;fs.append((a,b,b+n,a+n))
        o=mesh('ScarfDrape',vs,fs,lining,collection,[{'chest':1}]*len(vs))
        so=o.modifiers.new('Scarf thickness','SOLIDIFY');so.thickness=.002;apply(o,so)
    # Waist belt and compact buckle, matched to the existing modular trousers.
    cloth_shell('Belt',[(1.039,.151,.108),(1.043,.152,.109),(1.075,.149,.108),(1.079,.148,.106)],leather,collection,start=0,end=360)
    corners=[(-.023,-.115,1.045),(.023,-.115,1.045),(.023,-.115,1.074),(-.023,-.115,1.074),(-.023,-.115,1.045)]
    line('Buckle',corners,.0032,brass,collection,'pelvis')
    line('BucklePin',[(0,-.118,1.045),(0,-.118,1.075)],.0015,brass,collection,'pelvis')
    for z in [1.14,1.21,1.28]:ellipsoid('Button',(.063,-.111,z),(.004,.003,.004),brass,collection,'spine' if z<1.25 else 'chest',16,8)
    # Small layered heraldic sleeve patch, visible in the concept.
    crest=[(.271,-.063,1.347),(.291,-.064,1.327),(.282,-.063,1.304),(.262,-.061,1.323),(.271,-.063,1.347)]
    line('GuildBadge',crest,.002,brass,collection,'upper_arm.L')
    line('GuildBadgeSlash',[(.268,-.064,1.318),(.285,-.066,1.337)],.0016,brass,collection,'upper_arm.L')
    return join(collection,'Top_ShortJacket' if short else 'Top_Longcoat')

coat=top(col('10'))
jacket=top(col('11'),True)
# Smooth surrounding existing parts so the face/coat do not clash with faceted limbs.
for name in ['Legs_Trousers','Hands_Gloves','Feet_Boots','Body_Covered']:
    for p in bpy.data.objects[name].data.polygons:p.use_smooth=True
for m in bpy.data.materials:
    if m.name.startswith('Skin |'):
        bs=m.node_tree.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=(.39,.22,.137,1)
        m.diffuse_color=(.39,.22,.137,1)

col('11').hide_viewport=True;col('11').hide_render=True
col('10').hide_viewport=False;col('10').hide_render=False
col('51').hide_viewport=True;col('51').hide_render=True
col('50').hide_viewport=False;col('50').hide_render=False
rig['next_stage']='Review v002 silhouette; improve garment deformation and Unity import.'
for c in bpy.data.collections:
    if c.name.startswith('CHARACTER'):c.name='CHARACTER | Swordsman v002'
bpy.data.texts['README_FIRST'].clear()
bpy.data.texts['README_FIRST'].write('SWORDSMAN v002\nFace, curved hair locks and longcoat refinement.\nSame skeleton, module names and weapon sockets as v001.\nUse SWAP_EQUIPMENT.py to switch top and sword variants.\nNo final UV textures, combat animation or Unity validation yet.\n')

def point_at(o,p):o.rotation_euler=(Vector(p)-o.location).to_track_quat('-Z','Y').to_euler()
cam=scene.camera
scene.cycles.samples=40
scene.render.resolution_x=1000;scene.render.resolution_y=1200
for name,energy,color in [('Key | warm',400,(1,.85,.71)),('Fill | cool',240,(.66,.78,1)),('Rim',300,(1,.70,.45))]:
    o=bpy.data.objects[name];o.data.energy=energy;o.data.color=color
scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.3
cam.location=(2.9,-5.4,2.75);point_at(cam,(0,0,.86));cam.data.ortho_scale=2.22
bpy.ops.object.select_all(action='DESELECT');coat.select_set(True);bpy.context.view_layer.objects.active=coat
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            space=area.spaces.active;space.shading.type='MATERIAL'
            space.region_3d.view_distance=2.8;space.region_3d.view_location=(0,0,.88)
            space.region_3d.view_rotation=cam.rotation_euler.to_quaternion()

blend=OUT/'swordsman_modular_v002.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(blend))
for filename,location,target,scale in [
 ('preview_front.png',(2.9,-5.4,2.75),(0,0,.86),2.22),
 ('preview_back.png',(-2.9,5.4,2.6),(0,0,.86),2.22),
 ('preview_portrait.png',(.75,-2.8,1.92),(0,-.008,1.58),.52),
 ('preview_game_camera.png',(3,-5,5.4),(0,0,.87),2.3),
]:
    cam.location=location;point_at(cam,target);cam.data.ortho_scale=scale
    scene.render.filepath=str(OUT/filename);bpy.ops.render.render(write_still=True)
cam.location=(2.9,-5.4,2.75);point_at(cam,(0,0,.86));cam.data.ortho_scale=2.22
col('10').hide_render=True;col('11').hide_render=False
col('50').hide_render=True;col('51').hide_render=False
scene.render.filepath=str(OUT/'preview_alternative.png');bpy.ops.render.render(write_still=True)
col('10').hide_render=False;col('11').hide_render=True
col('50').hide_render=False;col('51').hide_render=True
scene.render.filepath=str(OUT/'preview_front.png')
report={'version':'v002','source':str(SOURCE.relative_to(ROOT)),'source_sha256':source_hash,'changes':['Integrated sculpted face and almond eyes','Curved layered hair locks','Longer draped coat with fitted sleeves, collar, folds and red lining','Both top variants retain shared rig and module IDs'],'bones_preserved':source_bones=={b.name:[list(b.head_local),list(b.tail_local)] for b in rig.data.bones},'modules':{}}
for o in bpy.data.objects:
    if o.type=='MESH' and o.parent==rig:
        o.data.calc_loop_triangles()
        report['modules'][o.name]={'vertices':len(o.data.vertices),'triangles':len(o.data.loop_triangles)}
report['limitations']=['Provisional topology/weights, no animation-ready certification','No UV painting or Unity import check','Separate mesh patches remain at garment junctions']
(OUT/'build_report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
bpy.ops.wm.save_as_mainfile(filepath=str(blend))
assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==source_hash
print('V002_REFINEMENT_COMPLETE',str(blend))
