#!/usr/bin/env python3
"""Build an isolated consumer package and exercise public mount/bridge interfaces."""
import argparse
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import time
import traceback
import uuid
import xml.etree.ElementTree as ET

import numpy as np
import rclpy
from rclpy.qos import DurabilityPolicy, QoSProfile, qos_profile_sensor_data
from rosgraph_msgs.msg import Clock
from sensor_msgs.msg import PointCloud2, Imu
from sensor_msgs_py import point_cloud2
from tf2_msgs.msg import TFMessage
from ament_index_python.packages import get_package_share_directory
from livox_lidar_simulation_gz.configuration import load_model

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'run/robot_integration')
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    os.environ['GZ_PARTITION'] = 'livox_parent_' + uuid.uuid4().hex
    os.environ.setdefault('ROS_DOMAIN_ID', '121')
    os.environ['ROS_LOG_DIR'] = str(output/'ros_logs')
    os.environ['GZ_HOMEDIR'] = str(output)
    processes, logs = [], []
    result = dict(passed=False)
    rclpy.init()
    node = rclpy.create_node('parent_integration_' + uuid.uuid4().hex[:8])
    clouds = {'front': [], 'rear': []}
    imus = {'front': [], 'rear': []}
    transforms, clocks = [], []
    topics = {'front': ('/robot/front/points', '/robot/front/imu'),
              'rear': ('/sensors/avia/cloud', '/sensors/avia/inertial')}
    for name, (points, imu) in topics.items():
        node.create_subscription(PointCloud2, points, clouds[name].append, qos_profile_sensor_data)
        node.create_subscription(Imu, imu, imus[name].append, qos_profile_sensor_data)
    node.create_subscription(Clock, '/clock', clocks.append, qos_profile_sensor_data)
    node.create_subscription(TFMessage, '/tf_static', transforms.append,
        QoSProfile(depth=10, durability=DurabilityPolicy.TRANSIENT_LOCAL))

    def start(name, command):
        stream = (output/(name+'.log')).open('w')
        logs.append(stream)
        processes.append(subprocess.Popen(command, stdout=stream, stderr=subprocess.STDOUT,
                                           start_new_session=True))

    def wait_for(predicate, seconds=40):
        deadline = time.monotonic() + seconds
        while not predicate() and time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=.05)
            assert all(p.poll() is None for p in processes), 'Child process exited; see per-process logs'
        assert predicate(), 'Sensor readiness timeout; inspect Gazebo initialization, topics and bridge logs'

    try:
        with tempfile.TemporaryDirectory(prefix='livox_parent_ws_') as directory:
            workspace = Path(directory)
            source = workspace/'src/livox_test_robot'
            shutil.copytree(ROOT/'test/fixtures/parent_robot', source,
                            ignore=shutil.ignore_patterns('COLCON_IGNORE'))
            with (output/'build.log').open('w') as log:
                subprocess.run(['colcon', 'build', '--packages-select', 'livox_test_robot'],
                    cwd=workspace, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=120)
            share = workspace/'install/livox_test_robot/share/livox_test_robot'
            description = subprocess.check_output(['xacro', str(share/'robot.urdf.xacro')], text=True)
            urdf = workspace/'robot.urdf'
            urdf.write_text(description)
            converted = subprocess.check_output(['gz', 'sdf', '-p', str(urdf)], text=True)
            world = ET.parse(share/'world.sdf')
            robot = ET.fromstring(converted).find('model')
            assert robot is not None
            world.getroot().find('world').append(robot)
            world_path = workspace/'world.sdf'
            world.write(world_path, encoding='utf-8')
            start('gazebo', ['gz', 'sim', '-s', '-r', '-v', '4', str(world_path)])
            start('tf', ['ros2', 'run', 'robot_state_publisher', 'robot_state_publisher',
                         '--ros-args', '-p', 'use_sim_time:=true', '-p', 'robot_description:='+description])
            start('front_bridge', ['ros2', 'launch', 'livox_lidar_simulation_gz', 'sensor.launch.py',
                                  'model:=mid360', 'name:=front', 'namespace:=robot',
                                  'bridge_clock:=true', 'clock_topic:=/world/parent_world/clock'])
            start('rear_bridge', ['ros2', 'launch', 'livox_lidar_simulation_gz', 'sensor.launch.py',
                                 'model:=avia', 'name:=rear', 'namespace:=robot',
                                 'points_topic:=/sensors/avia/cloud', 'imu_topic:=/sensors/avia/inertial'])
            wait_for(lambda: all(len(c) >= 12 for c in clouds.values()) and
                     all(len(i) >= 100 for i in imus.values()) and transforms and clocks)
            frames = {t.child_frame_id: t for message in transforms for t in message.transforms}
            for name, x in [('front', .2), ('rear', .4)]:
                cloud = clouds[name][-1]
                assert cloud.header.frame_id == name+'_lidar'
                assert imus[name][-1].header.frame_id == name+'_imu'
                assert frames[name+'_body'].header.frame_id == 'base_link'
                assert abs(frames[name+'_body'].transform.translation.x-x) < 1e-6
                points = point_cloud2.read_points_numpy(cloud, field_names=('x','y','z'))
                cfg = load_model(get_package_share_directory('livox_lidar_simulation_gz'),
                                 'mid360' if name == 'front' else 'avia')
                assert np.count_nonzero(np.abs(points[:,0]-(3.9-x-cfg['measurement_xyz'][0])) < .01) > 100
                times = [m.header.stamp.sec+m.header.stamp.nanosec*1e-9 for m in clouds[name]]
                assert abs(np.median(np.diff(times))-.1) < .002
            assert len(node.get_publishers_info_by_topic('/clock')) == 1
            before = {name: len(messages) for name, messages in clouds.items()}
            reset = subprocess.run(['gz', 'service', '-s', '/world/parent_world/control',
                '--reqtype', 'gz.msgs.WorldControl', '--reptype', 'gz.msgs.Boolean',
                '--timeout', '5000', '--req', 'reset: {all: true} pause: false'],
                capture_output=True, text=True, check=True, timeout=8)
            assert 'true' in reset.stdout
            wait_for(lambda: all(len(clouds[n]) >= before[n]+12 for n in clouds), 15)
            for name in clouds:
                times = [m.header.stamp.sec+m.header.stamp.nanosec*1e-9 for m in clouds[name]]
                assert any(t < 0 for t in np.diff(times)), 'Clock rollback missing'
                assert clouds[name][-1].width > 100
            # Exercise real GPU graph teardown and creation, not only world reset.
            response = subprocess.run(['gz', 'service', '-s', '/world/parent_world/remove',
                '--reqtype', 'gz.msgs.Entity', '--reptype', 'gz.msgs.Boolean', '--timeout', '5000',
                '--req', 'name: "parent_robot" type: MODEL'],
                capture_output=True, text=True, check=True, timeout=8)
            assert 'true' in response.stdout
            for _ in range(2):
                deadline = time.monotonic() + 1
                while time.monotonic() < deadline:
                    rclpy.spin_once(node, timeout_sec=.05)
                counts = {n: len(v) for n,v in clouds.items()}
                if _ == 0:
                    stopped = counts
            assert counts == stopped, 'Removed robot is still publishing'
            robot_sdf = workspace/'robot.sdf'
            container = ET.Element('sdf', version='1.9')
            container.append(robot)
            ET.ElementTree(container).write(robot_sdf, encoding='utf-8')
            response = subprocess.run(['gz', 'service', '-s', '/world/parent_world/create',
                '--reqtype', 'gz.msgs.EntityFactory', '--reptype', 'gz.msgs.Boolean', '--timeout', '5000',
                '--req', f'sdf_filename: "{robot_sdf}" name: "parent_robot" allow_renaming: false'],
                capture_output=True, text=True, check=True, timeout=8)
            assert 'true' in response.stdout
            wait_for(lambda: all(len(clouds[n]) >= stopped[n]+12 for n in clouds), 20)
            assert all(messages[-1].width > 100 for messages in clouds.values())
            result.update(passed=True, parent_build=True, default_and_custom_topics=True,
                          frames=sorted(frames), reset_recovered=True, remove_respawn_recovered=True)
    except Exception as error:
        result.update(error=str(error), traceback=traceback.format_exc(),
                      clouds={k: len(v) for k,v in clouds.items()},
                      imus={k: len(v) for k,v in imus.items()}, clocks=len(clocks),
                      tf_messages=len(transforms))
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGINT)
                    process.wait(timeout=12)
                except ProcessLookupError:
                    pass
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=5)
        for log in logs:
            log.close()
        node.destroy_node()
        rclpy.shutdown()
    (output/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    if not __debug__:
        raise SystemExit('Validation requires assertions enabled')
    raise SystemExit(main())
