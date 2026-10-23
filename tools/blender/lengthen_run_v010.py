"""Increase real stride distance and lower cadence, preserving the v009 free arm."""
import bpy,math,json,hashlib,shutil,ast
from pathlib import Path
from mathutils import Vector,Quaternion,Matrix
ROOT=Path(__file__).resolve().parents[2];SOURCE=Path(bpy.data.filepath)
OUT=ROOT/'art/characters/swordsman/hunyuan_combat_v010';OUT.mkdir(parents=True,exist_ok=True)
scene=bpy.context.scene;rig=bpy.data.objects['Rig_Swordsman'];obj=bpy.data.objects['SK_Swordsman_Animation']
old=bpy.data.actions['run'];rig.animation_data.action=old
frames=23;period=(frames-1)/30;stance=.26;reference=3.9;travel=period*stance*reference
poses=[]
for i in range(frames):
    value=1+18*i/(frames-1);scene.frame_set(int(value),subframe=value-int(value));bpy.context.view_layer.update()
    poses.append({p.name:(p.location.copy(),p.rotation_quaternion.copy()) for p in rig.pose.bones})
rig.animation_data.action=None;bpy.data.actions.remove(old)
action=bpy.data.actions.new('run');action.use_fake_user=True;rig.animation_data.action=action
rest_q={b.name:b.matrix_local.to_quaternion() for b in rig.data.bones};ik_errors=[];ik_clamps={}
helper=ROOT/'tools/blender/build_swordsman_combat.py';tree=ast.parse(helper.read_text(encoding='utf-8'))
names={'local_world_rotation','shift_hips','orient','limb'}
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names],type_ignores=[]),str(helper),'exec'))
ankles={s:rig.data.bones['Foot.'+s].head_local.copy() for s in ('L','R')}
weights={v.index:{obj.vertex_groups[g.group].name:g.weight for g in v.groups} for v in obj.data.vertices}
foot_vertices={s:[i for i,w in weights.items() if w.get('Foot.'+s,0)+w.get('Toe.'+s,0)>.70] for s in ('L','R')}
def scalar(keys,t):
    for (a,x),(b,y) in zip(keys,keys[1:]):
        if a<=t<=b:
            u=(t-a)/(b-a);u=u*u*(3-2*u);return x+(y-x)*u
    return keys[-1][1]
