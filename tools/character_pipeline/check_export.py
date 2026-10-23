"""Blender reimport audit: structural evidence, not an engine or art approval."""
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
import bpy

p = argparse.ArgumentParser()
p.add_argument('--spec', required=True, type=Path)
p.add_argument('--file', required=True, type=Path)
p.add_argument('--report', required=True, type=Path)
a = p.parse_args(sys.argv[sys.argv.index('--') + 1:])
spec = json.loads(a.spec.read_text(encoding='utf-8'))
errors = []


def require(condition, message):
    if not condition:
        errors.append(message)


def positions(meshes, value):
    bpy.context.scene.frame_set(math.floor(value), subframe=value - math.floor(value))
    bpy.context.view_layer.update()
    result = []
    for obj in meshes:
        evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
        mesh = evaluated.to_mesh()
        result.extend(evaluated.matrix_world @ v.co for v in mesh.vertices)
        evaluated.to_mesh_clear()
    return result


def distance(first, second):
    return max(((x - y).length for x, y in zip(first, second)), default=0)


if a.report.exists():
    raise FileExistsError(a.report)
bpy.ops.wm.read_factory_settings(use_empty=True)
if a.file.suffix.lower() == '.glb':
    bpy.ops.import_scene.gltf(filepath=str(a.file))
elif a.file.suffix.lower() == '.fbx':
    bpy.ops.import_scene.fbx(filepath=str(a.file), use_anim=True)
else:
    raise ValueError('Expected GLB or FBX')
rigs = [o for o in bpy.context.scene.objects if o.type == 'ARMATURE']
bone_shapes = {pb.custom_shape for rig in rigs for pb in rig.pose.bones if pb.custom_shape}
meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH' and o not in bone_shapes]
skinned = [o for o in meshes if any(m.type == 'ARMATURE' for m in o.modifiers)]
triangles = sum(len(poly.vertices) - 2 for o in meshes for poly in o.data.polygons)
require(bool(meshes) and bool(skinned), 'No skinned geometry')
require(len(rigs) == 1, 'Expected exactly one armature')
require(0 < triangles <= spec['budgets']['triangles_max'], 'Triangle budget exceeded or empty mesh')
bad_weights = 0
for o in meshes:
    require(all(math.isfinite(c) for v in o.data.vertices for c in v.co), f'{o.name}: nonfinite vertex')
    textured = any(mat and mat.use_nodes and any(n.type == 'TEX_IMAGE' and n.image for n in mat.node_tree.nodes)
                   for mat in o.data.materials)
    if textured:
        require(bool(o.data.uv_layers), f'{o.name}: missing UV on textured mesh')
    if o in skinned:
        bone_names = set(rigs[0].data.bones.keys()) if rigs else set()
        for v in o.data.vertices:
            weights = [g.weight for g in v.groups if o.vertex_groups[g.group].name in bone_names and g.weight > 1e-7]
            if not weights or len(weights) > spec['budgets']['max_influences'] or abs(sum(weights) - 1) > 2e-5:
                bad_weights += 1
require(bad_weights == 0, 'Missing, excessive or unnormalized bone weights')
images = [im for im in bpy.data.images if im.type == 'IMAGE' and im.users]
require(bool(images), 'No texture images')
for im in images:
    size = list(im.size)  # Blender loads packed images lazily on first size/pixel access.
    pixel = im.pixels[0] if min(size) > 0 and len(im.pixels) else None
    require(pixel is not None and math.isfinite(pixel), f'{im.name}: missing texture bytes')
    require(max(im.size) <= spec['budgets']['texture_size'], f'{im.name}: texture size exceeds budget')
clips = []
if len(rigs) == 1:
    rig = rigs[0]
    if rig.animation_data and rig.animation_data.nla_tracks:
        for track in rig.animation_data.nla_tracks:
            track.mute = True
    rig.animation_data_create()
    for requested in spec['animations']:
        matches = [ac for ac in bpy.data.actions if ac.name == requested['name'] or
                   ac.name.endswith('|' + requested['name']) or ac.name.endswith('_' + requested['name'])]
        require(len(matches) == 1, f"{requested['name']}: missing or ambiguous action")
        if len(matches) != 1:
            continue
        action = matches[0]
        rig.animation_data.action = action
        start, end = action.frame_range
        first, last = positions(meshes, start), positions(meshes, end)
        endpoint = distance(first, last)
        motion = max(distance(first, positions(meshes, start + (end - start) * t)) for t in (.25, .5, .75))
        duration = (end - start) / (bpy.context.scene.render.fps / bpy.context.scene.render.fps_base)
        require(abs(duration - requested['duration_s']) < .06, f"{requested['name']}: duration mismatch")
        require(motion > 1e-5, f"{requested['name']}: no sampled motion")
        if requested['loop'] and requested['motion'] == 'in_place':
            require(endpoint <= .001, f"{requested['name']}: loop position gap >1 mm")
        clips.append(dict(name=requested['name'], duration_s=duration,
                          endpoint_gap_m=endpoint, sampled_motion_m=motion))
report = dict(file=str(a.file), sha256=hashlib.sha256(a.file.read_bytes()).hexdigest(),
              spec_sha256=hashlib.sha256(a.spec.read_bytes()).hexdigest(), blender=bpy.app.version_string,
              triangles=triangles, bones=sum(len(r.data.bones) for r in rigs),
              meshes=[dict(name=o.name, triangles=sum(len(poly.vertices)-2 for poly in o.data.polygons)) for o in meshes],
              excluded_bone_display_shapes=[o.name for o in bone_shapes],
              skinned_meshes=len(skinned), bad_weight_vertices=bad_weights,
              images=[dict(name=im.name, size=list(im.size)) for im in images], clips=clips,
              technical_pass=not errors, errors=errors,
              not_checked=['silhouette', 'joint deformation quality', 'grip contact', 'cloth collisions',
                           'root motion trajectory', 'transition velocity continuity', 'engine import', 'runtime FPS'])
a.report.parent.mkdir(parents=True, exist_ok=True)
with a.report.open('x', encoding='utf-8') as stream:
    json.dump(report, stream, indent=2)
print('CHARACTER_AUDIT', json.dumps(report), flush=True)
if errors:
    raise RuntimeError('; '.join(errors))
