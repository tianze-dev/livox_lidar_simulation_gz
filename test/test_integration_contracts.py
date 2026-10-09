"""Public mount/bridge contract, strict inputs and documentation examples."""
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET

import pytest
import xacro
import xacro.substitution_args
import yaml

from livox_lidar_simulation_gz.configuration import load_model, sensor_topics

ROOT = Path(__file__).resolve().parents[1]


def mount(monkeypatch, root=ROOT, **attributes):
    monkeypatch.setattr(xacro.substitution_args, '_eval_find', lambda name: str(root))
    element = ET.Element('mount', {k: str(v) for k, v in attributes.items()})
    attrs = ET.tostring(element, encoding='unicode').replace('<mount', '<xacro:livox_lidar')
    doc = xacro.parse('<robot name="parent" xmlns:xacro="http://www.ros.org/wiki/xacro">'
                      '<link name="base_link"/>'
                      '<xacro:include filename="$(find livox_lidar_simulation_gz)/urdf/livox.xacro"/>'
                      + attrs + '</robot>')
    xacro.process_doc(doc)
    return ET.fromstring(doc.toxml())


@pytest.mark.parametrize('model', ['mid360', 'avia'])
@pytest.mark.parametrize('namespace', ['livox', '', '/robot/a/'])
@pytest.mark.parametrize('custom', [False, True])
def test_macro_bridge_topic_parity(monkeypatch, model, namespace, custom):
    options = dict(points_topic='/custom/cloud', imu_topic='/custom/inertial') if custom else {}
    robot = mount(monkeypatch, parent='base_link', name='front', model=model,
                  namespace=namespace, **options)
    expected = sensor_topics(namespace, 'front', **options)
    assert robot.find('.//plugin/topic').text == expected[0]
    assert robot.find(".//sensor[@type='imu']/topic").text == expected[1]
    assert robot.find('.//plugin/frame').text == 'front_lidar'
    pattern = robot.find('.//pattern_preset_path')
    cfg = load_model(ROOT, model)
    assert pattern.get('pattern_count') == str(cfg['pattern_groups'])
    assert pattern.get('rays_per_frame') == str(cfg['rays_per_frame'])
    assert pattern.text.endswith('/' + cfg['pattern_file'])


@pytest.mark.parametrize('topic', ['relative', '/a//b', '/1cloud', '/a b', '/a/', '/a@b'])
def test_invalid_topic_rejected_by_both_paths(monkeypatch, topic):
    with pytest.raises(ValueError):
        sensor_topics('livox', 'front', points_topic=topic)
    with pytest.raises(xacro.XacroException):
        mount(monkeypatch, parent='base_link', points_topic=topic)


@pytest.mark.parametrize('field,value', [
    ('mass', True), ('mass', 1e-7), ('mass', '0.2'), ('mass', float('nan')),
    ('lidar_rate', float('inf')), ('lidar_rate', 0), ('imu_rate', -1),
    ('size_x', -1), ('measurement_xyz', False), ('measurement_xyz', [0, 0, 1]),
    ('range_min', True), ('range_min', -1), ('range_max', float('nan')),
    ('imu_xyz', [0, True, 0]), ('imu_from_lidar_xyz', [0, 0, 0]),
    ('connector_collision', 1), ('pattern_groups', 1.5), ('rays_per_frame', float('nan')),
])
def test_invalid_model_rejected_in_launch_and_direct_xacro(tmp_path, monkeypatch, field, value):
    shutil.copytree(ROOT/'urdf', tmp_path/'urdf')
    shutil.copytree(ROOT/'config', tmp_path/'config')
    shutil.copytree(ROOT/'dependencies', tmp_path/'dependencies')
    path = tmp_path/'config/models/mid360.yaml'
    cfg = yaml.safe_load(path.read_text())
    cfg[field] = value
    path.write_text(yaml.safe_dump(cfg))
    with pytest.raises(ValueError):
        load_model(tmp_path, 'mid360')
    with pytest.raises(xacro.XacroException):
        mount(monkeypatch, tmp_path, parent='base_link')


@pytest.mark.parametrize('value', [True, 0, -1, 1.5, float('nan')])
def test_invalid_locked_layout(tmp_path, monkeypatch, value):
    for folder in ('urdf', 'config', 'dependencies'):
        shutil.copytree(ROOT/folder, tmp_path/folder)
    path = tmp_path/'dependencies/lock.json'
    lock = json.loads(path.read_text())
    lock['scan_presets']['mid360']['pattern_groups'] = value
    path.write_text(json.dumps(lock))
    with pytest.raises(ValueError):
        load_model(tmp_path, 'mid360')
    with pytest.raises(xacro.XacroException):
        mount(monkeypatch, tmp_path, parent='base_link')


def test_bridge_passes_custom_topics(monkeypatch):
    from launch import LaunchContext
    path = ROOT/'launch/sensor.launch.py'
    spec = importlib.util.spec_from_file_location('sensor_launch_contract', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, 'get_package_share_directory', lambda name: str(ROOT))
    monkeypatch.setattr(module, 'Node', lambda **kwargs: kwargs)
    context = LaunchContext()
    context.launch_configurations.update(model='mid360', name='front', namespace='robot',
        points_topic='/custom/cloud', imu_topic='/custom/imu', bridge_clock='false')
    node = module._setup(context)[0]
    assert node['arguments'] == [
        '/custom/cloud@sensor_msgs/msg/PointCloud2[gz.msgs.PointCloudPacked',
        '/custom/imu@sensor_msgs/msg/Imu[gz.msgs.IMU']
    context.launch_configurations.update(bridge_clock='true', clock_topic='/world/robot_world/clock')
    node = module._setup(context)[0]
    assert node['arguments'][-1] == '/world/robot_world/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock'
    assert node['remappings'] == [('/world/robot_world/clock', '/clock')]


def test_pattern_fallback_path_and_namespace_validation(monkeypatch):
    monkeypatch.delenv('RGL_PATTERNS_DIR', raising=False)
    robot = mount(monkeypatch, parent='base_link')
    assert robot.find('.//pattern_preset_path').text == str(ROOT/'patterns/LivoxMid360.mat3x4f')
    with pytest.raises(xacro.XacroException):
        mount(monkeypatch, parent='base_link', namespace='bad//ns',
              points_topic='/explicit/cloud', imu_topic='/explicit/imu')


@pytest.mark.parametrize('name', ['README.md', 'README.en.md'])
def test_readme_examples_and_links(monkeypatch, name):
    text = (ROOT/name).read_text()
    blocks = re.findall(r'```(\w+)\n(.*?)```', text, re.S)
    for language, code in blocks:
        if language == 'bash':
            subprocess.run(['bash', '-n'], input=code, text=True, check=True)
        if language == 'xml' and 'xacro:livox_lidar' in code:
            monkeypatch.setattr(xacro.substitution_args, '_eval_find', lambda name: str(ROOT))
            doc = xacro.parse('<robot name="example" xmlns:xacro="http://www.ros.org/wiki/xacro">'
                              '<link name="base_link"/>' + code + '</robot>')
            xacro.process_doc(doc)
            assert 'front_lidar' in doc.toxml()
        elif language == 'xml':
            ET.fromstring('<world>' + code + '</world>')
    for link in re.findall(r'\]\(([^)]+)\)', text):
        if '://' not in link:
            assert (ROOT/link.split('#')[0]).exists(), link
