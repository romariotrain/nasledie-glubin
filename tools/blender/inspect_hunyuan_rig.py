import bpy,json,math
obj=bpy.data.objects['SK_Swordsman_Animation'];rig=bpy.data.objects['Rig_Swordsman']
print('QUADS',sum(len(p.vertices)==4 for p in obj.data.polygons))
group=obj.vertex_groups.get('Retopo_Joint_Rings')
print('JOINT_GROUP_VERTICES',sum(any(g.group==group.index and g.weight>.9 for g in v.groups) for v in obj.data.vertices))
bpy.context.scene.frame_set(90);bpy.context.view_layer.update()
evaluated=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=evaluated.to_mesh()
errors=[]
for edge in obj.data.edges:
    a,b=edge.vertices
    rest=(obj.data.vertices[a].co-obj.data.vertices[b].co).length
    posed=(mesh.vertices[a].co-mesh.vertices[b].co).length
    if rest>1e-5:errors.append((posed/rest,rest,posed,a,b))
for error in sorted(errors,reverse=True)[:12]:
    print('BAD_EDGE',error)
    for i in error[-2:]:
        v=obj.data.vertices[i]
        print('POINT',tuple(v.co),[(obj.vertex_groups[g.group].name,round(g.weight,3)) for g in v.groups])
evaluated.to_mesh_clear()
