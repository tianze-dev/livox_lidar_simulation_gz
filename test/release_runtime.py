#!/usr/bin/env python3
"""Bounded static endurance or moving-fixture validation; no estimator dependencies."""
import argparse
from collections import deque
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import time
import traceback
import uuid

import numpy as np
import rclpy
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Imu, JointState, PointCloud2
from sensor_msgs_py import point_cloud2
from tf2_msgs.msg import TFMessage
from smoke_runtime import stamp_seconds


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', choices=('mid360', 'avia'), default='mid360')
    parser.add_argument('--moving', action='store_true')
    parser.add_argument('--seconds', type=float, default=6)
    parser.add_argument('--output', type=Path, default=Path('run/release_runtime'))
    args = parser.parse_args()
    if not math.isfinite(args.seconds) or not 3 <= args.seconds <= 3600 or (args.moving and args.seconds > 15):
        parser.error('seconds must be 3..3600 (moving fixture: at most 15 to stay within rail limits)')
    args.output.mkdir(parents=True, exist_ok=True)
    os.environ['GZ_PARTITION'] = 'livox_release_' + uuid.uuid4().hex
    os.environ['ROS_LOG_DIR'] = str(args.output.resolve() / 'ros_logs')
    os.environ.setdefault('ROS_DOMAIN_ID', '120')
    rclpy.init()
    node = rclpy.create_node('release_check_' + uuid.uuid4().hex[:8])
    samples, imus, joints, tfs = deque(maxlen=100), deque(maxlen=1000), deque(maxlen=10000), deque(maxlen=10000)
    wall_times, stamps, points_counts, sampled_resources = [], [], [], []
    process = None
    report = {'passed': False, 'model': args.model, 'moving': args.moving, 'duration_wall_s': args.seconds}

    def cloud(msg):
        samples.append(msg)
        wall_times.append(time.monotonic())
        stamps.append(stamp_seconds(msg.header.stamp))
        points_counts.append(msg.width)

    node.create_subscription(PointCloud2, f'/livox/{args.model}/points', cloud, qos_profile_sensor_data)
    node.create_subscription(Imu, f'/livox/{args.model}/imu', lambda msg: imus.append(msg), qos_profile_sensor_data)
    if args.moving:
        node.create_subscription(JointState, f'/fixture/{args.model}/joint_states', lambda msg: joints.append(msg), qos_profile_sensor_data)
        node.create_subscription(TFMessage, '/tf', lambda msg: tfs.extend(msg.transforms), qos_profile_sensor_data)
    try:
        with (args.output / 'launch.log').open('w') as log:
            process = subprocess.Popen(['ros2', 'launch', 'livox_lidar_simulation_gz', 'demo.launch.py',
                'gui:=false', 'rviz:=false', f'model:={args.model}', f'name:={args.model}',
                'moving:=' + str(args.moving).lower()], stdout=log, stderr=subprocess.STDOUT,
                start_new_session=True)
            deadline = time.monotonic() + 45
            while not samples or not imus or (args.moving and (not joints or not tfs)):
                if time.monotonic() > deadline or process.poll() is not None:
                    raise RuntimeError('Sensors/feedback unavailable; see launch.log')
                rclpy.spin_once(node, timeout_sec=.1)
            begin, last_resource = time.monotonic(), 0
            wall_times.clear(); stamps.clear(); points_counts.clear()
            while time.monotonic() - begin < args.seconds:
                rclpy.spin_once(node, timeout_sec=.05)
                if process.poll() is not None:
                    raise RuntimeError('Demo exited during validation')
                if time.monotonic() - last_resource > 5:
                    last_resource = time.monotonic()
                    gpu = subprocess.run(['nvidia-smi', '--query-gpu=utilization.gpu,memory.used',
                        '--format=csv,noheader,nounits'], capture_output=True, text=True, timeout=3)
                    # Process-group RSS excludes unrelated projects, GPU utilisation is whole-device.
                    ps = subprocess.run(['ps', '-eo', 'pgid=,rss=,pcpu='], capture_output=True, text=True, timeout=3)
                    rows = [line.split() for line in ps.stdout.splitlines() if line.split()[0] == str(process.pid)]
                    rss = sum(int(row[1]) for row in rows)
                    cpu = sum(float(row[2]) for row in rows)
                    sampled_resources.append(dict(elapsed=time.monotonic()-begin, rss_kib=rss,
                                                  process_group_lifetime_cpu_pct=cpu, gpu=gpu.stdout.strip()))
            assert len(stamps) >= 10 and np.all(np.diff(stamps) > 0)
            assert abs(float(np.median(np.diff(stamps))) - .1) < .002
            maximum = 20000 if args.model == 'mid360' else 24000
            assert all(100 < count <= maximum for count in points_counts)
            message = samples[-1]
            assert message.header.frame_id == args.model + '_lidar'
            assert message.point_step == 16 and len(message.data) == message.width * 16
            assert [f.name for f in message.fields] == ['x', 'y', 'z', 'intensity']
            points = point_cloud2.read_points_numpy(message, field_names=('x', 'y', 'z'))
            assert np.isfinite(points).all()
            assert imus[-1].header.frame_id == args.model + '_imu'
            imu_steps = np.diff([stamp_seconds(msg.header.stamp) for msg in imus])
            assert abs(float(np.median(imu_steps)) - .005) < .002
            if not args.moving:
                assert np.count_nonzero(np.abs(points[:, 0] - 3.9) < .01) > 100
                assert abs(imus[-1].linear_acceleration.z - 9.80665) < .05
            else:
                joint_times = np.array([stamp_seconds(msg.header.stamp) for msg in joints])
                errors = []
                for msg in list(samples)[-30:]:
                    t = stamp_seconds(msg.header.stamp)
                    if not joint_times[0] <= t <= joint_times[-1]:
                        continue
                    joint = joints[int(np.argmin(np.abs(joint_times-t)))]
                    state = dict(zip(joint.name, joint.position))
                    x, yaw = state[args.model+'_translation'], state[args.model+'_rotation']
                    cloud_points = point_cloud2.read_points_numpy(msg, field_names=('x', 'y', 'z', 'intensity'))
                    surface = cloud_points[np.abs(cloud_points[:, 3]-80) < .01]
                    assert len(surface) > 100
                    world_x = x + math.cos(yaw)*surface[:, 0] - math.sin(yaw)*surface[:, 1]
                    errors.extend(np.abs(world_x-3.9).tolist())
                assert len(errors) > 1000
                p95 = float(np.percentile(errors, 95))
                assert p95 < .01, f'Moving wall residual p95={p95}'
                angular = float(np.median([msg.angular_velocity.z for msg in imus]))
                assert abs(angular-.15) < .02, f'Unexpected IMU gyro: {angular}'
                assert any(tf.child_frame_id == args.model+'_slide' for tf in tfs)
                assert any(tf.child_frame_id == args.model+'_platform' for tf in tfs)
                assert joints[-1].position != joints[0].position
                tf_errors = []
                for tf in list(tfs)[-100:]:
                    t = stamp_seconds(tf.header.stamp)
                    if not joint_times[0] <= t <= joint_times[-1]:
                        continue
                    joint = joints[int(np.argmin(np.abs(joint_times-t)))]
                    state = dict(zip(joint.name, joint.position))
                    if tf.child_frame_id == args.model+'_slide':
                        tf_errors.append(abs(tf.transform.translation.x-state[args.model+'_translation']))
                    elif tf.child_frame_id == args.model+'_platform':
                        yaw = state[args.model+'_rotation']
                        tf_errors.append(abs(tf.transform.rotation.z-math.sin(yaw/2)))
                assert tf_errors and max(tf_errors) < .001, 'Dynamic TF disagrees with joint feedback'
                acceleration = np.median([[msg.linear_acceleration.x, msg.linear_acceleration.y,
                                            msg.linear_acceleration.z] for msg in list(imus)[-200:]], axis=0)
                from ament_index_python.packages import get_package_share_directory
                from livox_lidar_simulation_gz.configuration import load_model
                config = load_model(get_package_share_directory('livox_lidar_simulation_gz'), args.model)
                expected_accel = np.array([-.15**2*config['imu_xyz'][0], -.15**2*config['imu_xyz'][1], 9.80665])
                assert np.max(np.abs(acceleration-expected_accel)) < .03
                report.update(wall_residual_p95_m=p95, imu_gyro_z=angular,
                              dynamic_tf_max_error=max(tf_errors), imu_acceleration=acceleration.tolist(),
                              dynamic_tf_samples=len(tfs), feedback_samples=len(joints))
            report.update(passed=True, received_clouds=len(stamps),
                lidar_sim_hz=1/float(np.median(np.diff(stamps))),
                imu_sim_hz=1/float(np.median(imu_steps)),
                wall_receive_hz=(len(wall_times)-1)/(wall_times[-1]-wall_times[0]),
                observed_real_time_factor=(stamps[-1]-stamps[0])/(wall_times[-1]-wall_times[0]),
                points_min=min(points_counts), points_max=max(points_counts), resources=sampled_resources)
            report['missed_frame_intervals'] = int(sum(max(0, round(dt/.1)-1) for dt in np.diff(stamps)))
            if args.moving:
                previous_time, previous_count, previous_tf_count = stamps[-1], len(stamps), len(tfs)
                for request in ('reset: {all: true}', 'pause: false'):
                    response = subprocess.run(['gz', 'service', '-s', '/world/livox_demo/control',
                        '--reqtype', 'gz.msgs.WorldControl', '--reptype', 'gz.msgs.Boolean',
                        '--timeout', '5000', '--req', request], capture_output=True, text=True,
                        check=True, timeout=8)
                    assert 'true' in response.stdout
                deadline = time.monotonic()+10
                while len(stamps) < previous_count+12 and time.monotonic() < deadline:
                    rclpy.spin_once(node, timeout_sec=.1)
                assert len(stamps) >= previous_count+12, 'Moving scan did not recover after reset'
                assert any(t < previous_time/2 for t in stamps[previous_count:]), 'No reset time rollback'
                assert any(stamp_seconds(tf.header.stamp) < previous_time/2
                           for tf in list(tfs)[previous_tf_count:]), 'Dynamic TF did not recover after reset'
                assert samples[-1].width > 100
                report['moving_reset_recovered'] = True
    except Exception as error:
        report.update(passed=False, error=repr(error), traceback=traceback.format_exc(), received_clouds=len(stamps),
                      feedback_samples=len(joints), dynamic_tf_samples=len(tfs))
    finally:
        if process:
            try:
                os.killpg(process.pid, signal.SIGINT); process.wait(timeout=12)
            except ProcessLookupError:
                pass
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL); process.wait(timeout=5)
        node.destroy_node(); rclpy.shutdown()
        (args.output/'result.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    if not __debug__:
        raise SystemExit('Validation requires assertions enabled; do not use Python -O')
    raise SystemExit(main())
