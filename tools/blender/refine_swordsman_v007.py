"""Slim the existing character and author reference-directed run/combat motion."""
import bpy, ast, math, json, shutil, hashlib, importlib.util
from pathlib import Path
from mathutils import Vector, Quaternion, Matrix

ROOT=Path(__file__).resolve().parents[2]
SOURCE=Path(bpy.data.filepath)
OUT=ROOT/'art/characters/swordsman/hunyuan_combat_v007';OUT.mkdir(parents=True,exist_ok=True)
scene=bpy.context.scene;rig=bpy.data.objects['Rig_Swordsman'];obj=bpy.data.objects['SK_Swordsman_Animation'];sword=bpy.data.objects['SM_Longsword']
old_rest={b.name:b.matrix_local.copy() for b in rig.data.bones}
old_points=[v.co.copy() for v in obj.data.vertices]
old_sword=sword.matrix_world.copy()
# Capture the old FK deformation operators, so unchanged clips can follow the slimmer rig.
unchanged={}
for name in ('idle','piercing_lunge','hurt','death'):
    rig.animation_data.action=bpy.data.actions[name];frames=[]
    for frame in range(1,round(bpy.data.actions[name].frame_range[1])+1):
        scene.frame_set(frame);bpy.context.view_layer.update()
        frames.append({p.name:p.matrix@old_rest[p.name].inverted() for p in rig.pose.bones})
    unchanged[name]=frames
rig.animation_data_clear()
for p in rig.pose.bones:p.location=(0,0,0);p.rotation_quaternion=(1,0,0,0);p.scale=(1,1,1)
bpy.context.view_layer.update()
old_sword=sword.matrix_world.copy()

def smooth(a,b,t):
    u=max(0,min(1,(t-a)/(b-a)));return u*u*(3-2*u)
def width(z):
    keys=[(0,.94),(.45,.94),(.85,.88),(1.20,.91),(1.40,.91),(1.56,1),(1.9,1)]
    for (a,x),(b,y) in zip(keys,keys[1:]):
        if a<=z<=b:return x+(y-x)*smooth(a,b,z)
    return 1
def warp(p):
    depth=.88 if .80<=p.z<=1.4 else 1-.12*smooth(.60,.80,p.z)*(1-smooth(1.4,1.56,p.z))
    return Vector((p.x*width(p.z),p.y*depth,p.z))

audit_spec=importlib.util.spec_from_file_location('parts',ROOT/'tools/blender/audit_swordsman_collisions.py')
parts=importlib.util.module_from_spec(audit_spec);audit_spec.loader.exec_module(parts)
weights={v.index:{obj.vertex_groups[g.group].name:g.weight for g in v.groups} for v in obj.data.vertices}
bpy.ops.object.select_all(action='DESELECT');rig.select_set(True);bpy.context.view_layer.objects.active=rig
bpy.ops.object.mode_set(mode='EDIT')
for b in rig.data.edit_bones:
    if b.name=='WeaponSocket.R':continue
    head,tail=b.head.copy(),b.tail.copy();b.head=warp(head);b.tail=warp(tail)
    if b.name.startswith('Hand.'):b.tail=b.head+(tail-head)
hand=rig.data.edit_bones['Hand.R'];hand_map=hand.matrix@old_rest['Hand.R'].inverted()
socket=rig.data.edit_bones['WeaponSocket.R']
socket.head=hand_map@old_rest['WeaponSocket.R'].translation
socket.tail=hand_map@(old_rest['WeaponSocket.R']@Vector((0,.08,0)))
bpy.ops.object.mode_set(mode='OBJECT');bpy.context.view_layer.update()
new_rest={b.name:b.matrix_local.copy() for b in rig.data.bones}
for v,p in zip(obj.data.vertices,old_points):
    q=warp(p)
    if v.index in parts.legs:
        side='L' if p.x>0 else 'R'
        centres=[old_rest['Foot.'+side].translation,old_rest['Shin.'+side].translation,old_rest['Thigh.'+side].translation]
        centre=centres[0]
        for a,b in zip(centres,centres[1:]):
            if a.z<=p.z<=b.z:centre=a.lerp(b,(p.z-a.z)/(b.z-a.z));break
        radial=.80 if p.z<.23 else .84 if p.z<.48 else .88
        q.x=warp(centre).x+(p.x-centre.x)*radial
        q.y=warp(centre).y+(p.y-centre.y)*(.85 if p.z<.23 else .86)
        # Lower the boot collar gently, preserving the knee loop at z~.405.
        q.z-=.020*math.exp(-((p.z-.32)/.055)**2)
    if v.index in parts.coat:
        q.x*=.95;q.y*=.86
        q.z+=.025*(1-smooth(.06,.30,abs(p.x)))*(1-smooth(.50,.72,p.z))
    # Keep the closed right-hand grip rigid relative to its relocated socket.
    w=weights[v.index].get('Hand.R',0)
    if w>.25:q=q.lerp(hand_map@p,smooth(.25,.75,w))
    v.co=q
