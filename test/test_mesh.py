import hashlib
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

import numpy as np
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
NS = {'c': 'http://www.collada.org/2005/11/COLLADASchema'}


def test_registered_mesh_and_collision_envelope():
    path = ROOT / 'meshes/mid360/mid360.dae'
    report = json.loads((path.parent / 'geometry_report.json').read_text())
    assert hashlib.sha256(path.read_bytes()).hexdigest() == report['output_sha256']
    root = ET.parse(path)
    assert root.find('c:asset/c:unit', NS).get('meter') == '1'
    assert root.find('c:asset/c:up_axis', NS).text == 'Z_UP'
    points = np.concatenate([
        np.fromstring(item.text, sep=' ').reshape(-1, 3)
        for item in root.findall('.//c:source/c:float_array', NS)
        if item.get('id').endswith('positions_array')])
    assert np.isfinite(points).all()
    assert np.allclose(points.min(0), report['bounds_m'][0], atol=1e-8)
    assert np.allclose(points.max(0), report['bounds_m'][1], atol=1e-8)
    # The 73 mm envelope includes the connector; never scale it down to 65 mm.
    assert np.allclose(np.ptp(points, axis=0), [.073, .065, .060], atol=.0005)
    body = ((np.abs(points[:, :2]) <= .0325 + 1e-7).all(axis=1)
            & (points[:, 2] >= -1e-7) & (points[:, 2] <= .0602))
    connector = ((points[:, 0] >= -.0405) & (points[:, 0] <= -.0325)
                 & (np.linalg.norm(points[:, 1:] - [0, .0143], axis=1) <= .0062))
    assert (body | connector).all(), 'Lightweight collision does not cover the visual'
    assert sum(int(item.get('count')) for item in root.findall('.//c:triangles', NS)) == report['exported_triangles']
    assert len(root.findall('c:library_materials/c:material', NS)) == 9
    transform = np.array(report['source_to_mount'])
    assert np.allclose(transform[:3, :3] @ transform[:3, :3].T, np.eye(3), atol=1e-7)
    assert np.linalg.det(transform[:3, :3]) == pytest.approx(1)


def test_official_imu_offset():
    config = yaml.safe_load((ROOT / 'config/models/mid360.yaml').read_text())
    assert config['measurement_z'] == .047
    lidar = np.array([0, 0, config['measurement_z']])
    assert np.allclose(np.array(config['imu_xyz']) - lidar, [.011, .02329, -.04412])


def test_body_winding_faces_outward():
    """A one-sided renderer must see the shell, not its interior back faces."""
    root = ET.parse(ROOT / 'meshes/mid360/mid360.dae')
    body = next(g for g in root.findall('c:library_geometries/c:geometry', NS)
                if g.get('name') == 'MID360_colored')
    positions = next(item for item in body.findall('.//c:source/c:float_array', NS)
                     if item.get('id').endswith('positions_array'))
    vertices = np.fromstring(positions.text, sep=' ').reshape(-1, 3)
    faces = np.concatenate([np.fromstring(t.find('c:p', NS).text, sep=' ', dtype=int)
                            .reshape(-1, 3, 2)[:, :, 0] for t in body.findall('.//c:triangles', NS)])
    parent = list(range(len(faces)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    edge_owner = {}
    for index, (a, b, c) in enumerate(faces):
        for edge in ((a, b), (b, c), (c, a)):
            key = tuple(sorted(edge))
            if key in edge_owner:
                parent[find(index)] = find(edge_owner[key])
            else:
                edge_owner[key] = index
    groups = {}
    for index, face in enumerate(faces):
        groups.setdefault(find(index), []).append(face)
    shell = max(groups.values(), key=len)
    a, b, c = vertices[np.array(shell)].transpose(1, 0, 2)
    volume = np.einsum('ij,ij->i', a, np.cross(b, c)).sum() / 6
    assert len(shell) == 21958
    assert volume > 8e-5, 'Main housing winding is reversed (backface-culling regression)'
    report = json.loads((ROOT / 'meshes/mid360/normal_repair.json').read_text())
    assert report['vertices_unchanged']
    assert report['boundary_edges_before'] == report['boundary_edges_after']
    assert report['flipped_faces'] == 22226


def test_primitive_fallback(monkeypatch):
    import xacro
    import xacro.substitution_args
    monkeypatch.setattr(xacro.substitution_args, '_eval_find', lambda name: str(ROOT))
    root = ET.fromstring(xacro.process_file(str(ROOT / 'urdf/demo.urdf.xacro'),
                         mappings={'visual_mesh': 'primitive'}).toxml())
    assert not root.findall('.//visual/geometry/mesh')
    assert len(root.findall('.//visual')) == 2


def test_rviz_model_topics_are_unique(tmp_path):
    sys.path.insert(0, str(ROOT))
    from livox_lidar_simulation_gz.configuration import load_sensors
    from livox_lidar_simulation_gz.world import prepare_rviz
    sensors = load_sensors(ROOT, ROOT / 'config/demos/dual_mid360.yaml')
    data = yaml.safe_load(prepare_rviz(ROOT, tmp_path, sensors, True).read_text())
    displays = data['Visualization Manager']['Displays']
    models = [item for item in displays if item['Class'].endswith('/RobotModel')]
    assert {item['Description Topic']['Value'] for item in models} == {
        '/robot_a/front/robot_description', '/robot_b/side/robot_description'}
    assert data['Visualization Manager']['Views']['Current']['Distance'] == .18
