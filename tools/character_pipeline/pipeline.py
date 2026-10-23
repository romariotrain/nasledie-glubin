"""Local character job intake. Run with work/hunyuan2mini/.venv/Scripts/python.exe."""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BLENDER = Path('C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe')
STAGES = ['references', 'shape', 'cleanup', 'retopology', 'uv_textures',
          'rig_weights', 'animations', 'visual_review', 'export_validation', 'engine_import']


def digest(path):
    with Path(path).open('rb') as stream:
        h = hashlib.sha256()
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            h.update(chunk)
        return h.hexdigest()


def read_spec(path):
    spec = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if spec.get('schema_version') != 1:
        raise ValueError('schema_version must be 1')
    if not re.fullmatch(r'[a-z][a-z0-9_-]{1,63}', spec.get('asset_id', '')):
        raise ValueError('asset_id: use 2-64 lowercase ASCII letters, numbers, _ or -')
    if spec.get('body_type') != 'humanoid':
        raise ValueError('This workflow currently requires an adapted humanoid rig')
    if not 0.1 <= spec.get('height_m', 0) <= 10:
        raise ValueError('height_m must be between 0.1 and 10 metres')
    views = spec.get('views', {})
    if 'front' not in views or set(views) - {'front', 'back', 'left', 'right'}:
        raise ValueError('views requires front; supported keys: front, back, left, right')
    backend = spec.get('shape', {}).get('backend')
    if backend not in ('2mini', '2mv'):
        raise ValueError('shape.backend must be 2mini or 2mv')
    if backend == '2mv' and len(views) < 2:
        raise ValueError('2mv requires at least two views')
    shape = spec['shape']
    if not 1 <= shape.get('steps', 30) <= 100 or not 128 <= shape.get('resolution', 256) <= 512:
        raise ValueError('shape steps must be 1-100, resolution 128-512')
    budget = spec.get('budgets', {})
    if not 100 <= budget.get('triangles_max', 0) <= 1000000:
        raise ValueError('Invalid triangles_max')
    if budget.get('texture_size') not in (512, 1024, 2048, 4096):
        raise ValueError('texture_size must be 512, 1024, 2048 or 4096')
    if budget.get('max_influences') not in (1, 2, 4):
        raise ValueError('max_influences must be 1, 2 or 4')
    clips = spec.get('animations', [])
    if not clips or len({c['name'] for c in clips}) != len(clips):
        raise ValueError('Animations must have unique names and cannot be empty')
    for clip in clips:
        if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,63}', clip['name']):
            raise ValueError('Animation names must be simple ASCII identifiers')
        if not isinstance(clip.get('loop'), bool) or clip.get('duration_s', 0) <= 0:
            raise ValueError('Each animation requires loop and positive duration_s')
        if clip.get('motion') not in ('in_place', 'root_motion') or not clip.get('description'):
            raise ValueError('Each animation requires motion and a description')
    return spec


def write_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)


def prepare(args):
    from PIL import Image
    spec = read_spec(args.spec)
    job = ROOT / 'work' / 'character-jobs' / args.job
    # Resolve and inspect every reference before creating the job.
    refs = []
    for view, filename in spec['views'].items():
        source = (ROOT / filename).resolve()
        with Image.open(source) as im:
            im.load()
            if min(im.size) < 256:
                raise ValueError(f'{view}: reference is smaller than 256 pixels')
            refs.append((view, source, dict(size=list(im.size), mode=im.mode,
                                          sha256=digest(source))))
    job.mkdir(parents=True, exist_ok=False)
    (job / 'inputs').mkdir()
    receipt = {}
    for view, source, meta in refs:
        target = job / 'inputs' / (view + source.suffix.lower())
        shutil.copyfile(source, target)
        if digest(target) != meta['sha256']:
            raise RuntimeError('Input copy hash mismatch')
        receipt[view] = dict(source=str(source), staged=str(target.relative_to(job)), **meta)
    write_new(job / 'spec.json', spec)
    write_new(job / 'inputs.json', receipt)
    write_new(job / 'stages.json', {s: {'status': 'pending', 'evidence': []} for s in STAGES})
    notes = ['Stages remain pending until execution and review produce evidence.']
    if spec['shape']['backend'] == '2mini' and len(refs) > 1:
        notes.append('2mini uses only front for shape; other views guide textures and review.')
    if spec['shape']['backend'] == '2mv':
        notes.append('2mv weights and GPU memory must be checked before generation; mini availability is not sufficient.')
    write_new(job / 'intake.json', dict(spec_sha256=digest(job / 'spec.json'), notes=notes))
    print(json.dumps(dict(job=str(job), notes=notes), ensure_ascii=False, indent=2))


