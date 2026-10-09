"""Independent static or moving Livox demo. All resources come from this package."""

import os
import math
from pathlib import Path

from ament_index_python.packages import get_package_prefix, get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, IncludeLaunchDescription, OpaqueFunction, RegisterEventHandler, SetEnvironmentVariable
from launch.event_handlers import OnShutdown
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
import xacro

from livox_lidar_simulation_gz.configuration import boolean, load_sensors
from livox_lidar_simulation_gz.world import prepare_demo_worlds, prepare_rviz


def _setup(context):
    value = lambda key: LaunchConfiguration(key).perform(context)
    share = Path(get_package_share_directory('livox_lidar_simulation_gz'))
    prefix = Path(get_package_prefix('livox_lidar_simulation_gz'))
    sensors = load_sensors(share, value('sensors_file'), defaults={
        key: value(key) for key in ('model', 'name', 'namespace', 'xyz', 'rpy', 'visual_mesh', 'mesh_rpy')})
    moving = boolean(value('moving'))
    if moving and len(sensors) != 1:
        raise ValueError('Moving fixture supports exactly one sensor')
    velocities = {key: value(key) for key in ('linear_velocity', 'angular_velocity')}
    for key, speed in velocities.items():
        if not math.isfinite(float(speed)) or abs(float(speed)) > .5:
            raise ValueError(f'{key} must be finite and in [-0.5, 0.5]')
    template = 'moving.urdf.xacro' if moving else 'demo.urdf.xacro'
    descriptions = [xacro.process_file(str(share / 'urdf' / template), mappings={**velocities, **{
        key: sensor[key] for key in ('model', 'name', 'xyz', 'rpy', 'points_topic', 'imu_topic',
                                     'visual_mesh', 'mesh_rpy')}}).toxml() for sensor in sensors]
    gui = boolean(value('gui'))
    rviz = boolean(value('rviz'))
    model_view = boolean(value('model_view'))
    directory, world_path = prepare_demo_worlds(
        share, [(sensor['name'], description) for sensor, description in zip(sensors, descriptions)])

    def cleanup(_context):
        directory.cleanup()
        return []

    actions = [
        RegisterEventHandler(OnShutdown(on_shutdown=[OpaqueFunction(function=cleanup)])),
        SetEnvironmentVariable('RGL_PATTERNS_DIR', str(share / 'patterns')),
        SetEnvironmentVariable('GZ_SIM_SYSTEM_PLUGIN_PATH',
                               str(prefix / 'lib/livox_lidar_simulation_gz/rgl') + os.pathsep +
                               os.environ.get('GZ_SIM_SYSTEM_PLUGIN_PATH', '')),
        # No intermediate shell: launch signals must reach the actual Gazebo CLI process.
        ExecuteProcess(cmd=['gz', 'sim', '-r', '-v', '3', str(world_path)] + ([] if gui else ['-s']),
                       output='screen'),
    ]
    for index, (sensor, description) in enumerate(zip(sensors, descriptions)):
        actions.extend([
            Node(package='robot_state_publisher', executable='robot_state_publisher',
                 name=sensor['name'] + '_state_publisher', namespace=sensor['namespace'],
                 remappings=[('robot_description', sensor['name'] + '/robot_description'),
                             ('joint_states', '/fixture/' + sensor['name'] + '/joint_states')],
                 parameters=[{'robot_description': description, 'use_sim_time': True, 'publish_frequency': 200.0}], output='screen'),
            IncludeLaunchDescription(PythonLaunchDescriptionSource(str(share / 'launch/sensor.launch.py')),
                                     launch_arguments={'model': sensor['model'], 'name': sensor['name'],
                                                       'namespace': sensor['namespace'],
                                                       'points_topic': sensor['points_topic'],
                                                       'imu_topic': sensor['imu_topic'],
                                                       'bridge_clock': 'true' if index == 0 else 'false',
                                                       'clock_topic': '/world/livox_demo/clock'}.items()),
        ])
        if moving:
            topic = '/fixture/' + sensor['name']
            actions.append(Node(package='ros_gz_bridge', executable='parameter_bridge',
                name=sensor['name'] + '_fixture_bridge', output='screen',
                arguments=[topic + '/joint_states@sensor_msgs/msg/JointState[gz.msgs.Model',
                           topic + '/linear_velocity@std_msgs/msg/Float64]gz.msgs.Double',
                           topic + '/angular_velocity@std_msgs/msg/Float64]gz.msgs.Double'],
                parameters=[{'use_sim_time': True}]))
    if rviz:
        actions.append(Node(package='rviz2', executable='rviz2',
                            arguments=['-d', str(prepare_rviz(share, directory.name, sensors, model_view))],
                            parameters=[{'use_sim_time': True}], output='screen'))
    return actions


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('model', default_value='mid360'),
        DeclareLaunchArgument('name', default_value='mid360'),
        DeclareLaunchArgument('namespace', default_value='livox'),
        DeclareLaunchArgument('xyz', default_value='0 0 1'),
        DeclareLaunchArgument('rpy', default_value='0 0 0'),
        DeclareLaunchArgument('sensors_file', default_value='',
                              description='Optional instance YAML; overrides single-sensor arguments.'),
        DeclareLaunchArgument('gui', default_value='true'),
        DeclareLaunchArgument('rviz', default_value='true'),
        DeclareLaunchArgument('model_view', default_value='false',
                              description='RViz close-up of the first sensor; hides point clouds.'),
        DeclareLaunchArgument('moving', default_value='false'),
        DeclareLaunchArgument('linear_velocity', default_value='0.1'),
        DeclareLaunchArgument('angular_velocity', default_value='0.15'),
        DeclareLaunchArgument('visual_mesh', default_value=''),
        DeclareLaunchArgument('mesh_rpy', default_value='0 0 0'),
        OpaqueFunction(function=_setup),
    ])
