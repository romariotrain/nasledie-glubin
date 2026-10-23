"""Bind Unity source, imported asset and the tested Windows player to receipts."""
import hashlib, json, shutil
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / 'unity/SwordsmanCombatTest'
OUT = PROJECT / 'Validation'
WORK = ROOT / 'work/unity-test'


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


runtime = json.loads((OUT / 'runtime-test-report.json').read_text(encoding='utf-8'))
assert runtime['passed'] and not runtime['runtimeErrors']
assert len(runtime['checks']) == 18 and all(c['passed'] for c in runtime['checks'])
build = json.loads((WORK / 'build-result.json').read_text(encoding='utf-8'))
assert build['result'] == 'Succeeded' and build['errors'] == 0 and build['warnings'] == 0
engine = json.loads((WORK / 'unity-import-report.json').read_text(encoding='utf-8'))
assert engine['avatarValid'] and engine['triangles'] == 11980 and engine['clips'] == 9
admission = json.loads((PROJECT / 'Assets/SwordsmanTest/Art/admission_receipt.json').read_text(encoding='utf-8'))
fbx = PROJECT / 'Assets/SwordsmanTest/Art' / next(f for f in admission['copied'] if f.endswith('.fbx'))
assert sha(fbx) == engine['sourceFbxSha256']
for filename, expected in admission['copied'].items():
    assert sha(fbx.parent / filename) == expected
for filename, meta in admission['derived'].items():
    assert sha(fbx.parent / filename) == meta['sha256']
with Image.open(OUT / 'unity_playtest.png') as image:
    assert min(image.size) >= 600
    assert max(high-low for low, high in image.convert('RGB').getextrema()) > 100, 'Blank visible-window capture'
for filename in ('unity-import-report.json', 'build-result.json'):
    shutil.copyfile(WORK / filename, OUT / filename)
project_files = [p for folder in ('Assets/SwordsmanTest', 'ProjectSettings', 'Packages')
                 for p in (PROJECT / folder).rglob('*') if p.is_file()]
build_root = WORK / 'Build'
build_files = [p for p in build_root.rglob('*') if p.is_file()]
evidence = [p for p in OUT.iterdir() if p.is_file() and p.suffix in ('.json', '.png')
            and p.name not in ('validation_receipt.json', 'unity_screen_with_hud.png')]
receipt = dict(status='unity_test_scene_functional_checks_passed',
               unity=runtime['unity'], gpu=runtime['gpu'], graphics_api=runtime['graphicsApi'],
               source_package_manifest_sha256=admission['package_manifest_sha256'],
               imported_fbx_sha256=sha(fbx), functional_checks=len(runtime['checks']),
               project_files={str(p.relative_to(PROJECT)): sha(p) for p in sorted(project_files)},
               build_files={str(p.relative_to(build_root)): sha(p) for p in sorted(build_files)},
               evidence={p.name: sha(p) for p in sorted(evidence)},
               reviewed_screenshot='unity_playtest.png (ordinary game window, HUD visible)',
               limits=['Scripted inputs validate engine behaviour, not human input feel',
                       'No production FPS benchmark or large enemy-crowd test',
                       'No exhaustive cloth-intersection test across every engine blend'])
path = OUT / 'validation_receipt.json'
path.write_text(json.dumps(receipt, indent=2), encoding='utf-8')
version = Path(admission['source_package']).name.rsplit('_v', 1)[-1]
job = ROOT / f'work/character-jobs/swordsman-combat-{version}/stages.json'
stages = json.loads(job.read_text(encoding='utf-8'))
stages['engine_import'] = dict(status='passed_in_unity_test_scene',
                              evidence=[dict(path=str(path.relative_to(ROOT)), sha256=sha(path))],
                              scope='FBX import, rendered window + HUD, 18 scripted runtime checks; not production validation')
job.write_text(json.dumps(stages, indent=2), encoding='utf-8')
print('UNITY_VALIDATION_SEALED', len(project_files), 'project files,', len(build_files), 'build files, 18 checks')
