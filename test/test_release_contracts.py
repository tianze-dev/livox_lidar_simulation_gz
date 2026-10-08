import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from livox_lidar_simulation_gz.configuration import load_model


@pytest.mark.parametrize('model,expected', [('mid360', 20000), ('avia', 24000)])
def test_models_use_declared_patterns(model, expected):
    cfg = load_model(ROOT, model)
    lock = json.loads((ROOT/'dependencies/lock.json').read_text())
    assert cfg['schema_version'] == 1
    assert cfg['rays_per_frame'] == expected
    assert 'patterns/'+cfg['pattern_file'] in {a['path'] for a in lock['artifacts']}


def test_avia_is_not_mid360_appearance(monkeypatch):
    import xacro
    import xacro.substitution_args
    monkeypatch.setattr(xacro.substitution_args, '_eval_find', lambda name: str(ROOT))
    xml = xacro.process_file(str(ROOT/'urdf/demo.urdf.xacro'), mappings={'model':'avia','name':'avia'}).toxml()
    robot = ET.fromstring(xml)
    assert robot.find(".//visual[@name='avia_window']") is not None
    assert robot.find(".//visual[@name='avia_cover_visual']") is None
    assert robot.find('.//mesh') is None
    assert len(robot.findall('.//collision')) == 1
    assert robot.find('.//pattern_preset').text == 'Livox Avia'


def test_moving_fixture_has_real_joints_and_feedback(monkeypatch):
    import xacro
    import xacro.substitution_args
    monkeypatch.setattr(xacro.substitution_args, '_eval_find', lambda name: str(ROOT))
    xml = xacro.process_file(str(ROOT/'urdf/moving.urdf.xacro')).toxml()
    robot = ET.fromstring(xml)
    assert robot.find("joint[@type='prismatic']") is not None
    assert robot.find("joint[@type='continuous']") is not None
    assert len(robot.findall("gazebo/plugin[@name='gz::sim::systems::JointController']")) == 2
    assert robot.find("gazebo/plugin[@name='gz::sim::systems::JointStatePublisher']") is not None
    assert robot.find('gazebo/static') is None
