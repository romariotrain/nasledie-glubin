import bpy,json
from pathlib import Path
from collections import defaultdict
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[2]
obj=bpy.data.objects['SK_Swordsman_Animation'];rig=bpy.data.objects['Rig_Swordsman']
obj.data.calc_loop_triangles();triangles=[tuple(t.vertices) for t in obj.data.loop_triangles]
adjacency=defaultdict(list)
for edge in obj.data.edges:
    a,b=edge.vertices;adjacency[a].append(b);adjacency[b].append(a)
remaining={v.index for v in obj.data.vertices if v.co.z<.81};coat=set();legs=set()
while remaining:
    q=[next(iter(remaining))];component=set()
    while q:
        i=q.pop()
        if i not in remaining:continue
        remaining.remove(i);component.add(i);q.extend(adjacency[i])
    points=[obj.data.vertices[i].co for i in component]
    if min(p.z for p in points)>.27 and max(p.x for p in points)-min(p.x for p in points)>.36:coat.update(component)
    if min(p.z for p in points)<.20:legs.update(component)
coat_faces=[f for f in triangles if all(i in coat for i in f)]
body_faces=[f for f in triangles if all(i in legs for i in f)]
def evaluate(clearance=-.001,return_points=False):
    bpy.context.view_layer.update();evaluated=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=evaluated.to_mesh()
    coords=[v.co.copy() for v in mesh.vertices];evaluated.to_mesh_clear()
    bvh=BVHTree.FromPolygons(coords,body_faces,all_triangles=True)
    samples=[((i,),coords[i]) for i in coat if coords[i].z<.76]
    samples.extend((f,sum((coords[i] for i in f),Vector())/3) for f in coat_faces if max(coords[i].z for i in f)<.76)
    penetrations=[];contacts=[];records=[]
    for indices,p in samples:
        nearest,normal,index,distance=bvh.find_nearest(p)
        if nearest is None or distance>.15:continue
        signed=(p-nearest).dot(normal)
        if signed<clearance:
            # Horizontal parity test rejects sign ambiguities near open waist.
            cursor=p.copy();hits=0
            for _ in range(12):
                hit,_,_,_=bvh.ray_cast(cursor,Vector((1,0,0)),2)
                if hit is None:break
                hits+=1;cursor=hit+Vector((.0001,0,0))
            if hits%2 or (signed>=0 and clearance>0):
                penetrations.append(max(0,-signed));contacts.append(p.copy())
                records.append(dict(indices=indices,point=p.copy(),nearest=nearest.copy(),normal=normal.copy(),signed=signed,body_face=body_faces[index]))
    result=dict(penetrating_samples=len(penetrations),deepest=max(penetrations,default=0))
    if return_points:result['_points']=contacts;result['_records']=records
    return result
if __name__=='__main__':
    report={}
    for action in ('Idle','Walk_InPlace','Slash_01'):
        rig.animation_data.action=bpy.data.actions[action]
        report[action]=[]
        for frame in (1,8,16,24,31):
            bpy.context.scene.frame_set(frame);report[action].append(dict(frame=frame,**evaluate()))
    print('COLLISION_AUDIT',json.dumps(dict(coat_vertices=len(coat),coat_faces=len(coat_faces),body_faces=len(body_faces),clips=report)),flush=True)
