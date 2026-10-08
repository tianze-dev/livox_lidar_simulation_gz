#!/usr/bin/env python3
"""Launch only our demo, validate real messages, then stop our process group."""

import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import time
import traceback
import uuid

import numpy as np
import rclpy
from rclpy.qos import DurabilityPolicy, QoSProfile, qos_profile_sensor_data
from rosgraph_msgs.msg import Clock
from sensor_msgs.msg import Imu, PointCloud2
from sensor_msgs_py import point_cloud2
from tf2_msgs.msg import TFMessage


def stamp_seconds(stamp):
    return stamp.sec + stamp.nanosec * 1e-9


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('run/smoke'))
    parser.add_argument('--reset-kind', choices=('all', 'time_only'), default='all')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    os.environ['GZ_PARTITION'] = 'livox_smoke_' + uuid.uuid4().hex
    os.environ['ROS_LOG_DIR'] = str(args.output.resolve() / 'ros_logs')
    os.environ['GZ_HOMEDIR'] = str(args.output.resolve())
    os.environ.setdefault('ROS_DOMAIN_ID', '117')
    rclpy.init()
    node = rclpy.create_node('livox_smoke_' + uuid.uuid4().hex[:8])
    clouds, imus, clocks, transforms = [], [], [], []
    node.create_subscription(PointCloud2, '/livox/mid360/points', clouds.append, qos_profile_sensor_data)
    node.create_subscription(Imu, '/livox/mid360/imu', imus.append, qos_profile_sensor_data)
    node.create_subscription(Clock, '/clock', clocks.append, qos_profile_sensor_data)
    node.create_subscription(TFMessage, '/tf_static', transforms.append,
                             QoSProfile(depth=10, durability=DurabilityPolicy.TRANSIENT_LOCAL))
    process = None
    report = {'passed': False}
    try:
        with (args.output / 'launch.log').open('w') as log:
            process = subprocess.Popen(
                ['ros2', 'launch', 'livox_lidar_simulation_gz', 'demo.launch.py',
                 'gui:=false', 'rviz:=false'], stdout=log, stderr=subprocess.STDOUT,
                start_new_session=True)
            deadline = time.monotonic() + 40
            while time.monotonic() < deadline and (len(clouds) < 12 or len(imus) < 100 or not clocks):
                rclpy.spin_once(node, timeout_sec=0.1)
                if process.poll() is not None:
                    raise RuntimeError(f'Demo exited early: {process.returncode}')
            assert len(clouds) >= 12, f'Only {len(clouds)} clouds; see launch.log'
            assert len(imus) >= 100 and clocks, 'IMU or clock unavailable'
            cloud = clouds[-1]
            report.update(clouds=len(clouds), imus=len(imus), clocks=len(clocks),
                          lidar_frame=cloud.header.frame_id, imu_frame=imus[-1].header.frame_id,
                          fields=[field.name for field in cloud.fields], point_step=cloud.point_step,
                          points_last_frame=cloud.width)
            assert cloud.header.frame_id == 'mid360_lidar'
            assert imus[-1].header.frame_id == 'mid360_imu'
            assert [field.name for field in cloud.fields] == ['x', 'y', 'z', 'intensity']
            assert cloud.point_step == 16
            assert len(cloud.data) == cloud.row_step * cloud.height
            points = point_cloud2.read_points_numpy(cloud, field_names=('x', 'y', 'z'), skip_nans=False)
            assert 100 < len(points) <= 20000 and np.isfinite(points).all()
            # Near face of front wall: world x=3.9, sensor x=0.
            front = np.abs(points[:, 0] - 3.9) < 0.01
            assert np.count_nonzero(front) > 100, 'Known front wall geometry missing'
            stamps = [stamp_seconds(msg.header.stamp) for msg in clouds]
            steps = np.diff(stamps)
            assert (steps > 0).all()
            assert abs(float(np.median(steps)) - 0.1) < 0.002
            imu_steps = np.diff([stamp_seconds(msg.header.stamp) for msg in imus])
            assert (imu_steps > 0).all()
            assert abs(float(np.median(imu_steps)) - 0.005) < 0.002
            assert abs(imus[-1].linear_acceleration.z - 9.80665) < 0.05
            frames = {transform.child_frame_id: transform
                      for message in transforms for transform in message.transforms}
            assert {'mid360_body', 'mid360_lidar', 'mid360_imu'} <= frames.keys(), 'Missing static TF'
            assert frames['mid360_body'].header.frame_id == 'world'
            assert abs(frames['mid360_body'].transform.translation.z - 1.0) < 1e-6
            assert abs(frames['mid360_lidar'].transform.translation.z - 0.047) < 1e-6
            imu_position = frames['mid360_imu'].transform.translation
            assert np.allclose([imu_position.x, imu_position.y, imu_position.z], [0.011, 0.02329, 0.00288])
            report.update(passed=True, clouds=len(clouds), imus=len(imus), clocks=len(clocks),
                          points_last_frame=len(points), front_wall_points=int(np.count_nonzero(front)),
                          lidar_sim_hz=1 / float(np.median(steps)),
                          imu_sim_hz=1 / float(np.median(imu_steps)),
                          fields=[field.name for field in cloud.fields],
                          imu_acceleration_z=imus[-1].linear_acceleration.z)
            # Reset only this test's uniquely partitioned world.
            reset = subprocess.run(
                ['gz', 'service', '-s', '/world/livox_demo/control',
                 '--reqtype', 'gz.msgs.WorldControl', '--reptype', 'gz.msgs.Boolean',
                 '--timeout', '5000', '--req', 'reset: {' + args.reset_kind + ': true}'],
                capture_output=True, text=True, timeout=8, check=True)
            assert 'true' in reset.stdout, reset.stdout + reset.stderr
            resume = subprocess.run(
                ['gz', 'service', '-s', '/world/livox_demo/control',
                 '--reqtype', 'gz.msgs.WorldControl', '--reptype', 'gz.msgs.Boolean',
                 '--timeout', '5000', '--req', 'pause: false'],
                capture_output=True, text=True, timeout=8, check=True)
            assert 'true' in resume.stdout, resume.stdout + resume.stderr
            count = len(clouds)
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline and len(clouds) < count + 12:
                rclpy.spin_once(node, timeout_sec=0.1)
            if len(clouds) < count + 12:
                scene = subprocess.run(
                    ['gz', 'service', '-s', '/world/livox_demo/scene/info',
                     '--reqtype', 'gz.msgs.Empty', '--reptype', 'gz.msgs.Scene',
                     '--timeout', '3000', '--req', ''],
                    capture_output=True, text=True, timeout=5)
                report['reset_scene_contains_sensor'] = 'mid360' in scene.stdout
                raise AssertionError('No point clouds after reset')
            all_stamps = [stamp_seconds(msg.header.stamp) for msg in clouds]
            assert any(step < 0 for step in np.diff(all_stamps)), 'Reset time rollback not observed'
            assert clouds[-1].width > 100, 'Geometry lost after reset'
            report.update(reset_recovered=True, reset_kind=args.reset_kind, tf_children=sorted(frames))
    except Exception as error:
        report['passed'] = False
        report['clouds_at_failure'] = len(clouds)
        report['clock_at_failure'] = stamp_seconds(clocks[-1].clock) if clocks else None
        report['error'] = repr(error)
        report['traceback'] = traceback.format_exc()
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
    raise SystemExit(main())
