import bpy,math,random,json
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[2]
OUT=Path(bpy.data.filepath).parent
scene=bpy.context.scene;obj=bpy.data.objects['SK_Swordsman_Animation'];rig=bpy.data.objects['Rig_Swordsman'];sword=bpy.data.objects['SM_Longsword']
scene.render.engine='BLENDER_EEVEE'
scene.render.resolution_x=900;scene.render.resolution_y=900;scene.render.resolution_percentage=100
scene.view_settings.view_transform='Standard';scene.view_settings.look='Medium High Contrast'
camera=scene.camera
rig.animation_data.action=bpy.data.actions['Idle'];scene.frame_set(1);bpy.context.view_layer.update()
# Inspect the real modified hand and hilt from the outer/front side.
grip=rig.pose.bones['WeaponSocket.R'].head.copy()
camera.location=grip+Vector((-1.4,-2,1.0));camera.rotation_euler=(grip-camera.location).to_track_quat('-Z','Y').to_euler()
camera.data.ortho_scale=.42;scene.render.resolution_x=640;scene.render.resolution_y=640
scene.render.filepath=str(OUT/'grip_closeup.png');bpy.ops.render.render(write_still=True)

# A compact illustrative dungeon, kept out of the deliverable asset scene.
def mat(name,color):
    material=bpy.data.materials.new(name);material.diffuse_color=(*color,1);material.use_nodes=True
    p=material.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(*color,1);p.inputs['Roughness'].default_value=.9
    return material
materials=[mat('Stone_'+str(i),color) for i,color in enumerate([(.105,.12,.13),(.135,.145,.15),(.17,.16,.14),(.12,.13,.14)])]
wood=mat('Wood',(.12,.066,.025));iron=mat('Iron',(.06,.07,.075))
vertices=[];faces=[];indices=[]
def box(center,size,material_index):
    start=len(vertices);x,y,z=center;a,b,c=(s/2 for s in size)
    vertices.extend([(x-a,y-b,z-c),(x+a,y-b,z-c),(x+a,y+b,z-c),(x-a,y+b,z-c),
                     (x-a,y-b,z+c),(x+a,y-b,z+c),(x+a,y+b,z+c),(x-a,y+b,z+c)])
    faces.extend([tuple(start+i for i in f) for f in [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]])
    indices.extend([material_index]*6)
random.seed(31)
for x in range(-7,8):
    for y in range(-8,9):box((x*.48,y*.48,-.075),(.465,.465,.14),random.randrange(4))
for row in range(3):
    for x in range(-6,7):box((x*.50+(row%2)*.25,2.8,.16+row*.32),(.48,.38,.30),random.randrange(4))
for row in range(2):
    for y in range(-2,6):box((-2.9,y*.50,.16+row*.32),(.38,.48,.30),random.randrange(4))
mesh=bpy.data.meshes.new('Dungeon_Stones');mesh.from_pydata(vertices,[],faces);mesh.update()
floor=bpy.data.objects.new('Dungeon_Preview',mesh);scene.collection.objects.link(floor)
for m in materials:mesh.materials.append(m)
for polygon,index in zip(mesh.polygons,indices):polygon.material_index=index
modifier=floor.modifiers.new('Stone_edges','BEVEL');modifier.width=.012;modifier.segments=1
environment=bpy.data.objects.new('Scrolling_Environment',None);scene.collection.objects.link(environment);floor.parent=environment
for x,y,size in [(-1.7,1.9,.60),(1.8,2.0,.52),(-2.0,1.0,.42)]:
    bpy.ops.mesh.primitive_cube_add(size=1,location=(x,y,size/2))
    crate=bpy.context.object;crate.name='Preview_Crate';crate.dimensions=(size,size,size);crate.data.materials.append(wood);crate.parent=environment
    bevel=crate.modifiers.new('Edges','BEVEL');bevel.width=.025;bevel.segments=1
    for offset in (-.30,.30):
        bpy.ops.mesh.primitive_cube_add(size=1,location=(x+offset*size,y,size/2))
        band=bpy.context.object;band.name='Crate_band';band.dimensions=(size*.065,size*1.02,size*1.02);band.data.materials.append(iron);band.parent=environment
scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.06,.085,.12,1)
scene.world.node_tree.nodes['Background'].inputs[1].default_value=.55
for name in ('Key','Fill','Rim'):
    light=bpy.data.objects.get(name)
    if light:light.data.energy*=.65
light_data=bpy.data.lights.new('Warm_dungeon_light','AREA');light_data.energy=240;light_data.color=(1,.35,.10);light_data.size=2
light=bpy.data.objects.new('Warm_dungeon_light',light_data);scene.collection.objects.link(light);light.location=(-1.8,1.4,2)
light.rotation_euler=(Vector((0,0,0))-light.location).to_track_quat('-Z','Y').to_euler()
camera.location=(6,-8,10);camera.rotation_euler=(Vector((0,0,.65))-camera.location).to_track_quat('-Z','Y').to_euler()
camera.data.ortho_scale=5.2
scene.render.resolution_x=960;scene.render.resolution_y=960
scene.frame_start=1;scene.frame_end=235
rig.animation_data.action=bpy.data.actions['Game_Demo'];scene.frame_set(1)
scene.render.filepath=str(OUT/'game_camera_preview.png');bpy.ops.render.render(write_still=True)
# Object motion emulates a camera following a forward-moving player.
def ground_position(frame):
    if frame<=60:return 0
    if frame<=69:
        t=(frame-60)/9;return .47*.3*(t*t*t-.5*t*t*t*t)
    if frame<=129:return .47*.15+.47*(frame-69)/30
    if frame<=138:
        t=(frame-129)/9;return .47*2.15+.47*.3*(t-t*t*t+.5*t*t*t*t)
    return .47*2.30
frames=OUT/'game_preview_frames';frames.mkdir(exist_ok=True)
scene.render.resolution_percentage=67
for frame in range(1,236,4):
    scene.frame_set(frame);environment.location.y=ground_position(frame)
    scene.render.filepath=str(frames/f'{frame:03}.png');bpy.ops.render.render(write_still=True)
scene.render.resolution_percentage=100;scene.frame_set(1);environment.location.y=0
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'game_camera_preview.blend'))
print('GAME_PREVIEW_READY',flush=True)
