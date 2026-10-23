"""Boundary checks for job identity and invalid requests; no generation required."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
import pipeline

TEST_ROOT = pipeline.ROOT / 'work' / 'character-pipeline-tests'
TEST_ROOT.mkdir(parents=True, exist_ok=True)


class JobBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.spec = json.loads(Path(__file__).with_name('swordsman.example.json').read_text(encoding='utf-8'))

    def check_spec(self, spec):
        with tempfile.TemporaryDirectory(dir=TEST_ROOT) as folder:
            path = Path(folder) / 'spec.json'
            path.write_text(json.dumps(spec), encoding='utf-8')
            return pipeline.read_spec(path)

    def test_multiview_cannot_accept_one_view(self):
        self.spec['shape']['backend'] = '2mv'
        del self.spec['views']['back']
        with self.assertRaisesRegex(ValueError, 'at least two views'):
            self.check_spec(self.spec)

    def test_duplicate_animation_rejected(self):
        self.spec['animations'].append(copy.deepcopy(self.spec['animations'][0]))
        with self.assertRaisesRegex(ValueError, 'unique'):
            self.check_spec(self.spec)

    def test_changed_inputs_and_spec_invalidate_job(self):
        with tempfile.TemporaryDirectory(dir=TEST_ROOT) as folder:
            job = Path(folder)
            spec = job / 'spec.json'; spec.write_text('{}', encoding='utf-8')
            art = job / 'front.png'; art.write_bytes(b'original input')
            pipeline.write_new(job / 'intake.json', {'spec_sha256': pipeline.digest(spec)})
            pipeline.write_new(job / 'inputs.json', {'front': {'staged': art.name, 'sha256': pipeline.digest(art)}})
            self.assertEqual(pipeline.verify_inputs(job), job.resolve())
            art.write_bytes(b'changed input')
            with self.assertRaisesRegex(ValueError, 'reference changed'):
                pipeline.verify_inputs(job)
            art.write_bytes(b'original input')
            spec.write_text('{"changed": true}', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'specification changed'):
                pipeline.verify_inputs(job)


if __name__ == '__main__':
    unittest.main()
