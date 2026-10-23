"""Bind the reviewed dungeon build to assets admitted into the user's open project."""
import json,hashlib,shutil,argparse
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[2]
PROJECT=ROOT/'unity/SwordsmanCombatTest'
PREVIEW=ROOT/'work/UnityDungeonPreview_v001'
WORK=ROOT/'work/unity-dungeon-test'
p=argparse.ArgumentParser();p.add_argument('--revision',default='v003');args=p.parse_args()
OUT=PROJECT/('Validation/dungeon_'+args.revision)
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda:f.read(4*1024*1024),b''):h.update(chunk)
    return h.hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8'))
runtime=read(OUT/'runtime-test-report.json');build=read(WORK/'build-result.json');engine=read(WORK/'unity-import-report.json')
expected_checks=24 if args.revision=='v003' else 18
assert runtime['passed'] and len(runtime['checks'])==expected_checks and all(c['passed'] for c in runtime['checks']) and not runtime['runtimeErrors']
assert build['result']=='Succeeded' and not build['errors'] and not build['warnings']
assert engine['avatarValid'] and engine['triangles']==11980 and engine['clips']==9
art=PROJECT/'Assets/SwordsmanTest/Art';admission=read(art/'admission_receipt.json')
for name,expected in admission['copied'].items():assert sha(art/name)==expected
for name,meta in admission['derived'].items():assert sha(art/name)==meta['sha256']
fbx=next(name for name in admission['copied'] if name.endswith('.fbx'))
assert sha(art/fbx)==engine['sourceFbxSha256']
version=Path(fbx).stem.rsplit('_',1)[-1]
scene=Path('Assets/SwordsmanTest/Scenes/DungeonCombatTest.unity')
prefab=f'SwordsmanPlayer_{version}.prefab' if version in ('v009','v010') else 'SwordsmanPlayer.prefab'
tuning='CombatTuning_v010.asset' if version=='v010' else 'CombatTuning.asset'
bound=[scene,Path('Assets/SwordsmanTest/Data')/tuning,Path('Assets/SwordsmanTest/Prefabs')/prefab]
bound.extend(p.relative_to(PROJECT) for p in (PROJECT/'Assets/SwordsmanTest').rglob('*.cs'))
bound.extend(p.relative_to(PROJECT) for p in (PROJECT/'Assets/SwordsmanTest/Art/Dungeon').iterdir() if p.is_file() and p.name not in ('provenance.json','provenance.json.meta'))
for path in bound:assert sha(PROJECT/path)==sha(PREVIEW/path),f'Project/build mismatch: {path}'
with Image.open(OUT/'unity_playtest.png') as image:
    assert image.width>=1000 and max(b-a for a,b in image.convert('RGB').getextrema())>100
for name in ('unity-import-report.json','build-result.json'):shutil.copyfile(WORK/name,OUT/name)
receipt=dict(status=f'engine_build_and_{expected_checks}_runtime_checks_passed',scene=str(scene),character=f'Admitted {version}; see source package receipt for change scope',
    gpu=runtime['gpu'],graphics_api=runtime['graphicsApi'],
    bound_project_files={str(p):sha(PROJECT/p) for p in sorted(set(bound))},
    imported_character_fbx_sha256=engine['sourceFbxSha256'],
    gameplay_tuning_sha256=sha(PROJECT/'Assets/SwordsmanTest/Data'/tuning),
    provenance_sha256=sha(art/'Dungeon/provenance.json'),
    build_files={str(p.relative_to(WORK/'Build')):sha(p) for p in sorted((WORK/'Build').rglob('*')) if p.is_file()},
    evidence={p.name:sha(p) for p in sorted(OUT.iterdir()) if p.is_file() and p.name!='validation_receipt.json'},
    visual_review='Actual D3D11 arena and ordinary visible game window reviewed; cool floor and localized warm fire light',
    limits=['First style prototype; not a pixel match to painted reference','Flame geometry is stylized placeholder VFX','No production crowd or FPS benchmark; scripted combat checks do not judge human game feel'])
(OUT/'validation_receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
job=ROOT/f'work/character-jobs/swordsman-combat-{version[1:]}/stages.json'
if job.exists():
    stages=read(job)
    stages['engine_import']=dict(status='passed_in_unity_test_scene',scope=f'D3D11 visible window, imported clips and {expected_checks} scripted functional checks',evidence=[dict(path=str((OUT/'validation_receipt.json').relative_to(ROOT)),sha256=sha(OUT/'validation_receipt.json'))])
    source=ROOT/admission['source_package']
    for stage,status,names in [('animations','source_and_roundtrip_checks_passed',['source_validation.json','roundtrip_validation.json','build_receipt.json']),('export_validation','passed',['validation/release_glb.json','validation/release_fbx.json']),('visual_review','reviewed',['pose_contact_sheet.jpg'])]:
        stages[stage]=dict(status=status,evidence=[dict(path=str((source/name).relative_to(ROOT)),sha256=sha(source/name)) for name in names])
    job.write_text(json.dumps(stages,indent=2),encoding='utf-8')
print('DUNGEON_VALIDATED',len(bound),'bound project files;',expected_checks,'checks; source character verified')
