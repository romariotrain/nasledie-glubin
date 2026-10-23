"""Rebuild joint bands, bind a humanoid/coat rig, export and check deformation."""
import bpy, bmesh, math, json, hashlib, time
from pathlib import Path
from collections import defaultdict, deque
from mathutils import Vector, Quaternion
from mathutils.bvhtree import BVHTree

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'art/characters/swordsman/hunyuan_lowpoly_v002/swordsman_12k.glb'
HIGH=ROOT/'art/characters/swordsman/hunyuan_lowpoly_v002/swordsman_clean_high.glb'
VERSION='v004'
OUT=ROOT/f'art/characters/swordsman/hunyuan_animation_{VERSION}'
OUT.mkdir(parents=True,exist_ok=True)
assert not (OUT/f'swordsman_animation_{VERSION}.blend').exists(), 'Output already exists'
bpy.ops.wm.read_factory_settings(use_empty=True)

def load(path):
    previous=set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    return [o for o in bpy.data.objects if o not in previous and o.type=='MESH'][0]

obj=load(SOURCE)
# Imported glTF converts Y-up into Blender Z-up; topology work below uses
# original source coordinates for reproducible landmark positions.
for v in obj.data.vertices:
    p=obj.matrix_world@v.co
    v.co=(p.x,p.z,-p.y)
obj.matrix_world.identity()
high=load(HIGH)
high_vertices=[]
for v in high.data.vertices:
    p=high.matrix_world@v.co
    high_vertices.append(Vector((p.x,p.z,-p.y)))
high_bvh=BVHTree.FromPolygons(high_vertices,[list(p.vertices) for p in high.data.polygons],all_triangles=True)
bpy.data.objects.remove(high,do_unlink=True)
bm=bmesh.new(); bm.from_mesh(obj.data)
bm.verts.ensure_lookup_table()
joint_layer=bm.verts.layers.int.new('joint_band')
patch_reports=[]

def edge_loops(edges):
    adjacency=defaultdict(list)
    for e in edges:
        a,b=e.verts; adjacency[a].append(b); adjacency[b].append(a)
    remaining=set(adjacency)
    result=[]
    while remaining:
        seed=next(iter(remaining)); stack=[seed]; comp=set()
        while stack:
            v=stack.pop()
            if v in comp: continue
            comp.add(v); stack.extend(adjacency[v])
        remaining-=comp
        if len(comp)<6 or any(len(adjacency[v])!=2 for v in comp): continue
        ordered=[seed]; prev=None; current=seed
        for _ in range(len(comp)-1):
            nxt=next(x for x in adjacency[current] if x!=prev and (x!=seed or len(ordered)==len(comp)))
            ordered.append(nxt); prev,current=current,nxt
        result.append(ordered)
    return result

def ordered_loop(loop,axis,u,v):
    center=sum((x.co for x in loop),Vector())/len(loop)
    area=sum((loop[i].co-center).cross(loop[(i+1)%len(loop)].co-center).dot(axis) for i in range(len(loop)))
    if area<0: loop=list(reversed(loop))
    start=min(range(len(loop)),key=lambda i: math.atan2((loop[i].co-center).dot(v),(loop[i].co-center).dot(u)))
    return loop[start:]+loop[:start]

def samples(loop,n):
    coords=[v.co.copy() for v in loop]
    lengths=[(coords[(i+1)%len(coords)]-p).length for i,p in enumerate(coords)]
    total=sum(lengths); cumulative=[0]
    for d in lengths: cumulative.append(cumulative[-1]+d)
    points=[]
    for k in range(n):
        s=total*k/n
        i=next(i for i in range(len(lengths)) if cumulative[i+1]>=s)
        points.append(coords[i].lerp(coords[(i+1)%len(coords)],(s-cumulative[i])/max(lengths[i],1e-10)))
    return points,[d/total for d in cumulative]

def bridge(a,b):
    # Zipper transition for unequal boundary counts; no T-junctions.
    na,nb=len(a),len(b)
    i=j=0
    while i<na or j<nb:
        ta=(i+1)/na if i<na else 2
        tb=(j+1)/nb if j<nb else 2
        if abs(ta-tb)<1e-7:
            face=[a[i%na],a[(i+1)%na],b[(j+1)%nb],b[j%nb]];i+=1;j+=1
        elif ta<tb:
            face=[a[i%na],a[(i+1)%na],b[j%nb]];i+=1
        else:
            face=[a[i%na],b[(j+1)%nb],b[j%nb]];j+=1
        if len(set(face))>=3:
            bm.faces.new(face)

