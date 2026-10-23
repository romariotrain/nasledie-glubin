"""Render actual combat model poses and clips; no engine-runtime claims."""
import bpy, sys, json, argparse
from pathlib import Path
from mathutils import Vector

p = argparse.ArgumentParser(); p.add_argument('--mode', choices=['keys', 'clips', 'combo'], default='keys')
p.add_argument('--clip',default=None)
a = p.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
OUT = Path(bpy.data.filepath).parent
scene = bpy.context.scene; rig = bpy.data.objects['Rig_Swordsman']
scene.render.engine = 'BLENDER_EEVEE'
if hasattr(scene, 'eevee'):
    scene.eevee.taa_render_samples = 16
scene.render.resolution_x = 512; scene.render.resolution_y = 512
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.view_settings.view_transform = 'Standard'; scene.view_settings.look = 'Medium High Contrast'
camera = scene.camera
camera.data.type = 'ORTHO'; camera.data.ortho_scale = 3.3
camera.location = (-3.8, -5.5, 3.6)
camera.rotation_euler = (Vector((0, -.05, .86)) - camera.location).to_track_quat('-Z', 'Y').to_euler()
scene.world.use_nodes = True
scene.world.node_tree.nodes['Background'].inputs[0].default_value = (.11, .14, .18, 1)
scene.world.node_tree.nodes['Background'].inputs[1].default_value = .5
bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, -.012))
plane = bpy.context.object; plane.name = 'Preview_Ground'
mat = bpy.data.materials.new('Preview_Floor'); mat.diffuse_color = (.11, .13, .15, 1)
mat.use_nodes = True
mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (.11, .13, .15, 1)
mat.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = .95
plane.data.materials.append(mat)
keys = {'idle': [1], 'run': [4, 9, 14], 'attack_1': [4, 7, 13], 'attack_2': [1, 6, 13],
        'attack_3': [7, 11, 13, 21], 'dodge': [3, 7], 'piercing_lunge': [5, 8, 11],
        'hurt': [3], 'death': [13, 25, 37]}
receipt = []
if a.mode == 'combo':
    folder = OUT / 'combo_frames'; folder.mkdir(exist_ok=True)
    sequence = [('idle', f) for f in range(1, 13)]
    for name, first in [('attack_1', 1), ('attack_2', 2), ('attack_3', 2)]:
        sequence += [(name, f) for f in range(first, round(bpy.data.actions[name].frame_range[1]) + 1)]
    sequence += [('idle', f) for f in range(1, 19)]
    for index, (name, frame) in enumerate(sequence):
        rig.animation_data.action = bpy.data.actions[name]; scene.frame_set(frame)
        scene.render.filepath = str(folder / f'{index:03}.png')
        bpy.ops.render.render(write_still=True)
        receipt.append(dict(clip=name, frame=frame, file=str(Path(scene.render.filepath).relative_to(OUT))))
    (OUT / 'combo_frames.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    print('COMBO_PREVIEW_COMPLETE', flush=True)
    sys.exit(0)
for name, frames in keys.items():
    if a.clip and name!=a.clip:continue
    action = bpy.data.actions[name]; rig.animation_data.action = action
    folder = OUT / ('keyframes' if a.mode == 'keys' else 'preview_frames') / name
    folder.mkdir(parents=True, exist_ok=True)
    if a.mode == 'clips':
        frames = list(range(1, int(action.frame_range[1]) + 1, 2))
        if frames[-1] != int(action.frame_range[1]): frames.append(int(action.frame_range[1]))
    for f in frames:
        scene.frame_set(f); scene.render.filepath = str(folder / f'{f:03}.png')
        bpy.ops.render.render(write_still=True)
        receipt.append(dict(clip=name, frame=f, file=str(Path(scene.render.filepath).relative_to(OUT))))
    print('PREVIEW_RENDERED', name, flush=True)
(OUT / ('keyframes.json' if a.mode == 'keys' else 'preview_frames.json')).write_text(json.dumps(receipt, indent=2), encoding='utf-8')
print('PREVIEWS_COMPLETE', a.mode, flush=True)
