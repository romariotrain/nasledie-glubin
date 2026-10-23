import bpy
from pathlib import Path
OUT=Path(bpy.data.filepath).parent
scene=bpy.context.scene;rig=bpy.data.objects['Rig_Swordsman']
rig.animation_data.action=bpy.data.actions['Slash_01']
scene.camera.data.ortho_scale=2.9
scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=12
scene.render.resolution_percentage=100;scene.frame_set(18)
scene.render.filepath=str(OUT/'preview_Slash_01.png');bpy.ops.render.render(write_still=True)
scene.cycles.samples=4;scene.render.resolution_percentage=50
for frame in range(1,37,2):
    scene.frame_set(frame);scene.render.filepath=str(OUT/'frames_Slash_01'/f'{frame:03}.png')
    bpy.ops.render.render(write_still=True)
