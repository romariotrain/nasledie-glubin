import bpy,math,json,time,importlib.util
from pathlib import Path
from mathutils import Vector,Quaternion,Matrix
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'art/characters/swordsman/hunyuan_polished_v005';OUT.mkdir(parents=True,exist_ok=True)
scene=bpy.context.scene;obj=bpy.data.objects['SK_Swordsman_Animation'];rig=bpy.data.objects['Rig_Swordsman'];sword=bpy.data.objects['SM_Longsword']
names=[p.name for p in rig.pose.bones]
def capture():return {p.name:(p.rotation_quaternion.copy(),p.location.copy()) for p in rig.pose.bones}
def apply(pose):
    for name,(q,p) in pose.items():rig.pose.bones[name].rotation_quaternion=q;rig.pose.bones[name].location=p
    bpy.context.view_layer.update()
def blend(a,b,t):return {n:(a[n][0].slerp(b[n][0],t),a[n][1].lerp(b[n][1],t)) for n in names}
def ease(t):return t*t*t*(t*(t*6-15)+10)
clips={}
for name,length in [('Idle',61),('Walk_InPlace',31),('Slash_01',37)]:
    rig.animation_data.action=bpy.data.actions[name];frames=[]
    for frame in range(1,length+1):scene.frame_set(frame);bpy.context.view_layer.update();frames.append(capture())
    clips[name]=frames
rig.animation_data_clear()
identity={n:(Quaternion(),Vector()) for n in names};apply(identity)

# Close the existing mitten-like gloved fingers and reposition the sword axis
# in the palm. This is an authored combat grip, not a new five-finger rig.
hand=rig.data.bones['Hand.R'];inverse=hand.matrix_local.inverted();matrix=hand.matrix_local.copy()
hand_group=obj.vertex_groups['Hand.R'].index
grip_spec=importlib.util.spec_from_file_location('combat_grip',ROOT/'tools/blender/swordsman_combat_grip.py')
grip_module=importlib.util.module_from_spec(grip_spec);grip_spec.loader.exec_module(grip_module)
grip_report=grip_module.rebuild_grip(obj,rig,OUT);edited=grip_report['new_grip_vertices']
bpy.context.view_layer.objects.active=rig
bpy.ops.object.select_all(action='DESELECT');rig.select_set(True)
bpy.ops.object.mode_set(mode='EDIT')
socket=rig.data.edit_bones['WeaponSocket.R']
grip=matrix@Vector((0,.068,.025));axis=(matrix.to_3x3()@Vector((0,1,0))).normalized()
socket.head=grip;socket.tail=grip+axis*.08
bpy.ops.object.mode_set(mode='OBJECT');bpy.context.view_layer.update()
orientation=matrix.to_quaternion()@Vector((0,1,0)).to_track_quat('Z','Y')
sword.matrix_world=Matrix.Translation(grip)@orientation.to_matrix().to_4x4()
bpy.context.view_layer.update()

# Smooth attack entry/recovery so both boundaries equal the idle combat pose.
idle_pose=clips['Idle'][0]
slash=clips['Slash_01']
for i in range(7):slash[i]=blend(idle_pose,slash[i],ease(i/6))
for i in range(29,37):slash[i]=blend(slash[i],idle_pose,ease((i-29)/7))
slash[0]=blend(idle_pose,idle_pose,0);slash[-1]=blend(idle_pose,idle_pose,0)
clips['Start_Walk']=[blend(idle_pose,clips['Walk_InPlace'][0],ease(i/9)) for i in range(10)]
clips['Stop_Walk']=[blend(clips['Walk_InPlace'][-1],idle_pose,ease(i/9)) for i in range(10)]

spec=importlib.util.spec_from_file_location('collision_audit',ROOT/'tools/blender/audit_swordsman_collisions.py')
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
# Shape a rest-space coat envelope around the tested motion. No runtime
# simulation, extra morph targets or additional per-frame geometry are needed.
original_coat={i:obj.data.vertices[i].co.copy() for i in audit.coat}
bone_inverse={p.name:p.bone.matrix_local.inverted() for p in rig.pose.bones}
vertex_weights={v.index:[(obj.vertex_groups[g.group].name,g.weight) for g in v.groups
    if obj.vertex_groups[g.group].name in rig.pose.bones] for v in obj.data.vertices}
reports=[]
for iteration in range(10):
    proposals={};contact_count=0
    for name,frames in clips.items():
        for pose in frames:
            apply(pose);result=audit.evaluate(return_points=True)
            if not result['_records']:continue
            contact_count+=len(result['_records'])
            transforms={p.name:(p.matrix@bone_inverse[p.name]).to_3x3() for p in rig.pose.bones}
            for record in result['_records']:
                displacement=record['nearest']+record['normal']*.005-record['point']
                for i in record['indices']:
                    matrix=Matrix.Identity(3)*0
                    for bone,weight in vertex_weights[i]:matrix+=transforms[bone]*weight
                    delta=matrix.inverted_safe()@displacement
                    if i not in proposals or delta.length>proposals[i].length:proposals[i]=delta
    print('ENVELOPE',iteration,contact_count,len(proposals),flush=True)
    reports.append(dict(iteration=iteration,contact_samples=contact_count,corrected_vertices=len(proposals)))
    if not proposals:break
    # Move nearby inner/outer coat surfaces together to retain thickness.
    original_proposals=list(proposals.items())
    for i in audit.coat:
        p=obj.data.vertices[i].co
        for j,delta in original_proposals:
            if (p-obj.data.vertices[j].co).length<.018:
                if i not in proposals or delta.length>proposals[i].length:proposals[i]=delta
    for i,delta in proposals.items():
        if delta.length>.012:delta=delta.normalized()*.012
        point=obj.data.vertices[i].co+delta*.8
        change=point-original_coat[i]
        if change.length>.055:point=original_coat[i]+change.normalized()*.055
        obj.data.vertices[i].co=point
    obj.data.update()
