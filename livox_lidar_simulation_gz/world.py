"""Build a private demo world with the robot present in the initial world state."""

from pathlib import Path
from copy import deepcopy
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import yaml


def prepare_demo_world(share, robot_description, name):
    return prepare_demo_worlds(share, [(name, robot_description)])


def prepare_demo_worlds(share, robots):
    directory = tempfile.TemporaryDirectory(prefix='livox_gz_demo_')
    try:
        root = Path(directory.name)
        world = ET.parse(Path(share) / 'worlds/demo.sdf')
        world_element = world.getroot().find('world')
        names = {model.get('name') for model in world_element.findall('model')}
        for index, (name, robot_description) in enumerate(robots):
            if name in names:
                raise ValueError(f'Duplicate world model: {name}')
            names.add(name)
            urdf = root / f'robot_{index}.urdf'
            urdf.write_text(robot_description)
            converted = subprocess.run(['gz', 'sdf', '-p', str(urdf)],
                                       check=True, capture_output=True, text=True, timeout=15)
            model = ET.fromstring(converted.stdout).find('model')
            if model is None:
                raise ValueError('URDF conversion did not produce a model')
            model.set('name', name)
            world_element.append(model)
        world_path = root / 'demo.sdf'
        world.write(world_path, encoding='utf-8', xml_declaration=True)
        return directory, world_path
    except Exception:
        directory.cleanup()
        raise


def prepare_rviz(share, directory, sensors):
    config = yaml.safe_load((Path(share) / 'rviz/demo.rviz').read_text())
    displays = config['Visualization Manager']['Displays']
    point_display = next(item for item in displays if item['Class'] == 'rviz_default_plugins/PointCloud2')
    displays.remove(point_display)
    for sensor in sensors:
        display = deepcopy(point_display)
        display['Name'] = sensor['name'] + ' points'
        display['Topic']['Value'] = sensor['points_topic']
        displays.append(display)
    path = Path(directory) / 'demo.rviz'
    path.write_text(yaml.safe_dump(config, sort_keys=False))
    return path
