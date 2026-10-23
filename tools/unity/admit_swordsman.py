"""Verify the sealed local asset and record exact copies into the Unity test."""
import hashlib, json, shutil, argparse
from pathlib import Path
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[2]
parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,default=ROOT/'art/characters/swordsman/hunyuan_combat_v006')
parser.add_argument('--replace-current',action='store_true');args=parser.parse_args()
SOURCE=args.source.resolve();VERSION=SOURCE.name.rsplit('_',1)[-1]
TARGET = ROOT / 'unity/SwordsmanCombatTest/Assets/SwordsmanTest/Art'
TARGET.mkdir(parents=True, exist_ok=True)
manifest = json.loads((SOURCE / 'package_manifest.json').read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


for filename, meta in manifest['files'].items():
    assert sha(SOURCE / filename) == meta['sha256'], f'Changed source: {filename}'
receipt = dict(source_package=str(SOURCE.relative_to(ROOT)),
               package_manifest_sha256=sha(SOURCE / 'package_manifest.json'),
               purpose='User-authorized local Unity combat prototype; no model weights or generator code admitted',
               copied={}, derived={})
previous_path=TARGET/'admission_receipt.json'
previous=json.loads(previous_path.read_text(encoding='utf-8')) if previous_path.exists() else {}
files = [f'SK_Swordsman_Combat_{VERSION}.fbx', 'swordsman_basecolor_2048.png',
         'swordsman_normal_2048.png', 'swordsman_roughness_2048.png', 'combat_events.json', 'spec.json']
for filename in files:
    target = TARGET / filename
    if target.exists() and sha(target) != sha(SOURCE / filename):
        if not args.replace_current or previous.get('copied',{}).get(filename)!=sha(target):
            raise FileExistsError(f'Existing unverified different file: {target}')
        backup=ROOT/'work/unity-test/admission-backups'/Path(previous['source_package']).name
        backup.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(target,backup/filename)
    shutil.copyfile(SOURCE / filename, target)
    assert sha(target) == manifest['files'][filename]['sha256']
    receipt['copied'][filename] = sha(target)
with Image.open(SOURCE / 'swordsman_roughness_2048.png') as rough:
    alpha = ImageOps.invert(rough.convert('L'))
    image = Image.new('RGBA', rough.size, (0, 0, 0, 255)); image.putalpha(alpha)
    destination = TARGET / 'body_metallic_smoothness.png'
    image.save(destination)
receipt['derived'][destination.name] = dict(sha256=sha(destination),
    source_sha256=sha(SOURCE / 'swordsman_roughness_2048.png'),
    operation='RGB=0 (nonmetal body), A=255-roughness; imported as linear data')
(TARGET / 'admission_receipt.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
print('UNITY_ASSET_ADMITTED', len(files), 'verified source files, one derived map')
