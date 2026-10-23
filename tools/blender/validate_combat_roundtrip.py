"""Compare world-space sampled poses and weapon bounds after GLB/FBX reimport."""
import bpy, json, math, hashlib
from pathlib import Path
from mathutils import Vector

OUT = Path(bpy.data.filepath).parent
VERSION = OUT.name.rsplit('_', 1)[-1]
spec = json.loads((OUT / 'spec.json').read_text(encoding='utf-8'))
source_hash = hashlib.sha256(Path(bpy.data.filepath).read_bytes()).hexdigest()
samples = (0, .10, .25, .50, .75, 1)


def capture(rig, sword, frame):
    bpy.context.scene.frame_set(math.floor(frame), subframe=frame-math.floor(frame))
    bpy.context.view_layer.update()
    result = {pb.name: list(rig.matrix_world @ pb.head) for pb in rig.pose.bones}
    points = [sword.matrix_world @ v.co for v in sword.data.vertices]
    result['sword_min'] = [min(p[i] for p in points) for i in range(3)]
    result['sword_max'] = [max(p[i] for p in points) for i in range(3)]
    return result


baseline = {}
rig = bpy.data.objects['Rig_Swordsman']; sword = bpy.data.objects['SM_Longsword']
for clip in spec['animations']:
    action = bpy.data.actions[clip['name']]; rig.animation_data.action = action
    start, end = action.frame_range
    baseline[clip['name']] = [capture(rig, sword, start+(end-start)*t) for t in samples]

reports = []
for extension in ('glb', 'fbx'):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    path = OUT / f'SK_Swordsman_Combat_{VERSION}.{extension}'
    if extension == 'glb': bpy.ops.import_scene.gltf(filepath=str(path))
    else: bpy.ops.import_scene.fbx(filepath=str(path), use_anim=True)
    rig = next(o for o in bpy.context.scene.objects if o.type == 'ARMATURE')
    sword = next(o for o in bpy.context.scene.objects if o.type == 'MESH' and 'Longsword' in o.name)
    for track in rig.animation_data.nla_tracks: track.mute = True
    errors = []; poses = []
    for clip in spec['animations']:
        name = clip['name']
        action = next(ac for ac in bpy.data.actions if ac.name == name or ac.name.endswith('|' + name))
        rig.animation_data.action = action; start, end = action.frame_range
        maximum = 0; worst = None
        for i, t in enumerate(samples):
            actual = capture(rig, sword, start+(end-start)*t)
            expected = baseline[name][i]
            for key in expected:
                delta = (Vector(actual[key])-Vector(expected[key])).length
                if delta > maximum:
                    maximum = delta; worst = dict(bone_or_bound=key, t=t, actual=actual[key], expected=expected[key])
        poses.append(dict(clip=name, max_bone_head_or_weapon_bounds_error_m=maximum, worst=worst))
        if maximum > .003: errors.append(name + ': world pose roundtrip difference >3mm')
    reports.append(dict(file=path.name, sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                        samples_normalized=list(samples), poses=poses, errors=errors))
report = dict(source_sha256=source_hash, exports=reports,
              limits='Bone head positions and weapon bounds only; sampled times, not exhaustive geometry equivalence')
(OUT / 'roundtrip_validation.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print('COMBAT_ROUNDTRIP', json.dumps(report), flush=True)
if any(r['errors'] for r in reports): raise RuntimeError('Roundtrip pose checks failed')