def rebuild_band(name,center,axis,halfwidth,segments=16):
    center=Vector(center);axis=Vector(axis).normalized()
    u=Vector((1,0,0));u=(u-axis*u.dot(axis)).normalized();v=axis.cross(u)
    planes=[center-axis*halfwidth,center+axis*halfwidth]
    boundaries=[]
    for plane in planes:
        bmesh.ops.bisect_plane(bm,geom=list(bm.verts)+list(bm.edges)+list(bm.faces),dist=1e-6,
                              plane_co=plane,plane_no=axis,clear_inner=False,clear_outer=False)
        edges=[e for e in bm.edges if all(abs((p.co-plane).dot(axis))<3e-5 for p in e.verts)]
        loops=edge_loops(edges)
        candidates=[]
        for loop in loops:
            c=sum((p.co for p in loop),Vector())/len(loop)
            distance=(c-plane).length
            radius=max((p.co-c).length for p in loop)
            if distance<0.18 and radius<0.24:
                candidates.append((distance,loop))
        if not candidates:
            raise RuntimeError(f'{name}: no isolated limb cross-section at {tuple(plane)}')
        boundaries.append(ordered_loop(min(candidates,key=lambda p:p[0])[1],axis,u,v))
    a,b=boundaries
    boundary_edges=set()
    for loop in boundaries:
        for i in range(len(loop)):
            boundary_edges.add(bm.edges.get((loop[i],loop[(i+1)%len(loop)])))
    def inside(face):
        s=(face.calc_center_median()-center).dot(axis)
        return -halfwidth-1e-5<s<halfwidth+1e-5
    seeds=[f for e in boundary_edges if e for f in e.link_faces if inside(f) and any(p in a for p in e.verts)]
    selected=set();q=list(seeds)
    while q:
        f=q.pop()
        if f in selected or not inside(f):continue
        selected.add(f)
        for e in f.edges:
            if e not in boundary_edges:q.extend(e.link_faces)
    if not selected or not any(any(v in b for v in f.verts) for f in selected):
        raise RuntimeError(name+': joint patch is not connected between both rings')
    if len(selected)>1600:raise RuntimeError(name+': selected region leaks into torso')
    removed=len(selected)
    points_a,_=samples(a,segments);points_b,_=samples(b,segments)
    bmesh.ops.delete(bm,geom=list(selected),context='FACES_ONLY')
    inner=[]
    for t in (.25,.5,.75):
        points=[pa.lerp(pb,t) for pa,pb in zip(points_a,points_b)]
        c=sum(points,Vector())/segments
        ring=[]
        for p in points:
            direction=p-c
            if direction.length>1e-6:
                hit,normal,_,distance=high_bvh.ray_cast(c,direction.normalized(),0.35)
                if hit is not None and 0.5*direction.length<distance<1.5*direction.length:
                    p=p.lerp(hit,.8)
            vertex=bm.verts.new(p);vertex[joint_layer]=1;ring.append(vertex)
        inner.append(ring)
    for loop in boundaries:
        for vertex in loop:vertex[joint_layer]=1
    rings=[a]+inner+[b]
    for first,second in zip(rings,rings[1:]):bridge(first,second)
    dangling=[v for v in bm.verts if not v.link_faces]
    if dangling:bmesh.ops.delete(bm,geom=dangling,context='VERTS')
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    patch_reports.append(dict(name=name,removed_faces=removed,boundary_counts=[len(a),len(b)],interior_rings=3,segments=segments))
    print('JOINT_PATCH',patch_reports[-1],flush=True)

patches=[
 ('Elbow.L',(.35,.215,.06),(.35,-.94,.02),.065),
 ('Elbow.R',(-.375,.215,-.075),(-.35,-.94,.02),.065),
 ('Knee.L',(.22,-.55,.045),(.10,-.995,-.02),.075),
 ('Knee.R',(-.225,-.55,-.04),(-.04,-.999,-.02),.075),
 ('Thigh.L',(.15,-.205,.06),(.14,-.99,-.03),.065),
 ('Thigh.R',(-.17,-.205,-.02),(-.12,-.99,-.03),.065),
 ('Shoulder.L',(.32,.31,.045),(.5,-.866,.03),.04),
 ('Shoulder.R',(-.34,.31,-.07),(-.5,-.866,.03),.04),
]
for specification in patches:rebuild_band(*specification)
def collapse_micro_edges(mesh):
    # Edge-collapse link condition preserves a closed manifold. Proximity
    # welding alone can incorrectly join thin, nearby coat surfaces.
    count=0
    for edge in list(mesh.edges):
        if not edge.is_valid or edge.calc_length()>=.0005 or not edge.is_manifold:continue
        if any(len(face.verts)!=3 for face in edge.link_faces):continue
        a,b=edge.verts
        neighbours_a={e.other_vert(a) for e in a.link_edges}
        neighbours_b={e.other_vert(b) for e in b.link_edges}
        if len(neighbours_a&neighbours_b)!=2:continue
        bmesh.ops.collapse(mesh,edges=[edge],uvs=False);count+=1
    return count
