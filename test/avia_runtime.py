#!/usr/bin/env python3
"""Avia range, empty-cloud and ordinary-object occlusion regression on real RGL."""
import argparse
from collections import deque
import json
import os
from pathlib import Path
import signal
import subprocess
import threading
import uuid
import xml.etree.ElementTree as ET

import numpy as np
import xacro
from ament_index_python.packages import get_package_share_directory
from gz.transport13 import Node
from gz.msgs10.pointcloud_packed_pb2 import PointCloudPacked
from livox_lidar_simulation_gz.configuration import load_model
from livox_lidar_simulation_gz.world import prepare_demo_world


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('run/avia_specification'))
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    os.environ['GZ_PARTITION'] = 'avia_spec_' + uuid.uuid4().hex
    os.environ['GZ_HOMEDIR'] = str(output)
    share = Path(get_package_share_directory('livox_lidar_simulation_gz'))
    cfg = load_model(share, 'avia')
    origin = np.array(cfg['measurement_xyz'])
    description = xacro.process_file(str(share/'urdf/demo.urdf.xacro'),
        mappings={'model':'avia', 'name':'avia', 'xyz':'0 0 0',
                  'points_topic':'/spec/cloud', 'imu_topic':'/spec/imu'}).toxml()
    directory, path = prepare_demo_world(share, description, 'avia')
    tree = ET.parse(path)
    world = tree.getroot().find('world')
    world.set('name', 'avia_spec')
    for model in list(world.findall('model')):
        if model.get('name') != 'avia':
            world.remove(model)

    def box(name, xyz, size, retro):
        model = ET.SubElement(world, 'model', name=name)
        ET.SubElement(model, 'static').text = 'true'
        ET.SubElement(model, 'pose').text = ' '.join(map(str, xyz))+' 0 0 0'
        link = ET.SubElement(model, 'link', name='body')
        visual = ET.SubElement(link, 'visual', name='visual')
        ET.SubElement(ET.SubElement(ET.SubElement(visual, 'geometry'), 'box'), 'size').text = size
        ET.SubElement(visual, 'laser_retro').text = str(retro)

    box('wall', origin+[10.01,0,0], '.02 800 800', 80)
    box('occluder', origin+[1000,0,0], '.02 .8 .8', 40)
    tree.write(path)
    transport = Node()
    messages = deque(maxlen=200)
    condition = threading.Condition()
    received = 0

    def receive(msg):
        nonlocal received
        with condition:
            messages.append(msg)
            received += 1
            condition.notify_all()
    assert transport.subscribe(PointCloudPacked, '/spec/cloud', receive)
    process = None
    result = dict(passed=False)

    def sample(frames=6):
        with condition:
            target = received + frames
            assert condition.wait_for(lambda: received >= target, timeout=30), 'No point-cloud messages'
            msg = messages[-1]
        assert msg.point_step == 16 and len(msg.data) == msg.width*16
        points = np.frombuffer(msg.data, dtype='<f4').reshape(-1,4)
        assert np.isfinite(points).all()
        return points

    def move(name, relative):
        xyz = origin + relative
        request = f'name: "{name}" position: {{x: {xyz[0]} y: {xyz[1]} z: {xyz[2]}}}'
        response = subprocess.run(['gz','service','-s','/world/avia_spec/set_pose',
            '--reqtype','gz.msgs.Pose','--reptype','gz.msgs.Boolean','--timeout','5000','--req',request],
            capture_output=True, text=True, check=True, timeout=8)
        assert 'true' in response.stdout

    try:
        with (output/'gazebo.log').open('w') as log:
            process = subprocess.Popen(['gz','sim','-s','-r','-v','3',str(path)],
                stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            points = sample(12)
            assert len(points) == 24000
            assert np.max(np.abs(points[:,0]-10)) < .001
            azimuth = np.degrees(np.arctan2(points[:,1],points[:,0]))
            elevation = np.degrees(np.arctan2(points[:,2],np.hypot(points[:,0],points[:,1])))
            assert np.max(np.abs(azimuth)) < 35.4 and np.max(np.abs(elevation)) < 38.7
            result['ten_meter_wall_max_error_m'] = float(np.max(np.abs(points[:,0]-10)))
            move('wall',[.51,0,0])
            assert len(sample()) == 0, 'Sub-meter geometry must be rejected by conservative cutoff'
            move('wall',[1.06,0,0])
            points = sample()
            assert len(points) == 24000 and np.linalg.norm(points[:,:3],axis=1).min() >= 1
            move('wall',[200.01,0,0])
            assert len(sample()) == 0, 'Out-of-range geometry must return empty clouds'
            move('wall',[180.01,0,0])
            points = sample()
            assert len(points) > 100 and np.linalg.norm(points[:,:3],axis=1).max() <= 190.001
            move('wall',[10.01,0,0])
            move('occluder',[2.01,0,0])
            points = sample()
            blocked = np.abs(points[:,0]-2) < .001
            background = np.abs(points[:,0]-10) < .001
            assert blocked.sum() > 100 and background.sum() > 100
            center = (np.abs(points[:,1]/points[:,0]) < .19) & (np.abs(points[:,2]/points[:,0]) < .19)
            assert center.sum() > 100 and np.all(blocked[center]), 'Rays passed through occluder'
            result.update(passed=True, range_min=cfg['range_min'], range_max=cfg['range_max'],
                empty_clouds_valid=True, field_of_view_valid=True,
                ordinary_object_occlusion=True, occluder_hits=int(blocked.sum()),
                background_hits=int(background.sum()))
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


if __name__ == '__main__':
    if not __debug__:
        raise SystemExit('Validation requires assertions enabled')
    main()
