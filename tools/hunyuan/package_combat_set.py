"""Seal this combat iteration only after bound technical receipts pass."""
import hashlib, json, struct, argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser();p.add_argument('--folder',type=Path,default=ROOT/'art/characters/swordsman/hunyuan_combat_v006')
OUT=p.parse_args().folder.resolve();VERSION=OUT.name.rsplit('_',1)[-1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(name):
    return json.loads((OUT / name).read_text(encoding='utf-8'))


source = OUT / f'swordsman_combat_{VERSION}.blend'
spec = read('spec.json'); expected = {c['name'] for c in spec['animations']}
assert len(expected) == 9
for extension in ('glb', 'fbx'):
    audit = read(f'validation/release_{extension}.json')
    artifact = OUT / f'SK_Swordsman_Combat_{VERSION}.{extension}'
    assert audit['technical_pass'] and not audit['errors']
    assert audit['sha256'] == sha(artifact), 'Export changed since validation'
    assert audit['spec_sha256'] == sha(OUT / 'spec.json'), 'Spec changed since validation'
    assert {c['name'] for c in audit['clips']} == expected
    assert audit['triangles'] <= spec['budgets']['triangles_max']
roundtrip = read('roundtrip_validation.json')
assert roundtrip['source_sha256'] == sha(source)
for report in roundtrip['exports']:
    assert not report['errors'] and report['sha256'] == sha(OUT / report['file'])
audit = read('source_validation.json')
assert audit['source_sha256'] == sha(source) and not audit['errors']
assert set(audit['clips']) == expected
assert not any(c['coat_leg_penetrations'] for c in audit['clips'].values())
glb = (OUT / f'SK_Swordsman_Combat_{VERSION}.glb').read_bytes()
length, chunk_type = struct.unpack_from('<II', glb, 12)
assert chunk_type == 0x4E4F534A
document = json.loads(glb[20:20+length])
assert {a['name'] for a in document['animations']} == expected
review = dict(source_sha256=sha(source), method='Visual inspection of final labeled key-pose contact sheet',
              reviewed_images=[r['file'] for r in read('keyframes.json')],
              contact_sheet_sha256=sha(OUT / 'pose_contact_sheet.jpg'),
              findings=['Distinct diagonal/reverse-horizontal/heavy-overhead poses',
                        'Low dodge without roll; thrust aligned forward',
                        'Run leg alternation and backward death pose visible'],
              limits=['Key-pose review, not a live engine playtest',
                      'Motion feel, hitstop and cancellation rules require controller testing',
                      'Sampled cloth test does not prove every possible surface pair is collision-free'])
with (OUT / 'visual_review.json').open('x', encoding='utf-8') as stream:
    json.dump(review, stream, indent=2)
files = [source, OUT/f'SK_Swordsman_Combat_{VERSION}.glb', OUT/f'SK_Swordsman_Combat_{VERSION}.fbx',
         OUT/'README.md', OUT/'spec.json', OUT/'combat_events.json', OUT/'build_receipt.json',
         OUT/'cloth_correction.json', OUT/'key_reduction.json', OUT/'source_validation.json',
         OUT/'roundtrip_validation.json', OUT/'visual_review.json', OUT/'pose_contact_sheet.jpg',
         OUT/'combo_preview.gif', OUT/'animation_set_preview.gif',
         OUT/'validation/release_glb.json', OUT/'validation/release_fbx.json']
files.extend(sorted(OUT.glob('swordsman_*_2048.png')))
files.extend(OUT/f'{name}.gif' for name in sorted(expected))
build_receipt=read('build_receipt.json')
manifest = dict(asset_id=spec['asset_id'], status='blender_and_export_validated_engine_pending',
                provenance=dict(source=build_receipt.get('source','Existing local project swordsman'),
                                method=build_receipt.get('method','Locally authored combat animation'),
                                provider_generation=False),
                files={str(f.relative_to(OUT)): dict(bytes=f.stat().st_size, sha256=sha(f)) for f in files},
                scripts={str(f.relative_to(ROOT)): sha(f) for f in [
                    ROOT/'tools/blender/build_swordsman_combat.py', ROOT/'tools/blender/fix_combat_cloth.py',
                    ROOT/'tools/blender/export_combat_swordsman.py', ROOT/'tools/blender/validate_combat_source.py',
                    ROOT/'tools/blender/validate_combat_roundtrip.py']},
                engine_validation='not_run')
if VERSION=='v008':
    script=ROOT/'tools/blender/graphic_swordsman_v008.py'
    manifest['scripts'][str(script.relative_to(ROOT))]=sha(script)
if VERSION=='v009':
    script=ROOT/'tools/blender/lower_free_arm_v009.py'
    manifest['scripts'][str(script.relative_to(ROOT))]=sha(script)
if VERSION=='v010':
    script=ROOT/'tools/blender/lengthen_run_v010.py'
    manifest['scripts'][str(script.relative_to(ROOT))]=sha(script)
with (OUT / 'package_manifest.json').open('x', encoding='utf-8') as stream:
    json.dump(manifest, stream, indent=2)
print('PACKAGE_CHECKED', len(files), 'files; nine clips; engine pending')
