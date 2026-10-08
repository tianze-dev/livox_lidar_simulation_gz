import importlib.util
import io
import json
from pathlib import Path
import sys
import subprocess
import xml.etree.ElementTree as ET

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from livox_lidar_simulation_gz.configuration import boolean, load_model, sensor_topics

spec = importlib.util.spec_from_file_location('fetch_dependencies', ROOT / 'scripts/fetch_dependencies.py')
fetch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch)


def test_model_contract():
    model = load_model(ROOT, 'mid360')
    assert model['rays_per_frame'] * model['lidar_rate'] == 200000
    assert model['geometry_status'] == 'simplified_approximation'
    assert model['pattern_groups'] == 40


@pytest.mark.parametrize('model', ['avia', '../mid360', '', 'MID360'])
def test_unknown_model_is_rejected(model):
    with pytest.raises(ValueError):
        load_model(ROOT, model)


def test_independent_topics():
    assert sensor_topics('/robot/a/', 'front') == ('/robot/a/front/points', '/robot/a/front/imu')
    assert sensor_topics('', 'rear') == ('/rear/points', '/rear/imu')
    assert sensor_topics('robot/a', 'front') != sensor_topics('robot/b', 'front')


@pytest.mark.parametrize('namespace,name', [('a b', 'front'), ('valid', '../x'), ('valid', '1'), ('a//b', 'front')])
def test_invalid_names(namespace, name):
    with pytest.raises(ValueError):
        sensor_topics(namespace, name)


def test_boolean():
    assert boolean('true') and not boolean('false')
    with pytest.raises(ValueError):
        boolean('maybe')


def test_no_excluded_dependencies():
    package = ET.parse(ROOT / 'package.xml')
    dependencies = [item.text for item in package.getroot() if 'depend' in item.tag]
    assert not set(dependencies) & {'livox_ros_driver2', 'fast_livo', 'px4_msgs'}
    for folder in ('launch', 'cmake', 'urdf', 'livox_lidar_simulation_gz'):
        for path in (ROOT / folder).rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts:
                text = path.read_text()
                assert '/home/tianze' not in text
                assert 'sentry_simulation' not in text
                assert 'scut-uav' not in text


def test_cache_path_cannot_escape(tmp_path):
    with pytest.raises(ValueError):
        fetch.safe_path(tmp_path, '../escape')


def test_hash_mismatch_preserves_previous_file(tmp_path):
    target = tmp_path / 'artifact'
    target.write_bytes(b'previous')
    with pytest.raises(ValueError):
        fetch.atomic_copy(io.BytesIO(b'corrupt'), target, '0' * 64)
    assert target.read_bytes() == b'previous'
    assert list(tmp_path.iterdir()) == [target]


def test_offline_missing_file_fails(tmp_path):
    lock = json.loads((ROOT / 'dependencies/lock.json').read_text())
    with pytest.raises(RuntimeError, match='offline'):
        fetch.prepare(tmp_path, lock, offline=True)


def test_xacro_mount_and_sensor_contract(monkeypatch):
    import xacro
    import xacro.substitution_args
    monkeypatch.setattr(xacro.substitution_args, '_eval_find', lambda name: str(ROOT))
    xml = xacro.process_file(str(ROOT / 'urdf/demo.urdf.xacro'), mappings={'name': 'front'}).toxml()
    robot = ET.fromstring(xml)
    assert robot.find("link[@name='front_lidar']") is not None
    sensor = robot.find("gazebo[@reference='front_lidar']/sensor")
    assert sensor.get('type') == 'custom'
    assert sensor.find('plugin/frame').text == 'front_lidar'
    assert sensor.find('plugin/pattern_preset').text == 'Livox Mid360'
    assert len(robot.findall('.//collision')) == 1
    assert not robot.findall("link[@name='front_body']/visual")
    assert len(robot.findall("link[@name='front_lidar']/visual")) == 2
    assert sum(float(item.get('value')) for item in robot.findall('.//inertial/mass')) == pytest.approx(0.265)
    assert robot.find("gazebo[@reference='front_imu']/sensor/gz_frame_id").text == 'front_imu'


def test_world_and_xml_are_parseable():
    root = ET.parse(ROOT / 'worlds/demo.sdf').getroot()
    plugins = root.findall('world/plugin')
    assert len([p for p in plugins if p.get('name') == 'rgl::RGLServerPluginManager']) == 1
    assert root.find('world').get('name') == 'livox_demo'


def test_sdf_conversion_preserves_sensors(monkeypatch, tmp_path):
    import xacro
    import xacro.substitution_args
    monkeypatch.setattr(xacro.substitution_args, '_eval_find', lambda name: str(ROOT))
    xml = xacro.process_file(str(ROOT / 'urdf/demo.urdf.xacro')).toxml()
    path = tmp_path / 'robot.urdf'
    path.write_text(xml)
    result = subprocess.run(['gz', 'sdf', '-p', str(path)], text=True, capture_output=True,
                            check=True, timeout=15)
    sdf = ET.fromstring(result.stdout)
    assert sdf.find(".//link[@name='mid360_lidar']/sensor/plugin/frame").text == 'mid360_lidar'
    assert sdf.find(".//link[@name='mid360_imu']/sensor").get('type') == 'imu'


def test_demo_world_contains_initial_robot(monkeypatch):
    import xacro
    import xacro.substitution_args
    from livox_lidar_simulation_gz.world import prepare_demo_world
    monkeypatch.setattr(xacro.substitution_args, '_eval_find', lambda name: str(ROOT))
    xml = xacro.process_file(str(ROOT / 'urdf/demo.urdf.xacro')).toxml()
    directory, path = prepare_demo_world(ROOT, xml, 'mid360')
    try:
        assert ET.parse(path).find("world/model[@name='mid360']") is not None
    finally:
        directory.cleanup()
    assert not path.exists()
