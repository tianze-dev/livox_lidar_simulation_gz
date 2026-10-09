"""Check the locked non-repetitive Avia preset, not a synthesized scan law."""
import json
import os
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def test_avia_scan_layout_and_field_of_view():
    lock = json.loads((ROOT/'dependencies/lock.json').read_text())
    info = lock['scan_presets']['avia']
    directory = Path(os.environ.get('LIVOX_TEST_PATTERN_DIR',
                                   ROOT/'.deps/rgl/patterns'))
    path = directory/info['pattern_file']
    assert path.is_file(), 'Prepare locked dependencies before running scan tests'
    transforms = np.fromfile(path, dtype='<f4').reshape(-1, 3, 4)
    assert len(transforms) == info['pattern_groups']*info['rays_per_frame'] == 960000
    assert np.isfinite(transforms).all()
    assert np.allclose(transforms[:, :, 3], 0)
    # RGL uses each matrix's local +Z as its ray direction.
    direction = transforms[:, :, 2]
    assert np.allclose(np.linalg.norm(direction, axis=1), 1, atol=1e-6)
    assert np.all(direction[:, 0] > 0), 'Avia rays must point through the front window'
    azimuth = np.degrees(np.arctan2(direction[:, 1], direction[:, 0]))
    elevation = np.degrees(np.arctan2(direction[:, 2], np.hypot(direction[:, 0], direction[:, 1])))
    # Official nominal H=70.4, V=77.2 degrees. The upstream preset spans H~70.62.
    assert abs(float(np.ptp(azimuth))-70.4) < .3
    assert abs(float(np.ptp(elevation))-77.2) < .1
    groups = direction.reshape(40, 24000, 3)
    assert all(not np.array_equal(groups[0], group) for group in groups[1:])
    assert info['rays_per_frame']*10 == 240000
