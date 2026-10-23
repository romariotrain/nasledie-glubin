import bpy,json,math,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'art/characters/swordsman/hunyuan_textured_v001'
results=[]
def sample(obj,frame):
    bpy.context.scene.frame_set(int(frame),subframe=frame-int(frame));bpy.context.view_layer.update()
    evaluated=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=evaluated.to_mesh()
    points=[obj.matrix_world@v.co for v in mesh.vertices];evaluated.to_mesh_clear();return points
for extension in ('glb','fbx'):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    before=set(bpy.data.objects)
    path=OUT/f'SK_Swordsman_Textured_v001.{extension}'
    if extension=='glb':bpy.ops.import_scene.gltf(filepath=str(path))
    else:bpy.ops.import_scene.fbx(filepath=str(path),use_anim=True)
    objects=[o for o in bpy.data.objects if o not in before]
    rig=next(o for o in objects if o.type=='ARMATURE')
    obj=next(o for o in objects if o.type=='MESH' and any(m.type=='ARMATURE' for m in o.modifiers))
    sword=next(o for o in objects if o.type=='MESH' and 'Longsword' in o.name)
    assert len(rig.data.bones)==31 and len(obj.data.uv_layers)==1
    triangles=sum(len(p.vertices)-2 for p in obj.data.polygons)
    sword_triangles=sum(len(p.vertices)-2 for p in sword.data.polygons)
    assert triangles==11898 and triangles+sword_triangles<=12000
    for vertex in obj.data.vertices:
        values=[g.weight for g in vertex.groups if g.weight>1e-7]
        assert 1<=len(values)<=4 and abs(sum(values)-1)<2e-5
    material=obj.data.materials[0]
    images=[n.image for n in material.node_tree.nodes if n.type=='TEX_IMAGE' and n.image]
    assert len(images)>=3 and all(im.size[0]==2048 for im in images)
    clip_reports=[]
    for name in ('Idle','Walk_InPlace','Slash_01'):
        action=next(a for a in bpy.data.actions if name in a.name)
        rig.animation_data.action=action
        start,end=action.frame_range
        rest=sample(obj,start);sword_rest=sword.matrix_world.copy()
        motions=[];sword_motions=[]
        for fraction in (.25,.5,.75):
            points=sample(obj,start+(end-start)*fraction)
            motions.append(max((a-b).length for a,b in zip(rest,points)))
            sword_motions.append((sword.matrix_world.translation-sword_rest.translation).length)
        assert max(motions)>.002
        if name!='Idle':assert max(sword_motions)>.01
        loop_error=None
        if name in ('Idle','Walk_InPlace'):
            last=sample(obj,end);loop_error=max((a-b).length for a,b in zip(rest,last))
            assert loop_error<.002,(extension,name,loop_error)
        clip_reports.append(dict(name=name,range=list(action.frame_range),max_sampled_vertex_motion=max(motions),
            max_sampled_weapon_grip_motion=max(sword_motions),loop_position_error=loop_error))
    results.append(dict(file=path.name,character_triangles=triangles,sword_triangles=sword_triangles,
        bones=31,uv_layers=1,texture_images=len(images),clips=clip_reports,
        sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
(OUT/'export_validation.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
print('VALIDATED_TEXTURED_EXPORTS',json.dumps(results),flush=True)
