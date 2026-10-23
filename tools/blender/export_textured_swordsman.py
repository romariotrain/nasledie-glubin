import bpy,bmesh,tempfile,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'art/characters/swordsman/hunyuan_textured_v001'
workspace_temp=ROOT/'work/hunyuan2mini/export-temp';workspace_temp.mkdir(exist_ok=True)
tempfile.tempdir=str(workspace_temp)
obj=bpy.data.objects['SK_Swordsman_Animation'];rig=bpy.data.objects['Rig_Swordsman'];sword=bpy.data.objects['SM_Longsword']
rig.animation_data.action=bpy.data.actions['Idle'];bpy.context.scene.frame_set(1)
original=obj.data;copy=original.copy();bm=bmesh.new();bm.from_mesh(copy)
bmesh.ops.triangulate(bm,faces=list(bm.faces),quad_method='BEAUTY',ngon_method='BEAUTY')
assert all(e.is_manifold for e in bm.edges)
bm.to_mesh(copy);bm.free();obj.data=copy
bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);rig.select_set(True);sword.select_set(True)
bpy.context.view_layer.objects.active=rig
bpy.ops.export_scene.gltf(filepath=str(OUT/'SK_Swordsman_Textured_v001.glb'),export_format='GLB',
    use_selection=True,export_animations=True,export_animation_mode='ACTIONS',export_nla_strips=True,
    export_influence_nb=4,export_skins=True,export_rest_position_armature=True,
    export_cameras=False,export_lights=False,export_force_sampling=True,export_materials='EXPORT')
bpy.ops.export_scene.fbx(filepath=str(OUT/'SK_Swordsman_Textured_v001.fbx'),use_selection=True,
    object_types={'ARMATURE','MESH'},add_leaf_bones=False,bake_anim=True,
    bake_anim_use_all_actions=True,bake_anim_use_nla_strips=False,path_mode='COPY',embed_textures=True,
    axis_forward='-Z',axis_up='Y',use_armature_deform_only=False)
obj.data=original;bpy.data.meshes.remove(copy)
clips=[dict(name=name,frames=frames,seconds=(frames-1)/30,loop=loop)
       for name,frames,loop in [('Idle',61,True),('Walk_InPlace',31,True),('Slash_01',37,False)]]
report=dict(character_triangles=sum(len(p.vertices)-2 for p in obj.data.polygons),
    sword_triangles=sum(len(p.vertices)-2 for p in sword.data.polygons),bones=len(rig.data.bones),
    uv_layers=len(obj.data.uv_layers),texture_size=2048,clips=clips,
    material_method='Front/rear concept projection to UV; CPU high-to-low tangent normal bake; authored roughness.',
    limitations='Prototype clips. FK baked analytic two-bone foot placement; no runtime IK or collision solver; rear texture is inferred; no facial/finger animation.')
(OUT/'material_animation_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('TEXTURED_ANIMATION_REPORT',json.dumps(report),flush=True)
