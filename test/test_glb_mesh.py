"""Optional GLB resources retain geometry and do not change the sensor contract."""
import hashlib
import json
from pathlib import Path
import struct
import sys
import xml.etree.ElementTree as ET

import numpy as np
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@pytest.mark.parametrize('model', ['mid360', 'avia'])
def test_glb_asset(model):
    path = ROOT/f'meshes/{model}/{model}.glb'
    data = path.read_bytes()
    report = json.loads((path.parent/'geometry_report.json').read_text())
    info = report['glb']
    assert hashlib.sha256(data).hexdigest() == info['sha256']
    assert len(data) == info['bytes']
    assert struct.unpack_from('<4sII', data) == (b'glTF', 2, len(data))
    json_size, kind = struct.unpack_from('<I4s', data, 12)
    assert kind == b'JSON'
    gltf = json.loads(data[20:20+json_size])
    binary_size, kind = struct.unpack_from('<I4s', data, 20+json_size)
    assert kind == b'BIN\0'
    binary = memoryview(data)[28+json_size:28+json_size+binary_size]
    assert len(gltf['buffers']) == 1 and 'uri' not in gltf['buffers'][0]
    assert not gltf.get('images') and not gltf.get('animations')
    assert len(gltf['materials']) == info['material_count']
    assert all('pbrMetallicRoughness' in m for m in gltf['materials'])
    assert all(m.get('alphaMode', 'OPAQUE') == 'OPAQUE' for m in gltf['materials'])
    # Exported mesh coordinates are already baked; unexpected node transforms would
    # invalidate the explicit Y-up correction and need a new audit.
    assert all(not set(n) & {'matrix', 'rotation', 'translation', 'scale', 'children'}
               for n in gltf['nodes'])
    assert sorted(n['mesh'] for n in gltf['nodes']) == list(range(len(gltf['meshes'])))
    assert sorted(gltf['scenes'][gltf['scene']]['nodes']) == list(range(len(gltf['nodes'])))
    vertices, triangles = [], 0
    for mesh in gltf['meshes']:
        for primitive in mesh['primitives']:
            assert primitive.get('mode', 4) == 4
            triangles += gltf['accessors'][primitive['indices']]['count'] // 3
            accessor = gltf['accessors'][primitive['attributes']['POSITION']]
            view = gltf['bufferViews'][accessor['bufferView']]
            assert accessor['componentType'] == 5126 and accessor['type'] == 'VEC3'
            assert 'sparse' not in accessor and view.get('byteStride', 12) == 12
            offset = view.get('byteOffset', 0) + accessor.get('byteOffset', 0)
            points = np.frombuffer(binary, dtype='<f4', count=accessor['count']*3,
                                   offset=offset).reshape(-1, 3)
            vertices.append(points)
    points = np.concatenate(vertices)
    assert np.isfinite(points).all()
    assert triangles == info['triangles'] == report['exported_triangles']
    # Roll +pi/2 maps GLB (x,y,z) to mounting frame (x,-z,y).
    corrected = points[:, [0, 2, 1]] * [1, -1, 1]
    assert np.allclose([corrected.min(0), corrected.max(0)], report['bounds_m'], atol=1e-7)
    assert np.allclose(info['mesh_rpy'], [np.pi/2, 0, 0])


@pytest.mark.parametrize('model', ['mid360', 'avia'])
def test_glb_demo_keeps_default_and_physics(model, monkeypatch):
    import xacro
    import xacro.substitution_args
    from livox_lidar_simulation_gz.configuration import load_sensors
    monkeypatch.setattr(xacro.substitution_args, '_eval_find', lambda name: str(ROOT))
    sensors = load_sensors(ROOT, ROOT/'config/demos/mixed_glb.yaml')
    item = next(s for s in sensors if s['model'] == model)
    assert item['visual_mesh'] == f'package://livox_lidar_simulation_gz/meshes/{model}/{model}.glb'
    report = json.loads((ROOT/f'meshes/{model}/geometry_report.json').read_text())
    assert np.allclose(np.fromstring(item['mesh_rpy'], sep=' '), report['glb']['mesh_rpy'])
    baseline = dict(model=model, name=model)
    def robot(mappings):
        return ET.fromstring(xacro.process_file(str(ROOT/'urdf/demo.urdf.xacro'),
                                               mappings=mappings).toxml())
    dae = robot(baseline)
    glb = robot({**baseline, 'visual_mesh': item['visual_mesh'], 'mesh_rpy': item['mesh_rpy']})
    assert dae.find('.//mesh').get('filename').endswith(f'{model}.dae')
    assert glb.find('.//mesh').get('filename').endswith(f'{model}.glb')
    # Only the visual mesh and its local rotation may differ.
    for xml in (dae, glb):
        for link in xml.findall('link'):
            for visual in link.findall('visual'):
                link.remove(visual)
        for element in xml.iter():
            if not (element.text or '').strip():
                element.text = None
            element.tail = None
    assert ET.tostring(dae) == ET.tostring(glb)
