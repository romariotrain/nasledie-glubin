"""UV material, high-to-low normal bake, in-place animation clips and exports."""
import bpy,bmesh,math,json,hashlib,tempfile
from pathlib import Path
from mathutils import Vector,Quaternion,Matrix
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'art/characters/swordsman/hunyuan_textured_v001'
workspace_temp=ROOT/'work/hunyuan2mini/export-temp';workspace_temp.mkdir(exist_ok=True)
tempfile.tempdir=str(workspace_temp)
obj=bpy.data.objects['SK_Swordsman_Animation'];rig=bpy.data.objects['Rig_Swordsman']
scene=bpy.context.scene
scene.frame_set(1);rig.animation_data_clear()
for pb in rig.pose.bones:pb.rotation_quaternion=(1,0,0,0);pb.location=(0,0,0)
bpy.context.view_layer.update()

material=bpy.data.materials.new('Swordsman_Stylized_Atlas');material.use_nodes=True
nodes=material.node_tree.nodes;links=material.node_tree.links
shader=nodes.get('Principled BSDF');shader.inputs['Roughness'].default_value=.8
shader.inputs['Specular IOR Level'].default_value=.25
def texture(name,filename,space='sRGB'):
    image=bpy.data.images.load(str(OUT/filename),check_existing=True)
    image.colorspace_settings.name=space
    node=nodes.new('ShaderNodeTexImage');node.name=name;node.image=image
    return node
base=texture('BaseColor_2048','swordsman_basecolor_2048.png')
rough=texture('Roughness_2048','swordsman_roughness_2048.png','Non-Color')
links.new(base.outputs['Color'],shader.inputs['Base Color'])
links.new(rough.outputs['Color'],shader.inputs['Roughness'])
obj.data.materials.clear();obj.data.materials.append(material)

# Bake tangent-space normals from the retained dense source on CPU.
normal_image=bpy.data.images.new('Swordsman_Normal_2048',width=2048,height=2048,alpha=False)
normal_image.colorspace_settings.name='Non-Color'
normal_node=nodes.new('ShaderNodeTexImage');normal_node.image=normal_image;normal_node.name='Baked_Normal'
nodes.active=normal_node
before=set(bpy.data.objects)
bpy.ops.import_scene.gltf(filepath=str(ROOT/'art/characters/swordsman/hunyuan_lowpoly_v002/swordsman_clean_high.glb'))
high=next(o for o in bpy.data.objects if o not in before and o.type=='MESH')
for vertex in high.data.vertices:
    p=high.matrix_world@vertex.co
    vertex.co=(p.x*.9,p.y*.9,(p.z+1)*.9)
high.matrix_world.identity()
for polygon in high.data.polygons:polygon.use_smooth=True
high.data.update()
scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=8
scene.render.bake.use_selected_to_active=True;scene.render.bake.cage_extrusion=.018
scene.render.bake.max_ray_distance=.065;scene.render.bake.margin=10
bpy.ops.object.select_all(action='DESELECT');high.select_set(True);obj.select_set(True)
bpy.context.view_layer.objects.active=obj
bpy.ops.object.bake(type='NORMAL',normal_space='TANGENT')
normal_image.filepath_raw=str(OUT/'swordsman_normal_2048.png');normal_image.file_format='PNG';normal_image.save()
bpy.data.objects.remove(high,do_unlink=True)
normal_map=nodes.new('ShaderNodeNormalMap');normal_map.inputs['Strength'].default_value=.65
links.new(normal_node.outputs['Color'],normal_map.inputs['Color']);links.new(normal_map.outputs['Normal'],shader.inputs['Normal'])

def simple_material(name,color,metal=0,roughness=.7):
    m=bpy.data.materials.new(name);m.use_nodes=True
    s=m.node_tree.nodes.get('Principled BSDF');s.inputs['Base Color'].default_value=(*color,1)
    s.inputs['Metallic'].default_value=metal;s.inputs['Roughness'].default_value=roughness
    return m