for i,pose in enumerate(poses):
    scene.frame_set(i+1);t=i/(frames-1);phase=2*math.pi*t
    for p in rig.pose.bones:p.location=pose[p.name][0];p.rotation_quaternion=pose[p.name][1]
    half=(2*t)%1
    drop=scalar([(0,.095),(.20,.105),(.48,.045),(.62,-.005),(.82,.025),(1,.095)],half)
    shift_hips(y=-.035,z=-drop);bpy.context.view_layer.update()
    targets={};rolls={}
    for side,offset in [('L',0),('R',.5)]:
        c=(t+offset)%1;sign=1 if side=='L' else -1
        target=ankles[side].copy();target.x=sign*.105
        centre=rig.data.bones['Thigh.'+side].head_local.y-.035
        front=.35;back=travel-front
        if c<stance:
            u=c/stance;target.y=centre-front+travel*u
            roll=scalar([(0,-10),(.22,0),(.55,0),(1,25)],u)
            target.z+=.11*max(0,(u-.55)/.45)**2
        else:
            u=(c-stance)/(1-stance)
            target.y=centre+scalar([(0,back),(.16,.44),(.43,.03),(.64,-.43),(.82,-.41),(1,-front)],u)
            target.z+=scalar([(0,.11),(.17,.39),(.43,.35),(.64,.25),(.82,.10),(1,0)],u)
            roll=scalar([(0,25),(.22,40),(.60,5),(.84,-12),(1,-10)],u)
        targets[side]=target;rolls[side]=roll
        swing=math.sin(phase+offset*2*math.pi)
        local_world_rotation('Coat_Front.'+side,x=-38-14*max(0,-swing),y=-sign*10)
        local_world_rotation('Coat_Back.'+side,x=35+14*max(0,swing),y=-sign*8)
        name='Coat_Front.'+side
        rig.pose.bones[name].location=rest_q[name].inverted()@Vector((sign*.025,-.030,.008))
    # Fit the pelvis to actual limb reach rather than silently clamping a long step.
    extra=0
    for side in ('L','R'):
        head=rig.pose.bones['Thigh.'+side].head;target=targets[side]
        length=rig.data.bones['Thigh.'+side].length+rig.data.bones['Shin.'+side].length-.001
        planar=(head.x-target.x)**2+(head.y-target.y)**2
        allowed=math.sqrt(max(.001,length*length-planar))
        extra=max(extra,head.z-target.z-allowed)
    if extra>0:shift_hips(y=-.035,z=-drop-extra);bpy.context.view_layer.update()
    for side in ('L','R'):
        end=limb('Thigh.'+side,'Shin.'+side,targets[side],((.025 if side=='L' else -.025),-1,.05))
        orient('Foot.'+side,end,q=Quaternion((1,0,0),math.radians(rolls[side]))@rest_q['Foot.'+side])
    evaluated=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=evaluated.to_mesh()
    low={s:min(mesh.vertices[j].co.z for j in foot_vertices[s]) for s in ('L','R')};evaluated.to_mesh_clear()
    for side in ('L','R'):
        if low[side]<.001:
            target=targets[side]+Vector((0,0,.001-low[side]))
            end=limb('Thigh.'+side,'Shin.'+side,target,((.025 if side=='L' else -.025),-1,.05))
            orient('Foot.'+side,end,q=Quaternion((1,0,0),math.radians(rolls[side]))@rest_q['Foot.'+side])
    for p in rig.pose.bones:
        p.keyframe_insert(data_path='location',frame=i+1,group=p.name);p.keyframe_insert(data_path='rotation_quaternion',frame=i+1,group=p.name)
for layer in action.layers:
    for strip in layer.strips:
        for bag in strip.channelbags:
            for curve in bag.fcurves:
                for point in curve.keyframe_points:point.interpolation='LINEAR'
for name in ('spec.json','combat_events.json','swordsman_basecolor_2048.png','swordsman_normal_2048.png','swordsman_roughness_2048.png'):shutil.copyfile(SOURCE.parent/name,OUT/name)
spec=json.loads((OUT/'spec.json').read_text());spec['asset_id']='swordsman-combat-v010'
for clip in spec['animations']:
    if clip['name']=='run':clip['duration_s']=period
(OUT/'spec.json').write_text(json.dumps(spec,indent=2),encoding='utf-8')
events=json.loads((OUT/'combat_events.json').read_text());events['run_reference_speed_m_s']=reference
events['run_gait']=dict(period=period,stance_fraction=stance,stance_travel=travel,plant_core=[.045,.14],track_width=.21)
(OUT/'combat_events.json').write_text(json.dumps(events,indent=2),encoding='utf-8')
report=dict(source=str(SOURCE.relative_to(ROOT)),source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),method='Longer running leg trajectory and lower cadence, with code-driven speed matching',
 reference_speed_m_s=reference,default_speed_m_s=4.3,cycle_s=period,stride_per_cycle_m=reference*period,step_length_m=reference*period/2,default_steps_per_minute=2*4.3/(reference*period)*60,
 previous=dict(default_speed_m_s=3.6,stride_per_cycle_m=1.8,step_length_m=.9,steps_per_minute=240),ik_reach_clamps_m=ik_clamps,
 unchanged='v009 free-arm pose, weapon arm, body mesh, rest skeleton, maps, other eight clips and all attack/dash/lunge timings')
(OUT/'build_receipt.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
rig.animation_data.action=bpy.data.actions['idle'];scene.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'swordsman_combat_v010.blend'))
print('LONGER_RUN_AUTHORED',json.dumps(report),flush=True)
