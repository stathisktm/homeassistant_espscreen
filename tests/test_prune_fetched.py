"""ESPHome's clones of this repository in the app's data (esphome/external_components, esphome/packages) are pruned
before a build: one per `ref:`, never removed by ESPHome, they grew the app's data by gigabytes."""
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'screen_manager/app'))
from firmware import Firmware  # noqa: E402

DAY = 86400


class PruneFetched(unittest.TestCase):
    def clone(self, root, name, age_days, now):
        path = root / name
        (path / '.git').mkdir(parents=True)
        (path / '.git' / 'FETCH_HEAD').write_text('x')
        (root / (name + '.lock')).write_text('')
        stamp = now - age_days * DAY
        for target in (path / '.git' / 'FETCH_HEAD', path / '.git', path):
            os.utime(target, (stamp, stamp))
        return path

    def test_old_clones_beyond_the_newest_go(self):
        now = time.time()
        with tempfile.TemporaryDirectory() as tmp:
            firmware = Firmware(tmp, tmp)
            root = Path(tmp) / 'esphome' / 'packages'
            fresh = [self.clone(root, f'fresh{i}', i, now) for i in range(3)]
            old = [self.clone(root, f'old{i}', 30 + i, now) for i in range(10)]
            removed = firmware.prune_fetched(now)
            kept = {p.name for p in root.iterdir() if p.is_dir()}
            # the three fresh ones and the five newest old ones make the eight that always stay
            self.assertEqual(kept, {p.name for p in fresh} | {f'old{i}' for i in range(5)})
            self.assertEqual(len(removed), 5)
            self.assertFalse((root / 'old9.lock').exists())
            self.assertTrue((root / 'old0.lock').exists())

    def test_recent_clones_stay_however_many(self):
        now = time.time()
        with tempfile.TemporaryDirectory() as tmp:
            firmware = Firmware(tmp, tmp)
            root = Path(tmp) / 'esphome' / 'external_components'
            for i in range(12):
                self.clone(root, f'c{i}', i, now)
            self.assertEqual(firmware.prune_fetched(now), [])
            self.assertEqual(len([p for p in root.iterdir() if p.is_dir()]), 12)

    def test_no_folders_is_fine(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(Firmware(tmp, tmp).prune_fetched(), [])


if __name__ == '__main__':
    unittest.main()
