"""Re-import both deliverables in fresh scenes and check skin/action contracts."""
import bpy,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'art/characters/swordsman/hunyuan_animation_v004'
results=[]
for extension in ('glb','fbx'):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    before=set(bpy.data.objects)
    path=OUT/f'SK_Swordsman_Anim_v004.{extension}'
    if extension=='glb':bpy.ops.import_scene.gltf(filepath=str(path))
    else:bpy.ops.import_scene.fbx(filepath=str(path),use_anim=True)
    imported=[o for o in bpy.data.objects if o not in before]
    # glTF importer creates an unskinned Icosphere custom-shape helper for bones.
    meshes=[o for o in imported if o.type=='MESH' and any(m.type=='ARMATURE' for m in o.modifiers)]
    rigs=[o for o in imported if o.type=='ARMATURE']
    print('IMPORTED',extension,[(o.name,o.type) for o in imported],flush=True)
    assert len(meshes)==1 and len(rigs)==1
    obj=meshes[0];rig=rigs[0]
    tris=sum(len(p.vertices)-2 for p in obj.data.polygons)
    assert 6000<=tris<=12000
    assert len(rig.data.bones)==31
    assert any(m.type=='ARMATURE' and m.object==rig for m in obj.modifiers)
    for v in obj.data.vertices:
        values=[g.weight for g in v.groups if g.weight>1e-7]
        assert 1<=len(values)<=4
        assert abs(sum(values)-1)<2e-5
    assert len(bpy.data.actions)>=1 and rig.animation_data and rig.animation_data.action
    frames=rig.animation_data.action.frame_range
    assert frames[1]-frames[0]>60
    samples=[]
    # glTF is imported at the new scene's FPS, FBX carries its own frame rate.
    for frame in (int(frames[0]),int(frames[0]+.75*(frames[1]-frames[0]))):
        bpy.context.scene.frame_set(frame);bpy.context.view_layer.update()
        evaluated=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=evaluated.to_mesh()
        samples.append([obj.matrix_world@v.co for v in mesh.vertices]);evaluated.to_mesh_clear()
    max_motion=max((a-b).length for a,b in zip(*samples))
    print('MOTION',extension,list(frames),max_motion,flush=True)
    assert max_motion>.1,'Animation did not deform the exported mesh'
    results.append(dict(file=path.name,triangles=tris,bones=len(rig.data.bones),
                        normalized_weights=True,max_influences=4,action_count=len(bpy.data.actions),
                        frames=list(frames),max_vertex_motion_metres=max_motion,
                        sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
(OUT/'export_validation.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
print('EXPORT_VALIDATION',json.dumps(results),flush=True)
