#!/usr/bin/env python3
"""Two GPU sensors: topic/TF isolation, geometry, moving obstacle and world controls."""

import argparse
from collections import deque
import json
import os
from pathlib import Path
import signal
import subprocess
import time
import traceback
import uuid

from ament_index_python.packages import get_package_share_directory
import numpy as np
import rclpy
from rclpy.qos import DurabilityPolicy, QoSProfile, qos_profile_sensor_data
from rosgraph_msgs.msg import Clock
from sensor_msgs.msg import Imu, PointCloud2
from sensor_msgs_py import point_cloud2
from tf2_msgs.msg import TFMessage

from smoke_runtime import stamp_seconds
from livox_lidar_simulation_gz.configuration import load_model, load_sensors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('run/multi'))
    parser.add_argument('--mixed', action='store_true', help='Test MID-360 and Avia together')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    os.environ['GZ_PARTITION'] = 'livox_multi_' + uuid.uuid4().hex
    os.environ['ROS_LOG_DIR'] = str(args.output.resolve() / 'ros_logs')
    os.environ.setdefault('ROS_DOMAIN_ID', '118')
    rclpy.init()
    node = rclpy.create_node('livox_multi_' + uuid.uuid4().hex[:8])
    share = Path(get_package_share_directory('livox_lidar_simulation_gz'))
    profile = share / 'config/demos' / ('mixed.yaml' if args.mixed else 'dual_mid360.yaml')
    sensors = {item['name']: item for item in load_sensors(share, profile)}
    names = {name: item['points_topic'].rsplit('/', 1)[0] for name, item in sensors.items()}
    clouds = {name: deque(maxlen=200) for name in names}
    imus = {name: deque(maxlen=1000) for name in names}
    counts = {name: 0 for name in names}
    transforms, clocks = [], deque(maxlen=2000)

    def receive_cloud(name, msg):
        counts[name] += 1
        clouds[name].append(msg)

    for name, topic in names.items():
        node.create_subscription(PointCloud2, topic + '/points',
                                 lambda msg, name=name: receive_cloud(name, msg), qos_profile_sensor_data)
        node.create_subscription(Imu, topic + '/imu',
                                 lambda msg, name=name: imus[name].append(msg), qos_profile_sensor_data)
    node.create_subscription(Clock, '/clock', lambda msg: clocks.append(msg), qos_profile_sensor_data)
    node.create_subscription(TFMessage, '/tf_static', transforms.append,
                             QoSProfile(depth=10, durability=DurabilityPolicy.TRANSIENT_LOCAL))

    def spin(seconds):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.05)

    def wait_for(predicate, seconds=15):
        deadline = time.monotonic() + seconds
        while not predicate():
            if time.monotonic() >= deadline:
                raise TimeoutError('Runtime condition timed out')
            if process.poll() is not None:
                raise RuntimeError(f'Demo exited: {process.returncode}')
            rclpy.spin_once(node, timeout_sec=0.1)

    def service(suffix, request, request_type='gz.msgs.WorldControl'):
        response = subprocess.run(
            ['gz', 'service', '-s', '/world/livox_demo/' + suffix,
             '--reqtype', request_type, '--reptype', 'gz.msgs.Boolean',
             '--timeout', '5000', '--req', request], capture_output=True, text=True,
            timeout=8, check=True)
        assert 'true' in response.stdout, response.stdout + response.stderr

    def check_wall(world_x):
        hits = {}
        for name in names:
            cloud = clouds[name][-1]
            assert cloud.header.frame_id == name + '_lidar'
            assert imus[name][-1].header.frame_id == name + '_imu'
            assert cloud.point_step == 16 and len(cloud.data) == cloud.row_step * cloud.height
            points = point_cloud2.read_points_numpy(cloud, field_names=('x', 'y', 'z'))
            maximum = load_model(share, sensors[name]['model'])['rays_per_frame']
            assert 100 < len(points) <= maximum and np.isfinite(points).all()
            x = float(sensors[name]['xyz'].split()[0])
            yaw = float(sensors[name]['rpy'].split()[2])
            projected_x = x + np.cos(yaw)*points[:, 0] - np.sin(yaw)*points[:, 1]
            hits[name] = int(np.count_nonzero(np.abs(projected_x - world_x) < 0.01))
            assert hits[name] > 100, f'{name}: missing world wall at {world_x}'
        return hits

    process = None
    report = {'passed': False}
    try:
        with (args.output / 'launch.log').open('w') as log:
            process = subprocess.Popen(
                ['ros2', 'launch', 'livox_lidar_simulation_gz', 'demo.launch.py',
                 'gui:=false', 'rviz:=false',
                 'sensors_file:=' + str(profile)],
                stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            wait_for(lambda: all(counts[name] >= 8 and len(imus[name]) >= 80 for name in names)
                     and bool(clocks), 45)
            report['initial_wall_hits'] = check_wall(3.9)
            frames = {tf.child_frame_id: tf for msg in transforms for tf in msg.transforms}
            for name in names:
                assert {name + suffix for suffix in ('_body', '_lidar', '_imu')} <= frames.keys()
                assert len(node.get_publishers_info_by_topic(names[name] + '/points')) == 1
            assert len(node.get_publishers_info_by_topic('/clock')) == 1, 'Duplicate clock bridge'
            for name, sensor in sensors.items():
                x = float(sensor['xyz'].split()[0])
                yaw = float(sensor['rpy'].split()[2])
                assert abs(frames[name+'_body'].transform.translation.x - x) < 1e-6
                assert abs(frames[name+'_body'].transform.rotation.z - np.sin(yaw/2)) < 1e-6
            report['lidar_sim_hz'] = {}
            report['imu_sim_hz'] = {}
            for name in names:
                dt = np.diff([stamp_seconds(msg.header.stamp) for msg in clouds[name]])
                assert (dt > 0).all() and abs(float(np.median(dt)) - 0.1) < 0.002
                report['lidar_sim_hz'][name] = 1 / float(np.median(dt))
                imu_dt = np.diff([stamp_seconds(msg.header.stamp) for msg in imus[name]])
                assert (imu_dt > 0).all() and abs(float(np.median(imu_dt)) - 0.005) < 0.002
                report['imu_sim_hz'][name] = 1 / float(np.median(imu_dt))

            # Move just the obstacle, leaving both sensor mounts and TF fixed.
            service('set_pose/blocking',
                    'name: "front_wall" position: {x: 5 y: 0 z: 2} orientation: {w: 1}',
                    'gz.msgs.Pose')
            before = counts.copy()
            wait_for(lambda: all(counts[n] >= before[n] + 6 for n in names))
            report['moved_wall_hits'] = check_wall(4.9)

            service('control', 'pause: true')
            spin(0.7)  # Drain messages already in flight before assessing pause.
            paused_counts, paused_time = counts.copy(), stamp_seconds(clocks[-1].clock)
            paused_imu = {name: stamp_seconds(imus[name][-1].header.stamp) for name in names}
            spin(0.5)
            assert counts == paused_counts, 'Clouds published while paused'
            assert stamp_seconds(clocks[-1].clock) == paused_time, 'Clock advanced while paused'
            assert all(stamp_seconds(imus[n][-1].header.stamp) == paused_imu[n] for n in names)
            service('control', 'pause: true multi_step: 300')
            wait_for(lambda: stamp_seconds(clocks[-1].clock) >= paused_time + 0.299)
            spin(0.3)
            assert abs(stamp_seconds(clocks[-1].clock) - paused_time - 0.3) < 0.002
            assert all(counts[n] > paused_counts[n] for n in names)
            report['pause_and_step_passed'] = True
            service('control', 'pause: false')
            before = counts.copy()
            wait_for(lambda: all(counts[n] >= before[n] + 4 for n in names))
            check_wall(4.9)

            service('control', 'reset: {all: true}')
            service('control', 'pause: false')
            before = counts.copy()
            wait_for(lambda: all(counts[n] >= before[n] + 10 for n in names))
            report['reset_wall_hits'] = check_wall(3.9)
            for name in names:
                stamps = [stamp_seconds(msg.header.stamp) for msg in clouds[name]]
                assert any(dt < 0 for dt in np.diff(stamps)), name + ': no clock rollback'
            report.update(passed=True, counts=counts.copy(), tf_children=sorted(frames),
                          reset_recovered=True, clock_publishers=1)
    except Exception as error:
        report.update(error=repr(error), traceback=traceback.format_exc(), counts=counts.copy())
    finally:
        if process is not None:
            try:
                os.killpg(process.pid, signal.SIGINT)
                process.wait(timeout=12)
            except ProcessLookupError:
                pass
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=5)
        node.destroy_node()
        rclpy.shutdown()
        (args.output / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    if not __debug__:
        raise SystemExit('Validation requires assertions enabled; do not use Python -O')
    raise SystemExit(main())
