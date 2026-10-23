import bpy,bmesh,tempfile,json,hashlib,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=Path(bpy.data.filepath).parent
folder=ROOT/'work/hunyuan2mini/export-temp';folder.mkdir(exist_ok=True);tempfile.tempdir=str(folder)
obj=bpy.data.objects['SK_Swordsman_Animation'];rig=bpy.data.objects['Rig_Swordsman'];sword=bpy.data.objects['SM_Longsword']
rig.animation_data.action=bpy.data.actions['Idle'];bpy.context.scene.frame_set(1)
original=obj.data;copy=original.copy();bm=bmesh.new();bm.from_mesh(copy)
bmesh.ops.triangulate(bm,faces=list(bm.faces),quad_method='BEAUTY',ngon_method='BEAUTY')
assert all(e.is_manifold for e in bm.edges)
bm.to_mesh(copy);bm.free();obj.data=copy
bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);rig.select_set(True);sword.select_set(True);bpy.context.view_layer.objects.active=rig
bpy.ops.export_scene.gltf(filepath=str(OUT/'SK_Swordsman_Polished_v005.glb'),export_format='GLB',
    use_selection=True,export_animations=True,export_animation_mode='ACTIONS',export_nla_strips=True,
    export_influence_nb=4,export_skins=True,export_rest_position_armature=True,
    export_cameras=False,export_lights=False,export_force_sampling=True,export_materials='EXPORT')
bpy.ops.export_scene.fbx(filepath=str(OUT/'SK_Swordsman_Polished_v005.fbx'),use_selection=True,
    object_types={'ARMATURE','MESH'},add_leaf_bones=False,bake_anim=True,bake_anim_use_all_actions=True,
    bake_anim_use_nla_strips=False,path_mode='COPY',embed_textures=True,
    axis_forward='-Z',axis_up='Y',use_armature_deform_only=False)
obj.data=original;bpy.data.meshes.remove(copy)
print('POLISHED_EXPORTED',flush=True)