obj.data.update()
sword.matrix_world=new_rest['WeaponSocket.R']@old_rest['WeaponSocket.R'].inverted()@old_sword
bpy.context.view_layer.update()

for action in list(bpy.data.actions):bpy.data.actions.remove(action)
def key_pose(frame):
    for p in rig.pose.bones:
        p.rotation_mode='QUATERNION'
        p.keyframe_insert(data_path='rotation_quaternion',frame=frame,group=p.name)
        p.keyframe_insert(data_path='location',frame=frame,group=p.name)

for name,frames in unchanged.items():
    action=bpy.data.actions.new(name);action.use_fake_user=True;rig.animation_data_create();rig.animation_data.action=action
    for frame,operators in enumerate(frames,1):
        scene.frame_set(frame)
        for p in rig.pose.bones:
            matrix=operators[p.name]@new_rest[p.name]
            # Preserve new rest offsets through the parent chain. Copying old
            # world translations would detach joints after changing proportions.
            if p.parent and p.name!='Hips':
                matrix.translation=p.parent.matrix@new_rest[p.parent.name].inverted()@new_rest[p.name].translation
            p.matrix=matrix;bpy.context.view_layer.update()
        key_pose(frame)
rig.animation_data.action=bpy.data.actions['idle'];scene.frame_set(1);bpy.context.view_layer.update()
neutral={p.name:(p.rotation_quaternion.copy(),p.location.copy()) for p in rig.pose.bones}

# Reuse only explicit rig helper functions, without executing the old build job.
helper=ROOT/'tools/blender/build_swordsman_combat.py'
tree=ast.parse(helper.read_text(encoding='utf-8'))
selected={'reset','local_world_rotation','shift_hips','orient','limb','feet','arm','free_arm','coat','ease','interpolate','path'}
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in selected],type_ignores=[]),str(helper),'exec'))
ankles={s:rig.data.bones['Foot.'+s].head_local.copy() for s in ('L','R')}
rest_q={b.name:b.matrix_local.to_quaternion() for b in rig.data.bones}
ik_errors=[];ik_clamps={}

def params(grip,blade,yaw=0,lean=0,crouch=.03,hip_y=0,left_y=0,right_y=0):
    return dict(grip=grip,blade=blade,yaw=yaw,lean=lean,crouch=crouch,hip_y=hip_y,left_y=left_y,right_y=right_y)
IDLE=params((-.36,-.19,.91),(-.24,-.40,-.88))
WIND1=params((-.40,-.11,1.42),(-.65,.22,.73),-38,-3,.055,.01,0,.03)
HIT1=params((.10,-.39,1.02),(.42,-.58,-.69),38,14,.085,-.06,-.17,.03)
LINK12=params((.20,-.27,1.04),(.86,-.18,-.47),45,12,.08,-.055,-.16,.03)
MID2=params((-.11,-.45,1.13),(-.93,-.34,.08),-10,13,.085,-.06,-.18,-.02)
LINK23=params((-.29,-.12,1.43),(-.30,.32,.90),-38,-6,.075,-.03,-.15,.03)
WIND3=params((-.13,-.05,1.58),(-.10,.45,.89),-42,-10,.10,.02,-.10,.07)
HIT3=params((.10,-.43,.96),(.12,-.48,-.87),43,27,.14,-.085,-.24,.04)
PREP=params((-.36,-.10,.94),(-.15,-.55,-.82),-12,23,.12,-.035,-.10,.10)
BURST=params((-.35,.00,.94),(-.15,-.55,-.82),-12,39,.13,-.07,-.23,.24)
BRAKE=params((-.37,-.12,.95),(-.20,-.55,-.81),-7,24,.075,-.025,-.23,.09)

