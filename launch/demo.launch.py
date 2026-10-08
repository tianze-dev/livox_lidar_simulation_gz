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

from livox_lidar_simulation_gz.configuration import boolean, load_model, sensor_topics
from livox_lidar_simulation_gz.world import prepare_demo_world


def _setup(context):
    value = lambda key: LaunchConfiguration(key).perform(context)
    share = Path(get_package_share_directory('livox_lidar_simulation_gz'))
    prefix = Path(get_package_prefix('livox_lidar_simulation_gz'))
    load_model(share, value('model'))
    points, imu = sensor_topics(value('namespace'), value('name'))
    description = xacro.process_file(str(share / 'urdf/demo.urdf.xacro'), mappings={
        'model': value('model'), 'name': value('name'),
        'points_topic': points, 'imu_topic': imu,
        'visual_mesh': value('visual_mesh'), 'mesh_rpy': value('mesh_rpy'),
    }).toxml()
    gz_launch = Path(get_package_share_directory('ros_gz_sim')) / 'launch/gz_sim.launch.py'
    gui = boolean(value('gui'))
    rviz = boolean(value('rviz'))
    directory, world_path = prepare_demo_world(share, description, value('name'))

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
        Node(package='robot_state_publisher', executable='robot_state_publisher',
             name=value('name') + '_state_publisher', namespace=value('namespace'),
             parameters=[{'robot_description': description, 'use_sim_time': True}], output='screen'),
        IncludeLaunchDescription(PythonLaunchDescriptionSource(str(share / 'launch/sensor.launch.py')),
                                 launch_arguments={'model': value('model'), 'name': value('name'),
                                                   'namespace': value('namespace'), 'bridge_clock': 'true'}.items()),
    ]
    if rviz:
        actions.append(Node(package='rviz2', executable='rviz2',
                            arguments=['-d', str(share / 'rviz/demo.rviz')],
                            remappings=[('/livox/mid360/points', points)],
                            parameters=[{'use_sim_time': True}], output='screen'))
    return actions


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('model', default_value='mid360'),
        DeclareLaunchArgument('name', default_value='mid360'),
        DeclareLaunchArgument('namespace', default_value='livox'),
        DeclareLaunchArgument('gui', default_value='true'),
        DeclareLaunchArgument('rviz', default_value='true'),
        DeclareLaunchArgument('visual_mesh', default_value=''),
        DeclareLaunchArgument('mesh_rpy', default_value='0 0 0'),
        OpaqueFunction(function=_setup),
    ])
