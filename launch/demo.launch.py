"""Independent static MID-360 scene. All resources come from this package."""

import os
from pathlib import Path

from ament_index_python.packages import get_package_prefix, get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction, RegisterEventHandler, SetEnvironmentVariable
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
    descriptions = [xacro.process_file(str(share / 'urdf/demo.urdf.xacro'), mappings={
        key: sensor[key] for key in ('model', 'name', 'xyz', 'rpy', 'points_topic', 'imu_topic',
                                     'visual_mesh', 'mesh_rpy')}).toxml() for sensor in sensors]
    gz_launch = Path(get_package_share_directory('ros_gz_sim')) / 'launch/gz_sim.launch.py'
    gui = boolean(value('gui'))
    rviz = boolean(value('rviz'))
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
        IncludeLaunchDescription(PythonLaunchDescriptionSource(str(gz_launch)),
                                 launch_arguments={'gz_args': ['-r -v 3 ' if gui else '-r -s -v 3 ',
                                                              str(world_path)]}.items()),
    ]
    for index, (sensor, description) in enumerate(zip(sensors, descriptions)):
        actions.extend([
            Node(package='robot_state_publisher', executable='robot_state_publisher',
                 name=sensor['name'] + '_state_publisher', namespace=sensor['namespace'],
                 parameters=[{'robot_description': description, 'use_sim_time': True}], output='screen'),
            IncludeLaunchDescription(PythonLaunchDescriptionSource(str(share / 'launch/sensor.launch.py')),
                                     launch_arguments={'model': sensor['model'], 'name': sensor['name'],
                                                       'namespace': sensor['namespace'],
                                                       'bridge_clock': 'true' if index == 0 else 'false'}.items()),
        ])
    if rviz:
        actions.append(Node(package='rviz2', executable='rviz2',
                            arguments=['-d', str(prepare_rviz(share, directory.name, sensors))],
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
        DeclareLaunchArgument('visual_mesh', default_value=''),
        DeclareLaunchArgument('mesh_rpy', default_value='0 0 0'),
        OpaqueFunction(function=_setup),
    ])
