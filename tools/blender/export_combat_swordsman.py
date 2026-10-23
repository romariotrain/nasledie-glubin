"""Reduce redundant animation keys; export the nine authored clips only."""
import bpy, bmesh, tempfile, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]; OUT = Path(bpy.data.filepath).parent
VERSION = OUT.name.rsplit('_', 1)[-1]
tempfile.tempdir = str(ROOT / 'work/hunyuan2mini/export-temp')
rig = bpy.data.objects['Rig_Swordsman']; obj = bpy.data.objects['SK_Swordsman_Animation']
sword = bpy.data.objects['SM_Longsword']

# FBX carries joint transforms, not Blender bone lengths. A vertical Root with
# a single vertical child is reconstructed as connected by Blender's importer,
# which suppresses animated Hips translations. A horizontal display direction
# for the nondeforming Root avoids that inference without adding bones or motion.
bpy.ops.object.select_all(action='DESELECT'); rig.select_set(True)
bpy.context.view_layer.objects.active = rig
bpy.ops.object.mode_set(mode='EDIT')
root = rig.data.edit_bones['Root']; root.tail = root.head + __import__('mathutils').Vector((.126, 0, 0))
bpy.ops.object.mode_set(mode='OBJECT')
for pb in rig.pose.bones:
    pb.lock_location = (False, False, False)


def keep_rdp(points, tolerance=.00004):
    keep = {0, len(points)-1}; stack = [(0, len(points)-1)]
    while stack:
        a, b = stack.pop(); start, end = points[a], points[b]; worst = 0; index = None
        for i in range(a+1, b):
            t = (points[i][0]-start[0]) / (end[0]-start[0])
            error = abs(points[i][1]-(start[1]+(end[1]-start[1])*t))
            if error > worst: worst, index = error, i
        if worst > tolerance:
            keep.add(index); stack.extend([(a, index), (index, b)])
    return keep


before = after = 0
for action in bpy.data.actions:
    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                for curve in bag.fcurves:
                    points = [p.co[:] for p in curve.keyframe_points]; before += len(points)
                    keep = keep_rdp(points)
                    for i in reversed(range(len(points))):
                        if i not in keep: curve.keyframe_points.remove(curve.keyframe_points[i], fast=True)
                    for key in curve.keyframe_points: key.interpolation = 'LINEAR'
                    curve.update(); after += len(curve.keyframe_points)
rig.animation_data.action = bpy.data.actions['idle']; bpy.context.scene.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT / f'swordsman_combat_{VERSION}.blend'))
original = obj.data; triangulated = original.copy()
bm = bmesh.new(); bm.from_mesh(triangulated)
bmesh.ops.triangulate(bm, faces=list(bm.faces), quad_method='BEAUTY', ngon_method='BEAUTY')
assert all(e.is_manifold for e in bm.edges), 'Body has a nonmanifold edge'
bm.to_mesh(triangulated); bm.free(); obj.data = triangulated
bpy.ops.object.select_all(action='DESELECT')
for o in (obj, rig, sword): o.select_set(True)
bpy.context.view_layer.objects.active = rig
bpy.ops.export_scene.gltf(filepath=str(OUT / f'SK_Swordsman_Combat_{VERSION}.glb'), export_format='GLB',
    use_selection=True, export_animations=True, export_animation_mode='ACTIONS',
    export_influence_nb=4, export_skins=True, export_rest_position_armature=True,
    export_cameras=False, export_lights=False, export_force_sampling=True, export_materials='EXPORT')
bpy.ops.export_scene.fbx(filepath=str(OUT / f'SK_Swordsman_Combat_{VERSION}.fbx'), use_selection=True,
    object_types={'ARMATURE','MESH'}, add_leaf_bones=False, bake_anim=True,
    bake_anim_use_all_actions=True, bake_anim_use_nla_strips=False,
    bake_anim_step=.125, bake_anim_simplify_factor=0.0,
    path_mode='COPY', embed_textures=True, axis_forward='-Z', axis_up='Y', use_armature_deform_only=False)
obj.data = original; bpy.data.meshes.remove(triangulated)
(OUT / 'key_reduction.json').write_text(json.dumps(dict(before=before, after=after, tolerance=.00004)), encoding='utf-8')
print('COMBAT_EXPORTED', before, after, flush=True)
