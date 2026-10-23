import bpy,importlib.util,json
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('audit',ROOT/'tools/blender/audit_swordsman_collisions.py');audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
obj=audit.obj;rig=audit.rig;found=set()
for name,end in [('Idle',61),('Walk_InPlace',31),('Slash_01',37),('Start_Walk',10),('Stop_Walk',10)]:
    rig.animation_data.action=bpy.data.actions[name]
    for frame in range(1,end+1):
        bpy.context.scene.frame_set(frame)
        for record in audit.evaluate(return_points=True)['_records']:found.add(tuple(record['body_face']))
rig.animation_data.action=bpy.data.actions['Idle'];bpy.context.scene.frame_set(1);bpy.context.view_layer.update()
evaluated=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=evaluated.to_mesh();coords=[v.co.copy() for v in mesh.vertices];evaluated.to_mesh_clear()
coat=BVHTree.FromPolygons(coords,audit.coat_faces,all_triangles=True)
records=[]
for f in found:
    p=sum((coords[i] for i in f),Vector())/3
    directions=[Vector((6,-8,9)).normalized(),Vector((-6,8,9)).normalized(),Vector((0,-1,.1)).normalized()]
    occluded=[]
    for direction in directions:
        hit,_,_,_=coat.ray_cast(p+direction*.0002,direction,2);occluded.append(hit is not None)
    records.append(dict(face=f,center=tuple(p),occluded=occluded))
print('REMAINING_FACES',json.dumps(records),flush=True)