def action_pose(p,flutter=0):
    shift_hips(y=p['hip_y'],z=-p['crouch'])
    local_world_rotation('Hips',x=p['lean']*.20,z=p['yaw']*.25)
    local_world_rotation('Spine',x=p['lean']*.45,z=p['yaw']*.35)
    local_world_rotation('Chest',x=p['lean']*.35,z=p['yaw']*.40)
    local_world_rotation('Head',x=-p['lean']*.4,z=-p['yaw']*.55)
    bpy.context.view_layer.update();arm('R',p['grip'],p['blade']);free_arm(abs(p['yaw']))
    l,r=ankles['L'].copy(),ankles['R'].copy();l.y+=p['left_y'];r.y+=p['right_y'];feet(l,r)
    coat(-12-p['crouch']*40-flutter,10+flutter,-p['yaw']*.08)

def scalar(keys,t):
    for (a,x),(b,y) in zip(keys,keys[1:]):
        if a<=t<=b:return x+(y-x)*ease((t-a)/(b-a))
    return keys[-1][1]

foot_vertices={s:[i for i,w in weights.items() if w.get('Foot.'+s,0)+w.get('Toe.'+s,0)>.70] for s in ('L','R')}
def run(t):
    phase=2*math.pi*t;half=(2*t)%1
    drop=scalar([(0,.055),(.23,.075),(.60,.0),(.80,-.025),(1,.055)],half)
    shift_hips(y=-.035,z=-drop)
    local_world_rotation('Hips',x=5,z=4*math.sin(phase))
    local_world_rotation('Spine',x=11,z=-4*math.sin(phase))
    local_world_rotation('Chest',x=7,z=-4*math.sin(phase))
    local_world_rotation('Head',x=-12,z=2*math.sin(phase))
    bpy.context.view_layer.update()
    arm('R',(-.35,-.045+.035*math.cos(phase),.95+.025*math.sin(phase)),(-.12,-.58,-.81))
    local_world_rotation('UpperArm.L',x=-12+30*math.cos(phase),y=12)
    local_world_rotation('Forearm.L',x=-72-8*math.cos(phase))
    targets={};rolls={}
    for side,offset in [('L',0),('R',.5)]:
        c=(t+offset)%1;sign=1 if side=='L' else -1
        target=ankles[side].copy();target.x=sign*.105
        centre=rig.data.bones['Thigh.'+side].head_local.y-.035
        if c<.30:
            u=c/.30;target.y=centre-.27+.54*u
            roll=scalar([(0,-7),(.22,0),(.55,0),(1,20)],u)
            target.z+=.055*ease((u-.55)/.45)
        else:
            u=(c-.30)/.70
            target.y=centre+scalar([(0,.27),(.22,.34),(.62,-.01),(1,-.27)],u)
            target.z+=scalar([(0,.055),(.25,.37),(.52,.31),(.80,.13),(1,0)],u)
            roll=scalar([(0,20),(.25,43),(.60,12),(1,-7)],u)
        targets[side]=target;rolls[side]=roll
        end=limb('Thigh.'+side,'Shin.'+side,target,(sign*.025,-1,.05))
        orient('Foot.'+side,end,q=Quaternion((1,0,0),math.radians(roll))@rest_q['Foot.'+side])
        swing=math.sin(phase+offset*2*math.pi)
        local_world_rotation('Coat_Front.'+side,x=-20-8*max(0,-swing),y=sign*2)
        local_world_rotation('Coat_Back.'+side,x=22+10*max(0,swing),y=sign*2)
        local_world_rotation('Coat_Back.'+side+'_Tip',x=8+5*swing)
    # Keep the boot sole above the ground during heel strike/toe off.
    evaluated=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=evaluated.to_mesh()
    low={s:min(mesh.vertices[i].co.z for i in foot_vertices[s]) for s in ('L','R')};evaluated.to_mesh_clear()
    for side in ('L','R'):
        if low[side]<.001:
            target=targets[side]+Vector((0,0,.001-low[side]))
            end=limb('Thigh.'+side,'Shin.'+side,target,((.025 if side=='L' else -.025),-1,.05))
            orient('Foot.'+side,end,q=Quaternion((1,0,0),math.radians(rolls[side]))@rest_q['Foot.'+side])

