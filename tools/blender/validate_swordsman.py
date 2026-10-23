"""Read back the saved study and check module/rig contracts, without saving changes."""
import bpy
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(bpy.data.filepath).resolve().parent
rig=bpy.data.objects['Rig_Swordsman']
assert len([o for o in bpy.data.objects if o.type=='ARMATURE']) == 1
skinned=['Body_Exposed','Body_Covered','Hair_Starter','Top_Longcoat','Top_ShortJacket','Legs_Trousers','Hands_Gloves','Feet_Boots']
checks=[]
for name in skinned:
    o=bpy.data.objects[name]
    mods=[m for m in o.modifiers if m.type=='ARMATURE']
    assert len(mods)==1 and mods[0].object==rig,name
    assert all(g.name in rig.data.bones for g in o.vertex_groups),name
    for v in o.data.vertices:
        assert v.groups and abs(sum(g.weight for g in v.groups)-1)<.0001,(name,v.index)
    checks.append(name+': shared rig; all vertices weighted; weights normalized')

socket=bpy.data.objects['Socket_Weapon_R']
assert socket.parent==rig and socket.parent_bone=='hand.R'
for name in ['Weapon_Longsword','Weapon_RelicSword']:
    assert bpy.data.objects[name].parent==socket,name
bpy.context.view_layer.update()
before=socket.matrix_world.copy()
pb=rig.pose.bones['forearm.R'];pb.rotation_mode='XYZ';pb.rotation_euler.x=.35
bpy.context.view_layer.update()
after=socket.matrix_world.copy()
assert sum(abs(after[i][j]-before[i][j]) for i in range(4) for j in range(4))>.01
pb.rotation_euler.x=0
bpy.context.view_layer.update()
checks.append('Both swords follow the right hand socket when the forearm is posed')

text=bpy.data.texts['SWAP_EQUIPMENT.py'].as_string()
exec(compile(text.replace("TOP = 'longcoat'", "TOP = 'jacket'").replace("WEAPON = 'longsword'", "WEAPON = 'relic'"),'swap_test','exec'))
assert bpy.data.collections['10 | TOP - Longcoat [active]'].hide_render
assert not bpy.data.collections['11 | TOP - Short jacket [alternative]'].hide_render
assert bpy.data.collections['50 | WEAPON - Longsword [active]'].hide_render
assert not bpy.data.collections['51 | WEAPON - Relic sword [alternative]'].hide_render
exec(compile(text,'swap_restore','exec'))
assert not bpy.data.collections['10 | TOP - Longcoat [active]'].hide_viewport
assert bpy.data.collections['11 | TOP - Short jacket [alternative]'].hide_viewport
checks.append('Equipment helper switches both tops and both weapons and restores the initial set')
assert bpy.data.collections['02 | Body covered [hidden]'].hide_render
report={'passed':True,'checks':checks,'not_checked':['Unity import','combat animation deformation extremes','production topology/UV suitability']}
(OUT/'validation_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False))
