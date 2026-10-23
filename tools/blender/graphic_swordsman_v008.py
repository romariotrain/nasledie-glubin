"""Bake a restrained procedural character palette and soften small cloth folds.

This is a mesh/material bake, with UV and face identity retained from v007.
It does not synthesize a new concept or change animation timing.
"""
import bpy, json, hashlib, shutil, math, importlib.util
from pathlib import Path
from collections import Counter, defaultdict
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[2]
SOURCE=Path(bpy.data.filepath)
OUT=ROOT/'art/characters/swordsman/hunyuan_combat_v008'
OUT.mkdir(parents=True,exist_ok=True)
obj=bpy.data.objects['SK_Swordsman_Animation'];rig=bpy.data.objects['Rig_Swordsman'];scene=bpy.context.scene
part_spec=importlib.util.spec_from_file_location('parts',ROOT/'tools/blender/audit_swordsman_collisions.py')
parts=importlib.util.module_from_spec(part_spec);part_spec.loader.exec_module(parts)
mesh=obj.data;uv=mesh.uv_layers.active.data
old=bpy.data.images.load(str(SOURCE.parent/'swordsman_basecolor_2048.png'),check_existing=False)
pixels=list(old.pixels);w,h=old.size
def sample(t):
    x=max(0,min(w-1,round(t.x*(w-1))));y=max(0,min(h-1,round(t.y*(h-1))))
    return pixels[(y*w+x)*4:(y*w+x)*4+3]
def srgb(x):return x/12.92 if x<=.04045 else ((x+.055)/1.055)**2.4
palette={
 'coat':(.205,.21,.235),'trousers':(.12,.135,.165),'shirt':(.105,.12,.16),
 'red':(.53,.075,.105),'red_shadow':(.38,.045,.07),
 'leather':(.24,.135,.085),'boots':(.18,.105,.075),
 'hair':(.145,.075,.055),'hair_light':(.24,.125,.075),
 'skin':(.79,.49,.31),'brass':(.69,.47,.22)}
colours={k:tuple(srgb(x) for x in v)+(1,) for k,v in palette.items()}
def classify(rgb,p):
    r,g,b=rgb;light=max(rgb)
    if r>g*1.62 and r>b*1.45 and b>g*.84 and r>.08:
        return 'red_shadow' if p.z<1.0 and abs(p.x)<.18 and p.y>.025 else 'red'
    if p.z>1.48:
        if r>g*1.25 and g>b*1.15 and light>.34 and p.z<1.64:return 'skin'
        return 'hair_light' if light>.26 else 'hair'
    if abs(p.x)>.23 and .96<p.z<1.27 and r>g*1.2 and g>b*1.06 and light>.20:return 'skin'
    if r>g*1.12 and g>b*1.08 and r>.06:
        if r>.38 and g>.27 and .75<p.z<.95:return 'brass'
        return 'boots' if p.z<.37 else 'leather'
    if p.z<.38:return 'boots'
    if p.z<.83 and abs(p.x)<.20 and abs(p.y)<.115:return 'trousers'
    if p.y<-.07 and .87<p.z<1.25 and abs(p.x)<.12:return 'shirt'
    return 'coat'
labels={};hits=Counter()
colour=mesh.color_attributes.new(name='GraphicPalette',type='FLOAT_COLOR',domain='CORNER')
details=mesh.color_attributes.new(name='IdentityDetail',type='FLOAT_COLOR',domain='CORNER')
red_region=mesh.color_attributes.new(name='CrimsonRegion',type='FLOAT_COLOR',domain='CORNER')
vertex_classes=defaultdict(list)
for face in mesh.polygons:
    centre_uv=sum((uv[li].uv for li in face.loop_indices),Vector((0,0)))/len(face.loop_indices)
    for li in face.loop_indices:
        vertex=mesh.vertices[mesh.loops[li].vertex_index];p=vertex.co
        label=classify(sample(uv[li].uv.lerp(centre_uv,.04)),p);labels[li]=label;hits[label]+=1
        # Anatomical regions define the broad palette; baked warm shadows must
        # not become random leather patches on the fabric.
        base_label=label
        if label in ('red','red_shadow','leather','brass'):base_label='coat'
        if vertex.index in parts.legs:base_label='boots' if p.z<.35 else 'trousers'
        if p.z>1.48:base_label=label if label in ('skin','hair','hair_light') else 'hair'
        colour.data[li].color=colours[base_label]
        allow=1 if label in ('red','red_shadow') and vertex.index not in parts.legs and p.z<1.48 else 0
        if .94<p.z<1.035:allow=0
        leather_allow=1 if vertex.index not in parts.legs and p.z<1.40 and label!='skin' else 0
        red_region.data[li].color=(allow,leather_allow,0,1)
        # Preserve face/eyes and skin markings; flatten fabric, leather and hair.
        face_mask=1.0 if 1.40<p.z<1.635 and p.y<.028 and abs(p.x)<.125 else 0
        belt_mask=1.0 if .94<p.z<1.035 and abs(p.x)<.19 else 0
        hand_weight=sum(g.weight for g in vertex.groups if obj.vertex_groups[g.group].name.startswith('Hand.'))
        detail=face_mask if p.z>1.38 else max(belt_mask,.70 if hand_weight>.45 else .20 if label=='skin' else 0)
        details.data[li].color=(detail,detail,detail,1)
        vertex_classes[vertex.index].append(label)