functions={
 'run':(19,run),
 'attack_1':(13,lambda t:action_pose(path([(0,IDLE),(.25,WIND1),(.55,HIT1),(1,LINK12)],t),5*math.sin(math.pi*t))),
 'attack_2':(13,lambda t:action_pose(path([(0,LINK12),(.52,MID2),(1,LINK23)],t),6*math.sin(math.pi*t))),
 'attack_3':(21,lambda t:action_pose(path([(0,LINK23),(.30,WIND3),(.50,HIT3),(.60,HIT3),(1,IDLE)],t),9*math.sin(math.pi*t))),
 'dodge':(11,lambda t:action_pose(path([(0,IDLE),(.18,PREP),(.40,BURST),(.70,BRAKE),(1,IDLE)],t),10*math.sin(math.pi*t)))
}
for name,(frames,fn) in functions.items():
    action=bpy.data.actions.new(name);action.use_fake_user=True;rig.animation_data.action=action
    for frame in range(1,frames+1):
        scene.frame_set(frame);reset();fn((frame-1)/(frames-1));bpy.context.view_layer.update()
        if (name in ('attack_1','dodge') and frame==1) or (name in ('attack_3','dodge') and frame==frames):
            for p in rig.pose.bones:p.rotation_quaternion=neutral[p.name][0];p.location=neutral[p.name][1]
        key_pose(frame)
    print('REFINED',name,flush=True)
for action in bpy.data.actions:
    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                for curve in bag.fcurves:
                    for k in curve.keyframe_points:k.interpolation='LINEAR'
for filename in ('spec.json','combat_events.json','swordsman_basecolor_2048.png','swordsman_normal_2048.png','swordsman_roughness_2048.png'):
    shutil.copyfile(SOURCE.parent/filename,OUT/filename)
spec=json.loads((OUT/'spec.json').read_text());spec['asset_id']='swordsman-combat-v007'
(OUT/'spec.json').write_text(json.dumps(spec,indent=2),encoding='utf-8')
events=json.loads((OUT/'combat_events.json').read_text());events['run_reference_speed_m_s']=3.0
events['run_gait']=dict(period=.6,stance_fraction=.30,stance_travel=.54,plant_core=[.08,.17],track_width=.21)
(OUT/'combat_events.json').write_text(json.dumps(events,indent=2),encoding='utf-8')
rig.animation_data.action=bpy.data.actions['idle'];scene.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'swordsman_combat_v007.blend'))
report=dict(source=str(SOURCE.relative_to(ROOT)),source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
            topology_preserved=True,triangles=sum(len(p.vertices)-2 for p in obj.data.polygons)+sum(len(p.vertices)-2 for p in sword.data.polygons),
            silhouette_changes=dict(shoulder_width_factor=.91,hip_width_factor=.88,leg_radius_factor=[.80,.88],boot_depth_factor=.85,
                                    lower_coat_depth_factor=.86,torso_depth_factor=.88),
            motion_changes=['Narrow 21cm foot track','Heel pickup and toe-off','Forward body lean','Downward sword carry',
                            'Stronger opposing torso rotations in combo','Forward-leaning dash, trailing leg and braking'],
            helper_sha256=hashlib.sha256(helper.read_bytes()).hexdigest(),ik_reach_clamps_m=ik_clamps,
            scope='Reference-directed local sculpt and FK animation; no new Hunyuan generation')
(OUT/'refinement_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('REFINEMENT_READY',json.dumps(report),flush=True)
