"""Composable bridge only: no world, GUI, robot spawning or TF ownership."""

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

from livox_lidar_simulation_gz.configuration import boolean, load_model, sensor_topics, validate_topic


def _setup(context):
    value = lambda key: LaunchConfiguration(key).perform(context)
    load_model(get_package_share_directory('livox_lidar_simulation_gz'), value('model'))
    points, imu = sensor_topics(value('namespace'), value('name'),
                               value('points_topic'), value('imu_topic'))
    arguments = [points + '@sensor_msgs/msg/PointCloud2[gz.msgs.PointCloudPacked',
                 imu + '@sensor_msgs/msg/Imu[gz.msgs.IMU']
    remappings = []
    if boolean(value('bridge_clock')):
        clock = validate_topic(value('clock_topic'))
        arguments.append(clock + '@rosgraph_msgs/msg/Clock[gz.msgs.Clock')
        if clock != '/clock':
            remappings.append((clock, '/clock'))
    return [Node(package='ros_gz_bridge', executable='parameter_bridge',
                 name=value('name') + '_bridge', namespace=value('namespace').strip('/'),
                 arguments=arguments, remappings=remappings,
                 parameters=[{'use_sim_time': True}], output='screen')]


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('model', default_value='mid360'),
        DeclareLaunchArgument('name', default_value='mid360'),
        DeclareLaunchArgument('namespace', default_value='livox'),
        DeclareLaunchArgument('points_topic', default_value=''),
        DeclareLaunchArgument('imu_topic', default_value=''),
        DeclareLaunchArgument('bridge_clock', default_value='false'),
        DeclareLaunchArgument('clock_topic', default_value='/clock',
                              description='Gazebo clock source, e.g. /world/my_world/clock; ROS output is /clock'),
        OpaqueFunction(function=_setup),
    ])