steel=simple_material('Sword_Steel',(.38,.44,.50),.8,.28)
leather=simple_material('Sword_Grip',(.065,.032,.018),0,.8)
bronze=simple_material('Sword_Guard',(.30,.17,.05),.7,.4)
verts=[];faces=[];material_ids=[]
def prism(rings,material_index,caps=True):
    start=len(verts);n=len(rings[0]);verts.extend([tuple(p) for ring in rings for p in ring])
    for k in range(len(rings)-1):
        for i in range(n):faces.append((start+k*n+i,start+k*n+(i+1)%n,start+(k+1)*n+(i+1)%n,start+(k+1)*n+i));material_ids.append(material_index)
    if caps:
        faces.extend([tuple(start+i for i in reversed(range(n))),tuple(start+(len(rings)-1)*n+i for i in range(n))]);material_ids.extend([material_index]*2)
def ring(z,rx,ry,n=8):return [(rx*math.cos(2*math.pi*i/n),ry*math.sin(2*math.pi*i/n),z) for i in range(n)]
prism([ring(-.085,.018,.018),ring(.085,.018,.018)],1)
prism([ring(-.10,.024,.024),ring(-.085,.024,.024)],2)
prism([[(-.085,-.016,.085),(.085,-.016,.085),(.085,.016,.085),(-.085,.016,.085)],
       [(-.085,-.016,.112),(.085,-.016,.112),(.085,.016,.112),(-.085,.016,.112)]],2)
prism([[(-.030,0,.112),(0,-.009,.112),(.030,0,.112),(0,.009,.112)],
       [(-.026,0,.64),(0,-.007,.64),(.026,0,.64),(0,.007,.64)],
       [(-.0005,0,.75),(0,-.0005,.75),(.0005,0,.75),(0,.0005,.75)]],0)
mesh=bpy.data.meshes.new('Longsword_Mesh');mesh.from_pydata(verts,[],faces);mesh.update()
sword=bpy.data.objects.new('SM_Longsword',mesh);bpy.context.collection.objects.link(sword)
for m in (steel,leather,bronze):mesh.materials.append(m)
for polygon,index in zip(mesh.polygons,material_ids):polygon.material_index=index
grip=rig.pose.bones['WeaponSocket.R'].head.copy()
orientation=Vector((0,-.38,-.925)).to_track_quat('Z','Y')
sword.parent=rig;sword.parent_type='BONE';sword.parent_bone='WeaponSocket.R'
bpy.context.view_layer.update()
sword.matrix_world=Matrix.Translation(grip)@orientation.to_matrix().to_4x4()
bpy.context.view_layer.update()

def reset():
    for pb in rig.pose.bones:pb.rotation_quaternion=(1,0,0,0);pb.location=(0,0,0);pb.scale=(1,1,1)
def rotate(name,axis,degrees):
    pb=rig.pose.bones[name];axis=pb.bone.matrix_local.to_quaternion().inverted()@Vector(axis)
    pb.rotation_quaternion=Quaternion(axis,math.radians(degrees))
def world_rotation(name,xyz):
    pb=rig.pose.bones[name];rest=pb.bone.matrix_local.to_quaternion()
    q=Quaternion((0,0,1),math.radians(xyz[2]))@Quaternion((1,0,0),math.radians(xyz[0]))@Quaternion((0,1,0),math.radians(xyz[1]))
    pb.rotation_quaternion=rest.inverted()@q@rest
def root_shift(offset):
    pb=rig.pose.bones['Root'];pb.location=pb.bone.matrix_local.to_quaternion().inverted()@Vector(offset)
def orient(name,head,target,desired_quat=None):
    pb=rig.pose.bones[name]
    rest=pb.bone.matrix_local.to_quaternion()
    if desired_quat is None:
        direction=(target-head).normalized()
        rest_direction=pb.bone.tail_local-pb.bone.head_local
        desired_quat=rest_direction.normalized().rotation_difference(direction)@rest
    pb.matrix=Matrix.Translation(head)@desired_quat.to_matrix().to_4x4()
    bpy.context.view_layer.update()
def leg_ik(side,ankle,roll=0):
    upper=rig.pose.bones['Thigh.'+side];lower=rig.pose.bones['Shin.'+side]
    head=upper.head.copy();a=upper.bone.length;b=lower.bone.length
    delta=Vector(ankle)-head;distance=min(delta.length,a+b-.0005)
    axis=delta.normalized();forward=Vector((0,-1,0));bend=(forward-axis*forward.dot(axis)).normalized()
    along=(a*a-b*b+distance*distance)/(2*distance)
    height=math.sqrt(max(0,a*a-along*along));knee=head+axis*along+bend*height
    orient(upper.name,head,knee);orient(lower.name,knee,Vector(ankle))
    foot=rig.pose.bones['Foot.'+side]
    q=Quaternion((1,0,0),math.radians(roll))@foot.bone.matrix_local.to_quaternion()
    orient(foot.name,Vector(ankle),None,q)