micro_collapsed=collapse_micro_edges(bm)
bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
bm.verts.index_update()
protected=[v.index for v in bm.verts if v[joint_layer]]
bm.to_mesh(obj.data);bm.free();obj.data.update()
obj.name='SK_Swordsman_Animation'
group=obj.vertex_groups.new(name='Retopo_Joint_Rings');group.add(protected,1.0,'REPLACE')
triangles=lambda:sum(len(p.vertices)-2 for p in obj.data.polygons)
bpy.context.view_layer.objects.active=obj;obj.select_set(True)
if triangles()>12000:
    modifier=obj.modifiers.new('Budget_outside_joint_bands','DECIMATE')
    modifier.ratio=11900/triangles();modifier.vertex_group=group.name
    modifier.invert_vertex_group=True;modifier.vertex_group_factor=1000
    bpy.ops.object.modifier_apply(modifier=modifier.name)
cleanup=bmesh.new();cleanup.from_mesh(obj.data)
micro_collapsed+=collapse_micro_edges(cleanup)
bmesh.ops.recalc_face_normals(cleanup,faces=list(cleanup.faces))
cleanup.to_mesh(obj.data);cleanup.free();obj.data.update()
assert 6000<=triangles()<=12000,(triangles(),'triangle budget')
# Convert to metres and Blender Z-up. Approximately 1.8 m from hair to soles.
source_coordinates=[v.co.copy() for v in obj.data.vertices]
def world(p):return Vector((p[0]*.9,-p[2]*.9,(p[1]+1)*.9))
for vertex,p in zip(obj.data.vertices,source_coordinates):vertex.co=world(p)
for p in obj.data.polygons:p.use_smooth=True
obj.data.update()

armature=bpy.data.armatures.new('Swordsman_Humanoid')
rig=bpy.data.objects.new('Rig_Swordsman',armature);bpy.context.collection.objects.link(rig)
rig.show_in_front=True;armature.display_type='OCTAHEDRAL'
bpy.context.view_layer.objects.active=rig;obj.select_set(False);rig.select_set(True)
bpy.ops.object.mode_set(mode='EDIT')
bone_specs=[]
def bone(name,head,tail,parent=None,deform=True):
    b=armature.edit_bones.new(name);b.head=world(head);b.tail=world(tail)
    if parent:b.parent=armature.edit_bones[parent]
    b.use_deform=deform;b.align_roll(Vector((0,-1,0)))
    bone_specs.append(dict(name=name,head=head,tail=tail,parent=parent,deform=deform))
bone('Root',(0,-1,0),(0,-.86,0),deform=False)
bone('Hips',(0,-.06,0),(0,.13,0),'Root')
bone('Spine',(0,.13,0),(0,.35,0),'Hips')
bone('Chest',(0,.35,0),(0,.56,0),'Spine')
bone('Neck',(0,.56,0),(0,.69,0),'Chest')
bone('Head',(0,.69,0),(0,.95,0),'Neck')
for side,sign in [('L',1),('R',-1)]:
    shoulder=(.225,.475,.04) if sign>0 else (-.245,.475,-.065)
    elbow=(.35,.215,.06) if sign>0 else (-.375,.215,-.075)
    wrist=(.415,.015,.12) if sign>0 else (-.445,.015,-.045)
    hand=(.445,-.125,.15) if sign>0 else (-.48,-.125,-.025)
    hip=(.145,-.09,.06) if sign>0 else (-.16,-.09,-.02)
    knee=(.22,-.55,.045) if sign>0 else (-.225,-.55,-.04)
    ankle=(.25,-.845,.02) if sign>0 else (-.245,-.845,-.055)
    ball=(.27,-.95,.18) if sign>0 else (-.27,-.95,.10)
    tip=(.28,-.95,.31) if sign>0 else (-.28,-.95,.20)
    bone('Shoulder.'+side,(0,.52,shoulder[2]),shoulder,'Chest')
    bone('UpperArm.'+side,shoulder,elbow,'Shoulder.'+side)
    bone('Forearm.'+side,elbow,wrist,'UpperArm.'+side)
    bone('Hand.'+side,wrist,hand,'Forearm.'+side)
    bone('Thigh.'+side,hip,knee,'Hips')
    bone('Shin.'+side,knee,ankle,'Thigh.'+side)
    bone('Foot.'+side,ankle,ball,'Shin.'+side)
    bone('Toe.'+side,ball,tip,'Foot.'+side)
    for direction,z0,z1,z2 in [('Front',.20,.26,.27),('Back',-.16,-.25,-.29)]:
        name=f'Coat_{direction}.{side}'
        bone(name,(sign*.16,.025,z0),(sign*.23,-.25,z1),'Hips')
        bone(name+'_Tip',(sign*.23,-.25,z1),(sign*.30,-.45,z2),name)