def verify_inputs(job):
    job = Path(job).resolve()
    intake = json.loads((job / 'intake.json').read_text(encoding='utf-8'))
    if digest(job / 'spec.json') != intake['spec_sha256']:
        raise ValueError('Job specification changed; prepare a new job')
    for meta in json.loads((job / 'inputs.json').read_text(encoding='utf-8')).values():
        if digest(job / meta['staged']) != meta['sha256']:
            raise ValueError('Staged reference changed; prepare a new job')
    return job


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('doctor')
    p = sub.add_parser('prepare'); p.add_argument('--spec', required=True, type=Path)
    p.add_argument('--job', required=True)
    p = sub.add_parser('status'); p.add_argument('--job', required=True, type=Path)
    p = sub.add_parser('shape-mini'); p.add_argument('--job', required=True, type=Path)
    p = sub.add_parser('check-export'); p.add_argument('--job', required=True, type=Path)
    p.add_argument('--file', required=True, type=Path); p.add_argument('--report', required=True, type=Path)
    p.add_argument('--blender', type=Path, default=BLENDER)
    args = parser.parse_args()
    if args.command == 'doctor':
        import torch
        mini = ROOT / 'work/hunyuan2mini/models/tencent/Hunyuan3D-2mini/hunyuan3d-dit-v2-mini/model.fp16.safetensors'
        print(json.dumps(dict(python=sys.executable, blender=BLENDER.exists(), mini_weights=mini.exists(),
                              cuda=torch.cuda.is_available(), gpu=torch.cuda.get_device_name() if torch.cuda.is_available() else None,
                              free_disk_gb=round(shutil.disk_usage(ROOT).free / 2**30, 1),
                              scope='intake and export audit automated; production stages executed by the agent'), indent=2))
    elif args.command == 'prepare':
        if not re.fullmatch(r'[a-zA-Z0-9_-]{2,80}', args.job):
            raise ValueError('job must be a simple unique directory name')
        prepare(args)
    elif args.command == 'status':
        job = verify_inputs(args.job)
        print((job / 'stages.json').read_text(encoding='utf-8'))
    elif args.command == 'shape-mini':
        job = verify_inputs(args.job)
        spec = read_spec(job / 'spec.json')
        if spec['shape']['backend'] != '2mini':
            raise ValueError('2mv needs its own installation and verified adapter; no single-view fallback')
        refs = json.loads((job / 'inputs.json').read_text(encoding='utf-8'))
        output = job / 'shape'
        if output.exists():
            raise FileExistsError('Shape attempt already exists; prepare a new job for another attempt')
        subprocess.run([sys.executable, str(ROOT / 'tools/hunyuan/generate_shape.py'),
                        '--image', str(job / refs['front']['staged']), '--output', str(output),
                        '--steps', str(spec['shape'].get('steps', 30)),
                        '--resolution', str(spec['shape'].get('resolution', 256)),
                        '--seed', str(spec['shape'].get('seed', 12345))], check=True)
        mesh = output / 'swordsman_untextured.glb'  # Legacy backend filename; geometry is input-dependent.
        write_new(job / 'shape_stage.json', dict(status='generated_needs_visual_review',
                  artifact=str(mesh.relative_to(job)), sha256=digest(mesh), receipt='shape/receipt.json'))
        print('Shape generated; inspect silhouette before cleanup. See shape_stage.json.')
    else:
        job = verify_inputs(args.job)
        if args.report.exists():
            raise FileExistsError('Choose a new report; previous evidence is preserved')
        subprocess.run([str(args.blender), '--background', '--factory-startup', '--python-exit-code', '1',
                        '--python', str(Path(__file__).with_name('check_export.py')), '--',
                        '--spec', str(job / 'spec.json'), '--file', str(args.file.resolve()),
                        '--report', str(args.report.resolve())], check=True)


if __name__ == '__main__':
    main()
