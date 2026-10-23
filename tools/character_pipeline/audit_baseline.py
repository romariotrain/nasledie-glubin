"""Read-only verification of the existing character + engine receipts.

Writes a new summary only when --report is supplied; never rebuilds or repairs assets.
Run from any directory with the existing project Python environment.
"""
import argparse,hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser()
p.add_argument('--version',default='v010')
p.add_argument('--revision',default='dungeon_v003')
p.add_argument('--report',type=Path)
args=p.parse_args()
asset=ROOT/f'art/characters/swordsman/hunyuan_combat_{args.version}'
project=ROOT/'unity/SwordsmanCombatTest'
validation=project/'Validation'/args.revision
errors=[];verified={};cache={}
def read(path):return json.loads(path.read_text(encoding='utf-8'))
def sha(path):
    path=path.resolve()
    if path not in cache:
        h=hashlib.sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda:stream.read(4*1024*1024),b''):h.update(chunk)
        cache[path]=h.hexdigest()
    return cache[path]
def check(path,expected):
    if not path.is_file():errors.append(f'Missing: {path.relative_to(ROOT)}');return
    if sha(path)!=expected:errors.append(f'Changed since receipt: {path.relative_to(ROOT)}')
    else:verified[str(path.relative_to(ROOT))]=expected
manifest=read(asset/'package_manifest.json')
for name,meta in manifest['files'].items():check(asset/name,meta['sha256'])
engine=read(validation/'validation_receipt.json')
for name,expected in engine['bound_project_files'].items():check(project/name,expected)
for name,expected in engine['build_files'].items():check(ROOT/'work/unity-dungeon-test/Build'/name,expected)
for name,expected in engine['evidence'].items():check(validation/name,expected)
runtime=read(validation/'runtime-test-report.json')
if not runtime['passed'] or runtime['runtimeErrors'] or not all(c['passed'] for c in runtime['checks']):errors.append('Runtime report contains failures')
export=read(asset/'validation/release_glb.json')
source=read(asset/'source_validation.json')
check(asset/f'swordsman_combat_{args.version}.blend',source['source_sha256'])
if source['errors'] or not export['technical_pass']:errors.append('Source/export report contains failures')
def tracked(prefix):
    result=subprocess.run(['git','ls-files','--',prefix],cwd=ROOT,capture_output=True,text=True,check=True)
    return len(result.stdout.splitlines())
summary=dict(audit='Existing sealed baseline integrity; no new engine run or artistic approval',
    baseline=dict(character=args.version,scene='Assets/SwordsmanTest/Scenes/DungeonCombatTest.unity',validation=args.revision,
                  unity=(project/'ProjectSettings/ProjectVersion.txt').read_text().splitlines()[0],
                  blender=export['blender'],gpu=runtime['gpu'],triangles=export['triangles'],bones=export['bones'],
                  clip_names=[c['name'] for c in read(asset/'spec.json')['animations']],functional_checks=len(runtime['checks'])),
    checks=runtime['checks'],source_run_stance=source.get('run_stance'),
    hash_verified_files=len(verified),hash_mismatches=errors,
    tracked_files={prefix:tracked(prefix) for prefix in ('unity','art','tools','docs')},
    source_manifest_sha256=sha(asset/'package_manifest.json'),engine_receipt_sha256=sha(validation/'validation_receipt.json'),
    limits=['Existing receipt verification is not a fresh build or clean-machine restoration',
            'No production performance, enemy crowd, exhaustive collision or gameplay quality guarantee'])
if args.report:
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(verified_files=len(verified),errors=errors,tracked_files=summary['tracked_files'],checks=len(runtime['checks'])),ensure_ascii=False))
raise SystemExit(bool(errors))