ankles={side:rig.data.bones['Foot.'+side].head_local.copy() for side in ('L','R')}
def idle(t):
    phase=2*math.pi*t
    root_shift((0,0,.004*math.sin(phase)))
    rotate('Chest',(1,0,0),1.2*math.sin(phase));rotate('Head',(0,0,1),1.5*math.sin(phase))
    rotate('UpperArm.R',(1,0,0),-8);rotate('Forearm.R',(1,0,0),-8)
    for side in ('L','R'):
        rotate('Coat_Front.'+side,(1,0,0),1.5*math.sin(phase))
def walk(t):
    phase=2*math.pi*t
    root_shift((.009*math.sin(phase),0,-.035+.006*math.cos(2*phase)))
    rotate('Chest',(0,0,1),3*math.sin(phase))
    rotate('UpperArm.L',(1,0,0),20*math.cos(phase));rotate('UpperArm.R',(1,0,0),-20*math.cos(phase)-8)
    rotate('Forearm.L',(1,0,0),-12);rotate('Forearm.R',(1,0,0),-18)
    bpy.context.view_layer.update()
    for side,offset in [('L',0),('R',.5)]:
        cycle=(t+offset)%1
        p=ankles[side].copy()
        if cycle<.6:
            s=cycle/.6;p.y+=-.14+.28*s;lift=0
        else:
            s=(cycle-.6)/.4;p.y+=.14-.28*(3*s*s-2*s*s*s);lift=.075*math.sin(math.pi*s)
        p.z+=lift
        leg_ik(side,p,roll=5*math.sin(phase+offset*2*math.pi) if lift>0 else 0)
        rotate('Coat_Front.'+side,(1,0,0),-8-8*math.cos(phase+offset*2*math.pi))
        rotate('Coat_Back.'+side,(1,0,0),5+6*math.cos(phase+offset*2*math.pi))
def attack(t):
    # Anticipation -> diagonal slash -> recovery, all in place.
    keys=[(0,(0,0,0,0)),(.28,(25,52,-30,-65)),(.48,(-65,24,30,-12)),(.68,(-45,15,15,-20)),(1,(0,0,0,0))]
    for (a,av),(b,bv) in zip(keys,keys[1:]):
        if a<=t<=b:
            s=(t-a)/(b-a);s=s*s*(3-2*s);x,y,z,elbow=[i+(j-i)*s for i,j in zip(av,bv)];break
    root_shift((0,-.035*math.sin(math.pi*t),-.02*math.sin(math.pi*t)))
    rotate('Chest',(0,0,1),z*.55);rotate('Spine',(1,0,0),-6*math.sin(math.pi*t))
    world_rotation('UpperArm.R',(x,y,z));rotate('Forearm.R',(1,0,0),elbow)
    world_rotation('UpperArm.L',(-15*math.sin(math.pi*t),-18*math.sin(math.pi*t),-z*.2))
    rotate('Forearm.L',(1,0,0),-25*math.sin(math.pi*t))
    for side in ('L','R'):
        rotate('Coat_Front.'+side,(1,0,0),-8*math.sin(math.pi*t))
    bpy.context.view_layer.update()
    for side in ('L','R'):leg_ik(side,ankles[side])

clips=[]
for name,frames,fn,loop in [('Idle',61,idle,True),('Walk_InPlace',31,walk,True),('Slash_01',37,attack,False)]:
    rig.animation_data_create();action=bpy.data.actions.new(name);rig.animation_data.action=action
    action.use_fake_user=True
    for frame in range(1,frames+1):
        scene.frame_set(frame);reset();fn((frame-1)/(frames-1));bpy.context.view_layer.update()
        for pb in rig.pose.bones:
            pb.keyframe_insert(data_path='rotation_quaternion',frame=frame,group=pb.name)
            pb.keyframe_insert(data_path='location',frame=frame,group=pb.name)
    clips.append(dict(name=name,frames=frames,seconds=(frames-1)/30,loop=loop))
