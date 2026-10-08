"""Avia appearance, coordinate, collision and portable-material regression tests."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
NS = {'c': 'http://www.collada.org/2005/11/COLLADASchema'}


@pytest.fixture(scope='module')
def asset():
    path = ROOT/'meshes/avia/avia.dae'
    root = ET.parse(path)
    report = json.loads((path.parent/'geometry_report.json').read_text())
    points = np.fromstring(root.find(".//c:float_array[@id='avia_positions_array']", NS).text,
                           sep=' ').reshape(-1, 3)
    return path, root, report, points


def test_avia_registered_geometry_and_provenance(asset):
    path, root, report, points = asset
    assert hashlib.sha256(path.read_bytes()).hexdigest() == report['output_sha256']
    assert root.find('c:asset/c:unit', NS).get('meter') == '1'
    assert root.find('c:asset/c:up_axis', NS).text == 'Z_UP'
    assert np.isfinite(points).all()
    assert np.allclose([points.min(0), points.max(0)], report['bounds_m'], atol=1e-8)
    assert np.allclose(np.ptp(points, axis=0), [.091, .07555, .0648], atol=1e-6)
    assert report['schema_version'] == 1
    assert report['material_count'] == 3
    assert len(root.findall('.//c:geometry', NS)) == 1  # No metre-scale FOV helper.
    assert sum(int(t.get('count')) for t in root.findall('.//c:triangles', NS)) == 193139


def test_avia_lightweight_collision_covers_mesh(asset, monkeypatch):
    import xacro
    import xacro.substitution_args
    points = asset[3]
    monkeypatch.setattr(xacro.substitution_args, '_eval_find', lambda name: str(ROOT))
    robot = ET.fromstring(xacro.process_file(str(ROOT/'urdf/demo.urdf.xacro'),
        mappings={'model': 'avia', 'name': 'avia'}).toxml())
    covered = np.zeros(len(points), dtype=bool)
    for collision in robot.findall('.//collision'):
        origin = np.fromstring(collision.find('origin').get('xyz'), sep=' ')
        size = np.fromstring(collision.find('geometry/box').get('size'), sep=' ')
        covered |= (np.abs(points-origin) <= size/2 + 1e-7).all(axis=1)
    assert covered.all()
    cfg = yaml.safe_load((ROOT/'config/models/avia.yaml').read_text())
    assert cfg['imu_extrinsics_status'] == 'uncalibrated_approximation'
    assert robot.find("link[@name='avia_lidar']/visual/geometry/mesh") is not None
    assert robot.find("link[@name='avia_body']/visual") is None  # RGL self exclusion.


def test_avia_window_front_winding_and_materials(asset):
    _, root, _, points = asset
    window = root.find(".//c:triangles[@material='material_2']", NS)
    faces = np.fromstring(window.find('c:p', NS).text, dtype=int, sep=' ').reshape(-1, 3, 2)[:, :, 0]
    triangle_points = points[faces]
    assert np.allclose(triangle_points[:, :, 0], .04533, atol=1e-7)
    cross = np.cross(triangle_points[:, 1]-triangle_points[:, 0], triangle_points[:, 2]-triangle_points[:, 0])
    assert (cross[:, 0] > 0).all(), 'Optical window must face forward (+X)'
    for diffuse in root.findall('.//c:phong/c:diffuse/c:color', NS):
        rgba = np.fromstring(diffuse.text, sep=' ')
        assert len(rgba) == 4 and rgba[3] == 1
    assert len(root.findall('.//c:material', NS)) == 3
    assert not root.findall('.//c:image', NS)  # No external texture dependency.
    assert not root.findall('.//c:transparent', NS)
