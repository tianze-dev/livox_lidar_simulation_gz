#!/usr/bin/env python3
"""Capture front/rear views from actual Gazebo cameras while checking Avia output."""
import argparse
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import threading
import uuid
import xml.etree.ElementTree as ET

import numpy as np
from PIL import Image as PILImage
import xacro
from ament_index_python.packages import get_package_share_directory
from gz.transport13 import Node
from gz.msgs10.image_pb2 import Image
from gz.msgs10.pointcloud_packed_pb2 import PointCloudPacked
from gz.msgs10.imu_pb2 import IMU
from livox_lidar_simulation_gz.world import prepare_demo_world
from livox_lidar_simulation_gz.configuration import load_model


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--format', choices=('dae', 'glb'), default='dae')
    parser.add_argument('--output', type=Path, default=Path('run/avia_visual'))
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    os.environ['GZ_PARTITION'] = 'avia_visual_' + uuid.uuid4().hex
    os.environ['GZ_HOMEDIR'] = str(output)
    share = Path(get_package_share_directory('livox_lidar_simulation_gz'))
    cfg = load_model(share, 'avia')
    mappings = dict(model='avia', name='avia', points_topic='/visual/points', imu_topic='/visual/imu')
    if args.format == 'glb':
        mappings.update(visual_mesh='package://livox_lidar_simulation_gz/meshes/avia/avia.glb',
                        mesh_rpy=f'{math.pi/2} 0 0')
    description = xacro.process_file(str(share/'urdf/demo.urdf.xacro'), mappings=mappings).toxml()
    directory, path = prepare_demo_world(share, description, 'avia')
    tree = ET.parse(path)
    world = tree.getroot().find('world')
    plugin = ET.SubElement(world, 'plugin', filename='gz-sim-sensors-system', name='gz::sim::systems::Sensors')
    ET.SubElement(plugin, 'render_engine').text = 'ogre2'
    images, counts = {}, {'front': 0, 'rear': 0}
    clouds, imus = [], []
    done = threading.Event()
    transport = Node()

    def receive(view, msg):
        images[view] = msg
        counts[view] += 1
        if min(counts.values()) >= 3 and len(clouds) >= 10 and len(imus) >= 100:
            done.set()

    for view, (x, y, z) in {'front': (.22, .20, 1.17), 'rear': (-.22, -.20, 1.17)}.items():
        camera = ET.SubElement(world, 'model', name=view+'_camera')
        ET.SubElement(camera, 'static').text = 'true'
        pitch = math.atan2(z-1.0324, math.hypot(x, y))
        yaw = math.atan2(-y, -x)
        ET.SubElement(camera, 'pose').text = f'{x} {y} {z} 0 {pitch} {yaw}'
        sensor = ET.SubElement(ET.SubElement(camera, 'link', name='camera'), 'sensor',
                               name='camera', type='camera')
        for key, value in [('always_on', 'true'), ('update_rate', '4'), ('topic', '/visual/'+view)]:
            ET.SubElement(sensor, key).text = value
        cam = ET.SubElement(sensor, 'camera')
        ET.SubElement(cam, 'horizontal_fov').text = '.55'
        image = ET.SubElement(cam, 'image')
        for key, value in [('width','1000'), ('height','800'), ('format','R8G8B8')]:
            ET.SubElement(image, key).text = value
        clip = ET.SubElement(cam, 'clip')
        ET.SubElement(clip, 'near').text = '.001'
        ET.SubElement(clip, 'far').text = '20'
        assert transport.subscribe(Image, '/visual/'+view, lambda msg, view=view: receive(view, msg))
    assert transport.subscribe(PointCloudPacked, '/visual/points', clouds.append)
    assert transport.subscribe(IMU, '/visual/imu', imus.append)
    tree.write(path)
    process = None
    result = dict(passed=False, format=args.format)
    try:
        with (output/'gazebo.log').open('w') as log:
            process = subprocess.Popen(['gz','sim','-s','-r','--headless-rendering',str(path)],
                                       stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            assert done.wait(45), 'Missing camera, cloud or IMU output'
            for view, msg in images.items():
                assert len(msg.data) == msg.width*msg.height*3
                pixels = np.frombuffer(msg.data, dtype=np.uint8).reshape(-1, 3)
                assert np.unique(pixels, axis=0).shape[0] > 100, 'Blank camera view'
                PILImage.frombytes('RGB', (msg.width,msg.height), msg.data).save(output/(view+'.png'))
            points = np.frombuffer(clouds[-1].data, dtype='<f4').reshape(-1, 4)
            assert 100 < len(points) <= 24000
            assert np.isfinite(points).all()
            assert np.count_nonzero(np.abs(points[:,0]+cfg['measurement_xyz'][0]-3.9)<.01) > 100
            result.update(passed=True, camera_frames=counts, point_count=len(points),
                          note='Actual renderer captures; pixel checks do not establish PBR equivalence')
    finally:
        if process is not None and process.poll() is None:
            os.killpg(process.pid, signal.SIGINT)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=5)
        directory.cleanup()
        (output/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    if not __debug__:
        raise SystemExit('Validation requires assertions enabled')
    raise SystemExit(main())
