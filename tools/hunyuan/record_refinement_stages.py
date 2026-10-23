"""Record the bounded evidence of the v007 revision without claiming new generation."""
import hashlib, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'art/characters/swordsman/hunyuan_combat_v007'
job=ROOT/'work/character-jobs/swordsman-combat-007/stages.json'
stages=json.loads(job.read_text())
def record(stage,status,paths,scope):
    stages[stage]=dict(status=status,scope=scope,evidence=[dict(path=str(p.relative_to(ROOT)),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in paths])
record('references','reviewed',[ROOT/'art/characters/swordsman/reference/run_target_2026-10-23.png',ROOT/'art/characters/swordsman/reference/actions_target_2026-10-23.png'],'User run/action references plus lighter-silhouette instructions')
for stage in ('shape','cleanup','retopology','uv_textures'):
    record(stage,'reused_and_refined',[OUT/'refinement_report.json',OUT/'build_receipt.json'],'Existing v006 mesh, joint topology and maps; proportion refinement, no new generation or triangle reduction')
record('rig_weights','validated_in_exports',[OUT/'validation/release_glb.json',OUT/'validation/release_fbx.json'],'Rest proportions adapted; normalized bounded weights; not a new rig')
record('animations','sampled_checks_passed',[OUT/'source_validation.json',OUT/'roundtrip_validation.json',OUT/'cloth_correction.json'],'Nine clips; fixed Root, socket, sampled lower-coat contact and pose roundtrip; arbitrary blends not proven')
record('visual_review','reviewed_first_iteration',[OUT/'before_after.png',OUT/'pose_contact_sheet.jpg',ROOT/'unity/SwordsmanCombatTest/Validation/unity_playtest.png'],'Identical-camera proportions and actual Unity frame reviewed; original folds/textures still partly volumetric, further art polish possible')
record('export_validation','passed',[OUT/'validation/release_glb.json',OUT/'validation/release_fbx.json',OUT/'roundtrip_validation.json'],'GLB/FBX technical checks and bone/sword roundtrip')
job.write_text(json.dumps(stages,indent=2),encoding='utf-8')
print('REFINEMENT_EVIDENCE_RECORDED')