bone('WeaponSocket.R',(-.48,-.11,-.025),(-.48,-.20,-.025),'Hand.R',False)
bpy.ops.object.mode_set(mode='OBJECT')
obj.select_set(True);bpy.context.view_layer.objects.active=rig
bpy.ops.object.parent_set(type='ARMATURE_AUTO')
# Isolate the skirt surface below the waist by actual connectivity, avoiding
# assigning the front coat to the thighs merely because they are close.
adjacency=defaultdict(list)
for edge in obj.data.edges:
    a,b=edge.vertices;adjacency[a].append(b);adjacency[b].append(a)
remaining={i for i,p in enumerate(source_coordinates) if p.y<-.1}
coat_vertices=set()
while remaining:
    seed=next(iter(remaining));q=[seed];component=set()
    while q:
        i=q.pop()
        if i not in remaining:continue
        remaining.remove(i);component.add(i);q.extend(adjacency[i])
    points=[source_coordinates[i] for i in component]
    if points and min(p.y for p in points)>-.70 and max(p.x for p in points)-min(p.x for p in points)>.4:
        coat_vertices.update(component)
deform_names={b.name for b in rig.data.bones if b.use_deform}
for name in deform_names:
    if not obj.vertex_groups.get(name):obj.vertex_groups.new(name=name)
for vertex,p in zip(obj.data.vertices,source_coordinates):
    weights={obj.vertex_groups[g.group].name:g.weight for g in vertex.groups if obj.vertex_groups[g.group].name in deform_names and g.weight>1e-6}
    if vertex.index in coat_vertices:
        tip=max(0,min(1,(-p.y-.18)/.25))
        attach=max(0,min(1,(p.y+.35)/.30))
        left=max(0,min(1,(p.x+.18)/.36))
        front=max(0,min(1,(p.z+.08)/.16))
        weights={'Hips':attach}
        for side,side_factor in [('L',left),('R',1-left)]:
            for direction,front_factor in [('Front',front),('Back',1-front)]:
                base=f'Coat_{direction}.{side}'
                factor=side_factor*front_factor*(1-attach)
                weights[base]=(1-tip)*factor;weights[base+'_Tip']=tip*factor
    elif p.y>.71:
        weights={'Head':1}
    if not weights:
        # Fail explicitly if heat binding did not bind this surface.
        raise RuntimeError(f'Unweighted vertex {vertex.index} at {tuple(p)}')
    weights=dict(sorted(weights.items(),key=lambda kv:kv[1],reverse=True)[:4]);total=sum(weights.values())
    for name in deform_names:obj.vertex_groups[name].remove([vertex.index])
    for name,value in weights.items():
        if value>1e-6:obj.vertex_groups[name].add([vertex.index],value/total,'REPLACE')

# Smooth fields along mesh edges (rather than across nearby separate surfaces).
# This removes hard skirt/waist transitions and blends each joint band.
names=sorted(deform_names)
fields=[]
for vertex in obj.data.vertices:
    fields.append({obj.vertex_groups[g.group].name:g.weight for g in vertex.groups
                   if obj.vertex_groups[g.group].name in deform_names})
