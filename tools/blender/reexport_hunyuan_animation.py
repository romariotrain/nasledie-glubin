"""Export explicit triangulation while retaining editable quads in the blend."""
import bpy,bmesh
from pathlib import Path
OUT=Path(bpy.data.filepath).parent
obj=bpy.data.objects['SK_Swordsman_Animation'];rig=bpy.data.objects['Rig_Swordsman']
bpy.context.scene.frame_set(1);bpy.context.view_layer.update()
original=obj.data;export=original.copy()
bm=bmesh.new();bm.from_mesh(export)
bmesh.ops.triangulate(bm,faces=list(bm.faces),quad_method='BEAUTY',ngon_method='BEAUTY')
assert all(e.is_manifold for e in bm.edges)
assert all(f.calc_area()>1e-12 for f in bm.faces)
bm.to_mesh(export);bm.free();obj.data=export
bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);rig.select_set(True)
bpy.context.view_layer.objects.active=rig
bpy.ops.export_scene.gltf(filepath=str(OUT/'SK_Swordsman_Anim_v004.glb'),export_format='GLB',
    use_selection=True,export_animations=True,export_animation_mode='ACTIVE_ACTIONS',
    export_influence_nb=4,export_skins=True,export_rest_position_armature=True,
    export_cameras=False,export_lights=False,export_force_sampling=True)
bpy.ops.export_scene.fbx(filepath=str(OUT/'SK_Swordsman_Anim_v004.fbx'),use_selection=True,
    object_types={'ARMATURE','MESH'},add_leaf_bones=False,bake_anim=True,
    bake_anim_use_all_actions=False,bake_anim_use_nla_strips=False,
    axis_forward='-Z',axis_up='Y',use_armature_deform_only=False)
obj.data=original;bpy.data.meshes.remove(export)