rig.animation_data.action=bpy.data.actions['Idle'];scene.frame_start=1;scene.frame_end=61;scene.render.fps=30
scene.frame_set(1)

# Eevee shows the actual UV maps and normal map; neutral studio illumination.
scene.render.engine='CYCLES';scene.cycles.samples=12;scene.cycles.device='CPU'
scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.12,.15,.20,1)
scene.world.node_tree.nodes['Background'].inputs[1].default_value=.45
for name,location,power,size in [('Key',(3,-4,5),650,4),('Fill',(-3,-2,3),420,4),('Rim',(1,3,4),500,3)]:
    data=bpy.data.lights.new(name,'AREA');data.energy=power;data.shape='DISK';data.size=size
    light=bpy.data.objects.new(name,data);scene.collection.objects.link(light);light.location=location
    light.rotation_euler=(Vector((0,0,1))-light.location).to_track_quat('-Z','Y').to_euler()
camera=scene.camera;camera.location=(2.5,-5,2.5);camera.rotation_euler=(Vector((0,0,.95))-camera.location).to_track_quat('-Z','Y').to_euler()
camera.data.ortho_scale=2.35
scene.view_settings.view_transform='Standard';scene.view_settings.look='Medium High Contrast'
scene.render.resolution_x=720;scene.render.resolution_y=900;scene.render.resolution_percentage=100
for name,frame in [('Idle',1),('Walk_InPlace',8),('Slash_01',18)]:
    camera.data.ortho_scale=2.9 if name=='Slash_01' else 2.35
    rig.animation_data.action=bpy.data.actions[name];scene.frame_set(frame)
    scene.render.filepath=str(OUT/f'preview_{name}.png');bpy.ops.render.render(write_still=True)
# Back view material inspection.
rig.animation_data.action=bpy.data.actions['Idle'];scene.frame_set(1)
old_location=camera.location.copy();old_rotation=camera.rotation_euler.copy()
camera.location=(-2.5,5,2.5);camera.rotation_euler=(Vector((0,0,.95))-camera.location).to_track_quat('-Z','Y').to_euler()
scene.render.filepath=str(OUT/'preview_Back.png');bpy.ops.render.render(write_still=True)
camera.location=old_location;camera.rotation_euler=old_rotation

# Render short previews at lower resolution and samples.
scene.cycles.samples=4;scene.render.resolution_percentage=50
for clip in clips:
    camera.data.ortho_scale=2.9 if clip['name']=='Slash_01' else 2.35
    rig.animation_data.action=bpy.data.actions[clip['name']]
    directory=OUT/f"frames_{clip['name']}";directory.mkdir(exist_ok=True)
    for frame in range(1,clip['frames'],2):
        scene.frame_set(frame);scene.render.filepath=str(directory/f'{frame:03}.png');bpy.ops.render.render(write_still=True)
scene.render.resolution_percentage=100;scene.cycles.samples=24
camera.data.ortho_scale=2.35
rig.animation_data.action=bpy.data.actions['Idle'];scene.frame_set(1);scene.frame_end=61
for image in (base.image,rough.image,normal_image):image.pack()
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'swordsman_textured_v001.blend'))

# Explicitly triangulate only the export copy; keep editable joint quads in .blend.
original=obj.data;copy=original.copy();bm=bmesh.new();bm.from_mesh(copy)
bmesh.ops.triangulate(bm,faces=list(bm.faces),quad_method='BEAUTY',ngon_method='BEAUTY')
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
report=dict(character_triangles=sum(len(p.vertices)-2 for p in obj.data.polygons),
    sword_triangles=sum(len(p.vertices)-2 for p in sword.data.polygons),bones=len(rig.data.bones),
    uv_layers=len(obj.data.uv_layers),texture_size=2048,clips=clips,
    material_method='Front/rear concept projection to UV; CPU high-to-low tangent normal bake; authored roughness.',
    limitations='Prototype clips. FK baked analytic two-bone foot placement; no runtime IK or collision solver; rear texture is inferred; no facial/finger animation.')
(OUT/'material_animation_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('TEXTURED_ANIMATION_REPORT',json.dumps(report),flush=True)