for iteration in range(20):
    updated=[]
    for i,values in enumerate(fields):
        neighbours=adjacency[i]
        if not neighbours:updated.append(values);continue
        result={name:weight*.5 for name,weight in values.items()}
        neighbour_weights=[1/max((obj.data.vertices[i].co-obj.data.vertices[j].co).length,.002)**2 for j in neighbours]
        neighbour_total=sum(neighbour_weights)
        for j,coefficient in zip(neighbours,neighbour_weights):
            for name,weight in fields[j].items():result[name]=result.get(name,0)+weight*.5*coefficient/neighbour_total
        # Intermediate fields retain more channels so smoothing cannot create
        # abrupt side boundaries merely through per-iteration truncation.
        result={name:value for name,value in result.items() if value>1e-5}
        total=sum(result.values());updated.append({name:value/total for name,value in result.items()})
    fields=updated
for vertex,values in zip(obj.data.vertices,fields):
    values=dict(sorted(values.items(),key=lambda item:item[1],reverse=True)[:4]);total=sum(values.values())
    for name in deform_names:obj.vertex_groups[name].remove([vertex.index])
    for name,value in values.items():obj.vertex_groups[name].add([vertex.index],value/total,'REPLACE')

# FK animation controls are the pose bones; lock irrelevant scaling.
for pb in rig.pose.bones:
    pb.rotation_mode='QUATERNION';pb.lock_scale=(True,True,True)
    if pb.name!='Root':pb.lock_location=(True,True,True)
    pb.bone.color.palette='THEME04' if pb.name.startswith('Coat') else 'THEME03'
def reset():
    for pb in rig.pose.bones:pb.rotation_quaternion=Quaternion();pb.location=(0,0,0)
def rotate(name,axis,degrees):
    pb=rig.pose.bones[name]
    local=pb.bone.matrix_local.to_quaternion().inverted()@Vector(axis)
    pb.rotation_quaternion=Quaternion(local,math.radians(degrees))
def pose(name):
    reset()
    if name=='elbows_90':
        rotate('Forearm.L',(1,0,0),-90);rotate('Forearm.R',(1,0,0),-90)
    elif name=='arms_raised':
        rotate('UpperArm.L',(0,1,0),-65);rotate('UpperArm.R',(0,1,0),65)
        rotate('Forearm.L',(1,0,0),-35);rotate('Forearm.R',(1,0,0),-35)
    elif name=='step':
        rotate('Thigh.L',(1,0,0),-40);rotate('Shin.L',(1,0,0),70)
        rotate('Thigh.R',(1,0,0),20);rotate('Shin.R',(1,0,0),20)
        rotate('UpperArm.R',(1,0,0),-25);rotate('UpperArm.L',(1,0,0),20)
        rotate('Coat_Front.L',(1,0,0),-35);rotate('Coat_Front.L_Tip',(1,0,0),-15)
        rotate('Coat_Back.R',(1,0,0),25)
    bpy.context.view_layer.update()

scene=bpy.context.scene;scene.render.fps=30
poses=[(1,'rest'),(30,'elbows_90'),(60,'arms_raised'),(90,'step'),(120,'rest')]
for frame,name in poses:
    scene.frame_set(frame);pose(name)
    for pb in rig.pose.bones:
        pb.keyframe_insert(data_path='rotation_quaternion',frame=frame,group=pb.name)
rig.animation_data.action.name='Deformation_Check'
scene.frame_start=1;scene.frame_end=120
rest=[v.co.copy() for v in obj.data.vertices]
edge_pairs=[tuple(e.vertices) for e in obj.data.edges]
deformation=[]
for frame,name in poses[:-1]:
    scene.frame_set(frame);bpy.context.view_layer.update()
    evaluated=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=evaluated.to_mesh()
    coords=[v.co.copy() for v in mesh.vertices]
    ratios=[]
    for a,b in edge_pairs:
        length=(rest[a]-rest[b]).length
        if length>1e-5:ratios.append((coords[a]-coords[b]).length/length)
    ratios.sort()
    assert all(math.isfinite(c) for p in coords for c in p)
    deformation.append(dict(pose=name,edge_stretch_p99=ratios[int(.99*len(ratios))],edge_stretch_max=max(ratios),edge_compression_min=min(ratios)))
    evaluated.to_mesh_clear()
scene.frame_set(1);reset()

