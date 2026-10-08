from pathlib import Path
import sys
import xml.etree.ElementTree as ET

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from livox_lidar_simulation_gz.configuration import load_sensors, vector3
from livox_lidar_simulation_gz.world import prepare_demo_worlds, prepare_rviz


def test_dual_configuration():
    sensors = load_sensors(ROOT, ROOT / 'config/demos/dual_mid360.yaml')
    assert [item['name'] for item in sensors] == ['front', 'side']
    assert sensors[0]['points_topic'] == '/robot_a/front/points'
    assert sensors[1]['points_topic'] == '/robot_b/side/points'
    assert sensors[1]['xyz'] == '1.0 0.0 1.0'


@pytest.mark.parametrize('value', ['0 0', '0 0 nan', [0, float('inf'), 0], [0, True, 1], None])
def test_reject_invalid_pose(value):
    with pytest.raises(ValueError):
        vector3(value, 'pose')


@pytest.mark.parametrize('data', [
    {'sensors': []}, {'sensors': 'front'}, {'other': []},
    {'sensors': [{'name': 'x'}, {'name': 'x', 'namespace': 'another'}]},
    {'sensors': [{'name': 'x', 'rate_typo': 10}]},
    {'sensors': [{'name': 1}]}, {'sensors': [{'model': 'hap'}]},
])
def test_reject_invalid_instance_file(tmp_path, data):
    path = tmp_path / 'sensors.yaml'
    path.write_text(yaml.safe_dump(data))
    with pytest.raises(ValueError):
        load_sensors(ROOT, path)


def test_rviz_has_independent_topics(tmp_path):
    sensors = load_sensors(ROOT, ROOT / 'config/demos/dual_mid360.yaml')
    path = prepare_rviz(ROOT, tmp_path, sensors)
    displays = yaml.safe_load(path.read_text())['Visualization Manager']['Displays']
    clouds = [item for item in displays if item['Class'].endswith('/PointCloud2')]
    assert [item['Topic']['Value'] for item in clouds] == [s['points_topic'] for s in sensors]


def test_world_has_both_sensors(monkeypatch):
    import xacro
    import xacro.substitution_args
    monkeypatch.setattr(xacro.substitution_args, '_eval_find', lambda name: str(ROOT))
    sensors = load_sensors(ROOT, ROOT / 'config/demos/dual_mid360.yaml')
    robots = [(item['name'], xacro.process_file(str(ROOT / 'urdf/demo.urdf.xacro'),
               mappings={key: value for key, value in item.items() if key != 'namespace'}).toxml())
              for item in sensors]
    directory, path = prepare_demo_worlds(ROOT, robots)
    try:
        world = ET.parse(path)
        for name, _ in robots:
            assert world.find(f"world/model[@name='{name}']//sensor/plugin/frame").text == name + '_lidar'
    finally:
        directory.cleanup()
    with pytest.raises(ValueError, match='Duplicate world model'):
        prepare_demo_worlds(ROOT, [('floor', robots[0][1])])
