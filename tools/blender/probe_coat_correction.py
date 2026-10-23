import bpy,importlib.util,math,json
from pathlib import Path
from mathutils import Quaternion
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('audit',ROOT/'tools/blender/audit_swordsman_collisions.py');audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
rig=bpy.data.objects['Rig_Swordsman'];rig.animation_data.action=bpy.data.actions['Walk_InPlace'];bpy.context.scene.frame_set(1);bpy.context.view_layer.update()
base={p.name:p.rotation_quaternion.copy() for p in rig.pose.bones}
rig.animation_data_clear()
print('BASE',audit.evaluate(),flush=True)
for name in ('Coat_Front.L','Coat_Front.R','Coat_Back.L','Coat_Back.R'):
    for angle in (-20,-10,10,20,30):
        for p in rig.pose.bones:p.rotation_quaternion=base[p.name]
        p=rig.pose.bones[name];rest=p.bone.matrix_local.to_quaternion()
        p.rotation_quaternion=(rest.inverted()@Quaternion((1,0,0),math.radians(angle))@rest)@p.rotation_quaternion
        bpy.context.view_layer.update();print('PROBE',name,angle,audit.evaluate(),flush=True)
best=None
for front in (0,10,20,30,40):
    for back in (0,10,20,30,40):
        for p in rig.pose.bones:p.rotation_quaternion=base[p.name]
        for name,angle in [('Coat_Front.L',front),('Coat_Back.L',back)]:
            p=rig.pose.bones[name];rest=p.bone.matrix_local.to_quaternion()
            p.rotation_quaternion=(rest.inverted()@Quaternion((1,0,0),math.radians(angle))@rest)@p.rotation_quaternion
        bpy.context.view_layer.update();result=audit.evaluate()
        rank=(result['penetrating_samples'],result['deepest'])
        if best is None or rank<best[0]:best=(rank,front,back)
print('BEST_COMBINED',best,flush=True)
