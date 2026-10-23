import bpy,bmesh,numpy as np
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'art/characters/swordsman/hunyuan_textured_v001'
OUT.mkdir(parents=True,exist_ok=True)
obj=bpy.data.objects['SK_Swordsman_Animation'];rig=bpy.data.objects['Rig_Swordsman']
bpy.context.scene.frame_set(1)
rig.animation_data_clear()
for pb in rig.pose.bones:
    pb.rotation_quaternion=(1,0,0,0);pb.location=(0,0,0)
bpy.context.view_layer.update()
bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj
bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.smart_project(angle_limit=1.151917,island_margin=.002,area_weight=.3,correct_aspect=True,scale_to_bounds=True)
bpy.ops.object.mode_set(mode='OBJECT')
obj.data.uv_layers.active.name='UV_Atlas'
obj.data.calc_loop_triangles()
positions=np.array([v.co[:] for v in obj.data.vertices],dtype=np.float32)
normals=np.array([v.normal[:] for v in obj.data.vertices],dtype=np.float32)
triangles=np.array([t.vertices[:] for t in obj.data.loop_triangles],dtype=np.int32)
uvs=np.array([[obj.data.uv_layers.active.data[i].uv[:] for i in t.loops] for t in obj.data.loop_triangles],dtype=np.float32)
np.savez(ROOT/'work/hunyuan2mini/texture_mesh.npz',positions=positions,normals=normals,triangles=triangles,uvs=uvs)
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'work/hunyuan2mini/swordsman_uv_work.blend'))
print('UV_READY',len(triangles),len(obj.data.uv_layers),flush=True)