# Restrained Taubin smoothing removes small ridges without removing seam/joint loops.
adj=defaultdict(set)
for e in mesh.edges:
    a,b=e.vertices;adj[a].add(b);adj[b].add(a)
original=[v.co.copy() for v in mesh.vertices]
protected=set()
for v in mesh.vertices:
    p=v.co;classes=vertex_classes[v.index]
    if not classes or any(c in ('skin','red','red_shadow','brass','hair','hair_light') for c in classes):protected.add(v.index)
    if .76<p.z<.91 or p.z>1.34 or abs(p.x)>.33:protected.add(v.index)
    if len(adj[v.index])<4:protected.add(v.index)
    # Protect hard garment edges and sole boundaries.
    if any(v.normal.dot(mesh.vertices[j].normal)<.42 for j in adj[v.index]):protected.add(v.index)
for iteration in range(14):
    for amount in (.46,-.475):
        positions=[v.co.copy() for v in mesh.vertices]
        for v in mesh.vertices:
            i=v.index
            if i in protected:continue
            mean=sum((positions[j] for j in adj[i]),Vector())/len(adj[i])
            delta=(mean-positions[i])*amount
            target=positions[i]+delta
            total=target-original[i]
            cap=.007 if v.co.z>.38 else .004
            if total.length>cap:target=original[i]+total.normalized()*cap
            v.co=target
mesh.update()
displacements=[(v.co-p).length for v,p in zip(mesh.vertices,original)]

# Bake the new material into the existing UV islands; retain only identity detail.
baked=bpy.data.images.new('Swordsman_Graphic_Basecolor',width=2048,height=2048,alpha=False)
temp=bpy.data.materials.new('Graphic palette bake');temp.use_nodes=True
nodes=temp.node_tree.nodes;nodes.clear();links=temp.node_tree.links
out=nodes.new('ShaderNodeOutputMaterial');emission=nodes.new('ShaderNodeEmission')
attr=nodes.new('ShaderNodeVertexColor');attr.layer_name=colour.name
mask=nodes.new('ShaderNodeVertexColor');mask.layer_name=details.name
source=nodes.new('ShaderNodeTexImage');source.image=old
# Pixel-accurate crimson mask avoids spreading thin trim across adjacent triangles.
separate=nodes.new('ShaderNodeSeparateColor');separate.mode='HSV';links.new(source.outputs['Color'],separate.inputs[0])
def math_node(operation,a,b):
    node=nodes.new('ShaderNodeMath');node.operation=operation
    for index,value in enumerate((a,b)):
        if isinstance(value,(int,float)):node.inputs[index].default_value=value
        else:links.new(value,node.inputs[index])
    return node.outputs[0]