# Studio and orthographic preview of the actual skinned mesh.
material=bpy.data.materials.new('Clay_Inspection');material.diffuse_color=(.42,.52,.62,1)
obj.data.materials.clear();obj.data.materials.append(material)
scene.render.engine='BLENDER_WORKBENCH'
scene.display.shading.light='STUDIO';scene.display.shading.color_type='MATERIAL'
scene.display.shading.show_cavity=True;scene.display.shading.cavity_type='BOTH'
scene.display.shading.show_shadows=True;scene.display.shading.show_object_outline=True
scene.display.shading.background_type='WORLD';scene.world=bpy.data.worlds.new('Studio')
scene.world.color=(.035,.045,.06)
scene.render.resolution_x=800;scene.render.resolution_y=900;scene.render.resolution_percentage=100
camera_data=bpy.data.cameras.new('InspectionCamera');camera=bpy.data.objects.new('InspectionCamera',camera_data)
bpy.context.collection.objects.link(camera);scene.camera=camera
camera.location=(2.5,-5,2.5);target=Vector((0,0,.95))
camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler()
camera_data.type='ORTHO';camera_data.ortho_scale=2.15
rig.hide_render=True
for frame,name in poses[:-1]:
    scene.frame_set(frame);scene.render.filepath=str(OUT/f'preview_{name}.png')
    bpy.ops.render.render(write_still=True)
# A short viewport-rendered deformation reel, not a locomotion animation.
frames_dir=OUT/'check_frames';frames_dir.mkdir(exist_ok=True)
scene.render.resolution_percentage=60
for frame in range(1,121,3):
    scene.frame_set(frame);scene.render.filepath=str(frames_dir/f'{frame:03}.png')
    bpy.ops.render.render(write_still=True)
scene.render.resolution_percentage=100
scene.frame_set(1);reset()

# Static validation includes the original bytes and normalized skin weights.
weight_checks=[]
for vertex in obj.data.vertices:
    values=[g.weight for g in vertex.groups if obj.vertex_groups[g.group].name in deform_names]
    assert 1<=len(values)<=4 and abs(sum(values)-1)<1e-5
meshcheck=bmesh.new();meshcheck.from_mesh(obj.data)
manifold=all(e.is_manifold for e in meshcheck.edges)
meshcheck.free()
assert manifold,'Non-manifold retopology'
report=dict(source=str(SOURCE),source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
            triangles=triangles(),vertices=len(obj.data.vertices),bones=len(rig.data.bones),
            deform_bones=len(deform_names),joint_patches=patch_reports,coat_weighted_vertices=len(coat_vertices),
            manifold=manifold,max_influences=4,normalized_weights=True,deformation=deformation,
            collapsed_submillimetre_edges=micro_collapsed,
            scale_note='Source approximately 2 units tall scaled to approximately 1.8 metres; A-pose rest.',
            limitations='FK prototype, no IK, no facial/finger rig, no UVs/textures, no engine import or automated self-intersection guarantee.')
(OUT/'rig_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
(OUT/'skeleton.json').write_text(json.dumps(bone_specs,indent=2),encoding='utf-8')
# Export only the character and rig, not inspection cameras.
bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);rig.select_set(True)
bpy.context.view_layer.objects.active=rig
# Explicit Beauty triangulation avoids the exporters choosing a diagonal that
# duplicates a tiny transition triangle. Editable joint quads stay in .blend.
editable_mesh=obj.data
export_mesh=editable_mesh.copy()
export_bm=bmesh.new();export_bm.from_mesh(export_mesh)
bmesh.ops.triangulate(export_bm,faces=list(export_bm.faces),quad_method='BEAUTY',ngon_method='BEAUTY')
assert all(e.is_manifold for e in export_bm.edges)
export_bm.to_mesh(export_mesh);export_bm.free();obj.data=export_mesh
bpy.ops.export_scene.gltf(filepath=str(OUT/f'SK_Swordsman_Anim_{VERSION}.glb'),export_format='GLB',
                          use_selection=True,export_animations=True,export_animation_mode='ACTIVE_ACTIONS',
                          export_influence_nb=4,export_skins=True,export_rest_position_armature=True,
                          export_cameras=False,export_lights=False,export_force_sampling=True)
bpy.ops.export_scene.fbx(filepath=str(OUT/f'SK_Swordsman_Anim_{VERSION}.fbx'),use_selection=True,
                         object_types={'ARMATURE','MESH'},add_leaf_bones=False,bake_anim=True,
                         bake_anim_use_all_actions=False,bake_anim_use_nla_strips=False,
                         axis_forward='-Z',axis_up='Y',use_armature_deform_only=False)
obj.data=editable_mesh;bpy.data.meshes.remove(export_mesh)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/f'swordsman_animation_{VERSION}.blend'))
print('RIG_REPORT',json.dumps(report),flush=True)
