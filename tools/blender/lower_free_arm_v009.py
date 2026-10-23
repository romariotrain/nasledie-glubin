"""Revise only the free left arm in v007 run; preserve shape and other clips."""
import bpy,math,json,hashlib,shutil
from pathlib import Path
from mathutils import Quaternion
ROOT=Path(__file__).resolve().parents[2];SOURCE=Path(bpy.data.filepath)
OUT=ROOT/'art/characters/swordsman/hunyuan_combat_v009';OUT.mkdir(parents=True,exist_ok=True)
rig=bpy.data.objects['Rig_Swordsman'];scene=bpy.context.scene;action=bpy.data.actions['run']
rig.animation_data.action=action
old=[]
for frame in range(1,20):
    scene.frame_set(frame);bpy.context.view_layer.update();old.append(list(rig.pose.bones['Hand.L'].head))
for layer in action.layers:
    for strip in layer.strips:
        for bag in strip.channelbags:
            for curve in list(bag.fcurves):
                if any(f'pose.bones["{name}"].rotation_quaternion'==curve.data_path for name in ('UpperArm.L','Forearm.L')):bag.fcurves.remove(curve)
def rotate(name,x,y):
    rest=rig.data.bones[name].matrix_local.to_quaternion()
    q=Quaternion((1,0,0),math.radians(x))@Quaternion((0,1,0),math.radians(y))
    bone=rig.pose.bones[name];bone.rotation_mode='QUATERNION';bone.rotation_quaternion=rest.inverted()@q@rest
    bone.keyframe_insert(data_path='rotation_quaternion',frame=scene.frame_current,group=name)
new=[]
for frame in range(1,20):
    scene.frame_set(frame);phase=2*math.pi*(frame-1)/18
    rotate('UpperArm.L',-4+7*math.cos(phase),3)
    rotate('Forearm.L',-25-3*math.cos(phase),0)
    bpy.context.view_layer.update();new.append(list(rig.pose.bones['Hand.L'].head))
for layer in action.layers:
    for strip in layer.strips:
        for bag in strip.channelbags:
            for curve in bag.fcurves:
                if 'UpperArm.L' in curve.data_path or 'Forearm.L' in curve.data_path:
                    for point in curve.keyframe_points:point.interpolation='LINEAR'
for name in ('spec.json','combat_events.json','swordsman_basecolor_2048.png','swordsman_normal_2048.png','swordsman_roughness_2048.png'):
    shutil.copyfile(SOURCE.parent/name,OUT/name)
spec=json.loads((OUT/'spec.json').read_text());spec['asset_id']='swordsman-combat-v009'
(OUT/'spec.json').write_text(json.dumps(spec,indent=2),encoding='utf-8')
report=dict(source=str(SOURCE.relative_to(ROOT)),source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
 method='Lowered free-arm FK pose with periodic cosine swing; only UpperArm.L and Forearm.L quaternion tracks in run changed',
 upper_arm_swing_degrees=dict(previous=60,current=14),elbow_bend_degrees=dict(previous=[64,80],current=[22,28]),
 original_left_hand_positions=old,revised_left_hand_positions=new,
 unchanged='Body mesh, rest rig, UV, maps, weights, weapon arm, leg gait, clip duration, all other clips and gameplay timings')
(OUT/'build_receipt.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
rig.animation_data.action=bpy.data.actions['idle'];scene.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'swordsman_combat_v009.blend'))
print('FREE_ARM_REVISED',flush=True)
