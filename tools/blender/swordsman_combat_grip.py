"""Small rigid combat-grip rebuild, preserving the wrist, skinning and UV atlas."""
import bpy,bmesh,math,numpy as np
from mathutils import Vector

def rebuild_grip(obj,rig,out):
    matrix=rig.data.bones['Hand.R'].matrix_local.copy();inverse=matrix.inverted()
    hand_group=obj.vertex_groups['Hand.R'].index
    protect=obj.vertex_groups.get('Grip_Keep') or obj.vertex_groups.new(name='Grip_Keep')
    bm=bmesh.new();bm.from_mesh(obj.data)
    uv=bm.loops.layers.uv.active;deform=bm.verts.layers.deform.verify()
    axis=(matrix.to_3x3()@Vector((0,1,0))).normalized();plane=matrix@Vector((0,.015,0))
    nearby=[v for v in bm.verts if -.10<(inverse@v.co).y<.25 and abs((inverse@v.co).x)<.13 and abs((inverse@v.co).z)<.13 and v[deform].get(hand_group,0)>.05]
    vs=set(nearby);es=[e for e in bm.edges if all(v in vs for v in e.verts)];fs=[f for f in bm.faces if all(v in vs for v in f.verts)]
    bmesh.ops.bisect_plane(bm,geom=nearby+es+fs,dist=1e-6,plane_co=plane,plane_no=axis,clear_inner=False,clear_outer=False)
    remove=[]
    for face in bm.faces:
        p=inverse@face.calc_center_median()
        weight=sum(v[deform].get(hand_group,0) for v in face.verts)/len(face.verts)
        if .015<p.y<.26 and abs(p.x)<.13 and abs(p.z)<.13 and weight>.25:remove.append(face)
    removed=len(remove);bmesh.ops.delete(bm,geom=remove,context='FACES_ONLY')
    boundary=[]
    for vertex in bm.verts:
        p=inverse@vertex.co
        if abs(p.y-.015)<.00005 and abs(p.x)<.13 and abs(p.z)<.13 and vertex[deform].get(hand_group,0)>.1 and any(e.is_boundary for e in vertex.link_edges):boundary.append(vertex)
    assert len(boundary)>=6,'Wrist boundary not found'
    boundary.sort(key=lambda v:math.atan2((inverse@v.co).z,(inverse@v.co).x))
    new=[]
    def vertex(point):
        v=bm.verts.new(matrix@Vector(point));v[deform][hand_group]=1;v[deform][protect.index]=1;new.append(v);return v
    def face(vertices,skin=False):
        f=bm.faces.new(vertices)
        for loop in f.loops:loop[uv].uv=((48 if skin else 16)/2048,16/2048)
        return f
    def bridge(a,b,skin=False):
        i=j=0;na=len(a);nb=len(b)
        while i<na or j<nb:
            ta=(i+1)/na if i<na else 2;tb=(j+1)/nb if j<nb else 2
            if abs(ta-tb)<1e-7:face([a[i%na],a[(i+1)%na],b[(j+1)%nb],b[j%nb]],skin);i+=1;j+=1
            elif ta<tb:face([a[i%na],a[(i+1)%na],b[j%nb]],skin);i+=1
            else:face([a[i%na],b[(j+1)%nb],b[j%nb]],skin);j+=1
    # Ordering in X/Z around the hand axis follows the same angle convention
    # as the preserved wrist boundary. Normals are consistently recalculated.
    rings=[]
    for y,rx,rz in [(.028,.037,.027),(.072,.041,.027),(.111,.034,.022)]:
        rings.append([vertex((rx*math.cos(-math.pi+2*math.pi*i/8),y,-.006+rz*math.sin(-math.pi+2*math.pi*i/8))) for i in range(8)])
    bridge(boundary,rings[0]);bridge(rings[0],rings[1]);bridge(rings[1],rings[2]);face(list(reversed(rings[-1])))
    # Four curved finger pads wrap the handle at distinct longitudinal positions.
    for y in (.035,.057,.079,.101):
        finger=[]
        for theta in (math.pi,math.pi/2,0):
            center=Vector((.028*math.cos(theta),y,.025+.028*math.sin(theta)))
            radial=Vector((math.cos(theta),0,math.sin(theta)))
            finger.append([vertex(center+radial*(.009*math.cos(2*math.pi*i/4))+Vector((0,.009*math.sin(2*math.pi*i/4),0))) for i in range(4)])
        bridge(finger[0],finger[1]);bridge(finger[1],finger[2],True)
        face(list(reversed(finger[0])));face(finger[-1],True)
    thumb=[]
    for p in [(-.035,.025,.012),(-.043,.049,.045),(-.015,.073,.058)]:
        thumb.append([vertex(Vector(p)+Vector((.011*math.cos(2*math.pi*i/4),.010*math.sin(2*math.pi*i/4),0))) for i in range(4)])
    bridge(thumb[0],thumb[1]);bridge(thumb[1],thumb[2],True);face(list(reversed(thumb[0])));face(thumb[-1],True)
    unused=[v for v in bm.verts if not v.link_faces]
    if unused:bmesh.ops.delete(bm,geom=unused,context='VERTS')
    wire=[e for e in bm.edges if not e.link_faces]
    if wire:bmesh.ops.delete(bm,geom=wire,context='EDGES')
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(obj.data);bm.free();obj.data.update()
    for polygon in obj.data.polygons:polygon.use_smooth=True
    bpy.context.view_layer.objects.active=obj
    bpy.ops.object.select_all(action='DESELECT');obj.select_set(True)
    count=sum(len(p.vertices)-2 for p in obj.data.polygons)
    if count>11900:
        keep=obj.vertex_groups.new(name='Grip_And_Joints_Keep')
        protected={protect.index}
        if obj.vertex_groups.get('Retopo_Joint_Rings'):protected.add(obj.vertex_groups['Retopo_Joint_Rings'].index)
        for v in obj.data.vertices:
            if any(g.group in protected and g.weight>.9 for g in v.groups):keep.add([v.index],1,'REPLACE')
        modifier=obj.modifiers.new('Keep_total_under_12k','DECIMATE');modifier.ratio=11900/count
        modifier.vertex_group=keep.name;modifier.invert_vertex_group=True;modifier.vertex_group_factor=1000
        bpy.ops.object.modifier_apply(modifier=modifier.name)
    for vertex in obj.data.vertices:
        values=[(g.group,g.weight) for g in vertex.groups if obj.vertex_groups[g.group].name in rig.data.bones]
        values=sorted(values,key=lambda p:p[1],reverse=True)[:4];total=sum(w for _,w in values)
        for group in obj.vertex_groups:
            if group.name in rig.data.bones:group.remove([vertex.index])
        for index,value in values:obj.vertex_groups[index].add([vertex.index],value/total,'REPLACE')
    # Flat palette cells in a verified empty corner of all three existing maps.
    # No extra material or draw call is introduced for the new glove geometry.
    material=obj.data.materials[0]
    for node in material.node_tree.nodes:
        if node.type!='TEX_IMAGE' or node.image is None:continue
        original=node.image;image=original.copy();node.image=image
        width,height=image.size;buffer=np.empty(width*height*4,dtype=np.float32);image.pixels.foreach_get(buffer)
        pixels=buffer.reshape(height,width,4)
        if 'basecolor' in original.name.lower():
            brown=(.30,.17,.10,1);skin=(.80,.50,.30,1);filename='swordsman_basecolor_2048.png'
        elif 'roughness' in original.name.lower():
            brown=skin=(.82,.82,.82,1);filename='swordsman_roughness_2048.png'
        else:
            brown=skin=(.5,.5,1,1);filename='swordsman_normal_2048.png'
        pixels[:32,:32]=brown;pixels[:32,32:64]=skin
        if image.packed_file:image.unpack(method='REMOVE')
        image.pixels.foreach_set(pixels.ravel());image.filepath_raw=str(out/filename);image.file_format='PNG';image.save();image.reload();image.pack()
    return dict(removed_hand_faces=removed,new_grip_vertices=len(new),style='Four curved finger pads and opposing thumb, rigidly weighted to Hand.R; wrist preserved; palette UVs in unused atlas corner.')
