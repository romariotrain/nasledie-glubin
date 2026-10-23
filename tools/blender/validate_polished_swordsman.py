import bpy,json,hashlib,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'art/characters/swordsman/hunyuan_polished_v005'
results=[]
def frame(value):bpy.context.scene.frame_set(math.floor(value),subframe=value-math.floor(value));bpy.context.view_layer.update()
def points(obj):
    evaluated=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=evaluated.to_mesh()
    result=[obj.matrix_world@v.co for v in mesh.vertices];evaluated.to_mesh_clear();return result
for extension in ('glb','fbx'):
    bpy.ops.wm.read_factory_settings(use_empty=True);before=set(bpy.data.objects)
    path=OUT/f'SK_Swordsman_Polished_v005.{extension}'
    if extension=='glb':bpy.ops.import_scene.gltf(filepath=str(path))
    else:bpy.ops.import_scene.fbx(filepath=str(path),use_anim=True)
    new=[o for o in bpy.data.objects if o not in before]
    rig=next(o for o in new if o.type=='ARMATURE')
    obj=next(o for o in new if o.type=='MESH' and any(m.type=='ARMATURE' for m in o.modifiers))
    sword=next(o for o in new if o.type=='MESH' and 'Longsword' in o.name)
    tris=sum(len(p.vertices)-2 for p in obj.data.polygons)
    sword_tris=sum(len(p.vertices)-2 for p in sword.data.polygons)
    assert 6000<tris+sword_tris<=12000 and len(rig.data.bones)==31 and len(obj.data.uv_layers)==1
    for vertex in obj.data.vertices:
        values=[g.weight for g in vertex.groups if g.weight>1e-7]
        assert 1<=len(values)<=4 and abs(sum(values)-1)<2e-5
    material=obj.data.materials[0]
    images=[n.image for n in material.node_tree.nodes if n.type=='TEX_IMAGE' and n.image]
    assert len(images)==3
    ends={};reports=[]
    for name in ('Idle','Walk_InPlace','Slash_01','Start_Walk','Stop_Walk','Game_Demo'):
        action=next(a for a in bpy.data.actions if name in a.name)
        rig.animation_data.action=action;start,end=action.frame_range
        frame(start);a=points(obj);weapon_start=sword.matrix_world.translation.copy()
        frame(start+(end-start)*.25);middle=points(obj);motion=max((p-q).length for p,q in zip(a,middle))
        frame(end);b=points(obj);ends[name]=(a,b)
        loop_error=max((p-q).length for p,q in zip(a,b))
        if name in ('Idle','Walk_InPlace','Game_Demo'):assert loop_error<.001
        assert motion>.0001
        reports.append(dict(name=name,frames=list(action.frame_range),motion_metres=motion,endpoint_error=loop_error))
    links=[('Idle',0,'Start_Walk',0),('Start_Walk',1,'Walk_InPlace',0),('Walk_InPlace',1,'Stop_Walk',0),
           ('Stop_Walk',1,'Idle',0),('Idle',0,'Slash_01',0),('Slash_01',1,'Idle',0)]
    transitions=[]
    for a,ai,b,bi in links:
        error=max((p-q).length for p,q in zip(ends[a][ai],ends[b][bi]));assert error<.001
        transitions.append(dict(source=a,target=b,max_position_gap_metres=error))
    results.append(dict(file=path.name,character_triangles=tris,sword_triangles=sword_tris,
        bones=31,images=3,clips=reports,transitions=transitions,
        sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
(OUT/'export_validation.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
print('POLISHED_VALIDATION',json.dumps(results),flush=True)