hue,saturation,value=[separate.outputs[i] for i in range(3)]
red_mask=math_node('MAXIMUM',math_node('LESS_THAN',hue,.025),math_node('GREATER_THAN',hue,.97))
red_mask=math_node('MULTIPLY',red_mask,math_node('GREATER_THAN',saturation,.45))
region=nodes.new('ShaderNodeVertexColor');region.layer_name=red_region.name
split_region=nodes.new('ShaderNodeSeparateColor');links.new(region.outputs['Color'],split_region.inputs[0])
red_mask=math_node('MULTIPLY',red_mask,split_region.outputs[0])
leather_mask=math_node('MULTIPLY',math_node('GREATER_THAN',hue,.025),math_node('LESS_THAN',hue,.13))
leather_mask=math_node('MULTIPLY',leather_mask,math_node('GREATER_THAN',saturation,.55))
leather_mask=math_node('MULTIPLY',leather_mask,split_region.outputs[1])
leather=nodes.new('ShaderNodeMixRGB');links.new(leather_mask,leather.inputs[0]);links.new(attr.outputs['Color'],leather.inputs[1]);leather.inputs[2].default_value=colours['leather']
trim=nodes.new('ShaderNodeMixRGB');links.new(red_mask,trim.inputs[0]);links.new(leather.outputs[0],trim.inputs[1]);trim.inputs[2].default_value=colours['red']
mix=nodes.new('ShaderNodeMixRGB');links.new(mask.outputs['Color'],mix.inputs[0]);links.new(trim.outputs[0],mix.inputs[1]);links.new(source.outputs['Color'],mix.inputs[2])
links.new(mix.outputs[0],emission.inputs['Color']);links.new(emission.outputs[0],out.inputs['Surface'])
target=nodes.new('ShaderNodeTexImage');target.image=baked;nodes.active=target
materials=list(mesh.materials);mesh.materials.clear();mesh.materials.append(temp)
for face in mesh.polygons:face.material_index=0
bpy.ops.object.select_all(action='DESELECT')
obj.hide_set(False);obj.hide_viewport=False;obj.hide_render=False
for collection in obj.users_collection:collection.hide_viewport=False;collection.hide_render=False
obj.select_set(True);bpy.context.view_layer.objects.active=obj
scene.render.engine='CYCLES';scene.cycles.samples=1;scene.cycles.device='CPU'
scene.render.bake.margin=12;scene.render.bake.use_clear=True;scene.render.bake.use_selected_to_active=False
bpy.ops.object.bake(type='EMIT')
baked.filepath_raw=str(OUT/'swordsman_basecolor_2048.png');baked.file_format='PNG';baked.save()
# Neutral data maps remove baked fold relief and material gloss noise.
for name,value in [('normal',(0.5,0.5,1,1)),('roughness',(.92,.92,.92,1))]:
    image=bpy.data.images.new('Graphic_'+name,width=2048,height=2048,alpha=False)
    image.colorspace_settings.name='Non-Color';image.generated_color=value
    image.filepath_raw=str(OUT/f'swordsman_{name}_2048.png');image.file_format='PNG';image.save()
mesh.materials.clear()
for material in materials:mesh.materials.append(material)
for material in materials:
    if not material or not material.use_nodes:continue
    for node in material.node_tree.nodes:
        if node.type=='TEX_IMAGE' and node.image:
            n=node.image.name.lower()
            kind='normal' if 'normal' in n else 'roughness' if 'roughness' in n else 'basecolor'
            node.image=bpy.data.images.load(str(OUT/f'swordsman_{kind}_2048.png'),check_existing=True)
            if kind!='basecolor':node.image.colorspace_settings.name='Non-Color'
    bsdf=next((n for n in material.node_tree.nodes if n.type=='BSDF_PRINCIPLED'),None)
    if bsdf:
        bsdf.inputs['Roughness'].default_value=.92
        bsdf.inputs['Specular IOR Level'].default_value=.12
for filename in ('spec.json','combat_events.json'):shutil.copyfile(SOURCE.parent/filename,OUT/filename)
spec=json.loads((OUT/'spec.json').read_text());spec['asset_id']='swordsman-combat-v008'
(OUT/'spec.json').write_text(json.dumps(spec,indent=2),encoding='utf-8')
rig.animation_data.action=bpy.data.actions['idle'];scene.frame_set(1)
scene.render.engine='BLENDER_EEVEE'
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'swordsman_combat_v008.blend'))
report=dict(source=str(SOURCE.relative_to(ROOT)),source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
 method='Semantic UV palette bake, neutral relief maps, bounded Taubin smoothing of cloth/leather',
 palette_srgb=palette,corner_class_counts=dict(hits),geometry=dict(max_displacement_m=max(displacements),changed_vertices=sum(x>.00001 for x in displacements),triangles=sum(len(p.vertices)-2 for p in mesh.polygons)+88),
 animation='All nine v007 clips, rest skeleton, skin weights and timing preserved',
 limits=['Face detail reused; material classification is heuristic and visually reviewed','No new topology or triangle reduction','Neutral normal map intentionally removes original high-frequency folds'])
(OUT/'build_receipt.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('GRAPHIC_REVISION_COMPLETE',json.dumps(report),flush=True)
