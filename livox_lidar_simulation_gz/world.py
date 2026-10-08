"""Build a private demo world with the robot present in the initial world state."""

from pathlib import Path
import subprocess
import tempfile
import xml.etree.ElementTree as ET


def prepare_demo_world(share, robot_description, name):
    directory = tempfile.TemporaryDirectory(prefix='livox_gz_demo_')
    try:
        root = Path(directory.name)
        urdf = root / 'robot.urdf'
        urdf.write_text(robot_description)
        converted = subprocess.run(['gz', 'sdf', '-p', str(urdf)],
                                   check=True, capture_output=True, text=True, timeout=15)
        model = ET.fromstring(converted.stdout).find('model')
        if model is None:
            raise ValueError('URDF conversion did not produce a model')
        model.set('name', name)
        world = ET.parse(Path(share) / 'worlds/demo.sdf')
        world.getroot().find('world').append(model)
        world_path = root / 'demo.sdf'
        world.write(world_path, encoding='utf-8', xml_declaration=True)
        return directory, world_path
    except Exception:
        directory.cleanup()
        raise
