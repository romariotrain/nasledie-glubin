"""Identical cameras and light for silhouette comparison, no source overwrite."""
import bpy, sys, argparse
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser();p.add_argument('--versions',nargs=2,default=['v006','v007'])
a=p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
OUT=ROOT/f'art/characters/swordsman/hunyuan_combat_{a.versions[1]}/comparison';OUT.mkdir(exist_ok=True)
for version in a.versions:
    bpy.ops.wm.open_mainfile(filepath=str(ROOT/f'art/characters/swordsman/hunyuan_combat_{version}/swordsman_combat_{version}.blend'))
    scene=bpy.context.scene;rig=bpy.data.objects['Rig_Swordsman']
    rig.animation_data.action=bpy.data.actions['idle'];scene.frame_set(1)
    scene.render.engine='BLENDER_EEVEE';scene.eevee.taa_render_samples=16
    scene.render.resolution_x=512;scene.render.resolution_y=640;scene.render.resolution_percentage=100
    scene.view_settings.view_transform='Standard';scene.view_settings.look='Medium High Contrast'
    camera=scene.camera;camera.data.ortho_scale=2.25
    for view,location in [('front',(-1.8,-5,2.1)),('side',(-5,-.1,1.7)),('back',(1.8,5,2.1))]:
        camera.location=location;camera.rotation_euler=(Vector((0,0,.90))-camera.location).to_track_quat('-Z','Y').to_euler()
        scene.render.filepath=str(OUT/f'{version}_{view}.png');bpy.ops.render.render(write_still=True)
print('SILHOUETTE_COMPARISON_READY',flush=True)