final_clips={name:list(frames) for name,frames in clips.items()}
max_coat_displacement=max((obj.data.vertices[i].co-p).length for i,p in original_coat.items())

# Transition endpoints must be identical, including skirt corrections.
final_clips['Start_Walk'][0]=final_clips['Idle'][0]
final_clips['Start_Walk'][-1]=final_clips['Walk_InPlace'][0]
final_clips['Stop_Walk'][0]=final_clips['Walk_InPlace'][-1]
final_clips['Stop_Walk'][-1]=final_clips['Idle'][0]
final_clips['Slash_01'][0]=final_clips['Idle'][0]
final_clips['Slash_01'][-1]=final_clips['Idle'][0]
demo=[]
for name in ('Idle','Start_Walk','Walk_InPlace','Walk_InPlace','Stop_Walk','Slash_01','Idle'):
    demo.extend(final_clips[name][:-1])
demo.append(final_clips['Idle'][0]);final_clips['Game_Demo']=demo

# Keep only authored clips in the new file.
for action in list(bpy.data.actions):bpy.data.actions.remove(action)
for name,frames in final_clips.items():
    action=bpy.data.actions.new(name);action.use_fake_user=True
    rig.animation_data_create();rig.animation_data.action=action
    for frame,pose in enumerate(frames,1):
        scene.frame_set(frame);apply(pose)
        for pb in rig.pose.bones:
            pb.keyframe_insert(data_path='rotation_quaternion',frame=frame,group=pb.name)
            pb.keyframe_insert(data_path='location',frame=frame,group=pb.name)

# Remove redundant static/linear keys to reduce animation-editor overhead.
def curves(action):
    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                yield from bag.fcurves
def keep_rdp(points,tolerance):
    if len(points)<=2:return {0,len(points)-1}
    keep={0,len(points)-1};stack=[(0,len(points)-1)]
    while stack:
        a,b=stack.pop();start,end=points[a],points[b];worst=0;index=None
        for i in range(a+1,b):
            t=(points[i][0]-start[0])/(end[0]-start[0])
            error=abs(points[i][1]-(start[1]+(end[1]-start[1])*t))
            if error>worst:worst=error;index=i
        if worst>tolerance:keep.add(index);stack.extend([(a,index),(index,b)])
    return keep
before_keys=after_keys=0
for action in bpy.data.actions:
    for curve in curves(action):
        points=[p.co[:] for p in curve.keyframe_points];before_keys+=len(points)
        keep=keep_rdp(points,.00008)
        for i in reversed(range(len(points))):
            if i not in keep:curve.keyframe_points.remove(curve.keyframe_points[i],fast=True)
        for p in curve.keyframe_points:p.interpolation='LINEAR'
        curve.update();after_keys+=len(curve.keyframe_points)

# Verify every frame of every clip after simplification and endpoint stitching.
verification={}
for name,frames in final_clips.items():
    rig.animation_data.action=bpy.data.actions[name];bad=[]
    for frame in range(1,len(frames)+1):
        scene.frame_set(frame);bpy.context.view_layer.update();result=audit.evaluate()
        if result['penetrating_samples']:bad.append(dict(frame=frame,**result))
    verification[name]=bad
    print('FINAL_COLLISIONS',name,len(bad),flush=True)

scene.cycles.preview_samples=16;scene.cycles.samples=16
# Saved asset opens in fast, texture-coloured Solid mode; material preview is
# available on demand. Eevee is the default final engine in the delivered file.
for material in obj.data.materials:
    if material and material.use_nodes:
        for node in material.node_tree.nodes:
            if node.type=='TEX_IMAGE' and 'basecolor' in node.image.name.lower():material.node_tree.nodes.active=node
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            space=area.spaces.active;space.shading.type='SOLID';space.shading.color_type='TEXTURE'
            space.overlay.show_relationship_lines=False;space.overlay.show_bones=True
            space.region_3d.view_location=Vector((0,0,.95));space.region_3d.view_distance=3.2
            space.region_3d.view_rotation=(Vector((2.5,-5,2.5))-Vector((0,0,.95))).to_track_quat('Z','Y')
            space.region_3d.view_perspective='ORTHO'
scene.render.use_simplify=True
scene.cycles.preview_samples=16
rig.animation_data.action=bpy.data.actions['Idle'];scene.frame_set(1);scene.frame_start=1;scene.frame_end=61
for material in bpy.data.materials:
    if material.use_nodes:
        shader=material.node_tree.nodes.get('Principled BSDF')
        if shader:material.diffuse_color=shader.inputs['Base Color'].default_value
bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj
report=dict(edited_grip_vertices=edited,grip_rebuild=grip_report,socket_palm_local=[0,.068,.025],
    max_coat_rest_correction_metres=max_coat_displacement,collision_solver=reports,final_collision_frames=verification,
    collision_method='Coat vertices and triangle centroids vs leg BVH; horizontal parity; waist above z=.76 excluded; penetration threshold 1 mm.',
    keyframes_before=before_keys,keyframes_after=after_keys,
    clips={name:len(frames) for name,frames in final_clips.items()},
    limitations='No guarantee for poses outside these clips; fused mitten grip, not articulated fingers; game view is Blender preview, not Unity profiling.')
(OUT/'polish_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
# Eevee scene engine and cheap textured Solid viewport are stored in the file.
try:scene.render.engine='BLENDER_EEVEE'
except TypeError:scene.render.engine='CYCLES'
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'swordsman_polished_v005.blend'))
print('POLISH_REPORT',json.dumps(report),flush=True)
