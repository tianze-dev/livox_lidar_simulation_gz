"""Composable bridge only: no world, GUI, robot spawning or TF ownership."""

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

from livox_lidar_simulation_gz.configuration import boolean, load_model, sensor_topics


def _setup(context):
    value = lambda key: LaunchConfiguration(key).perform(context)
    load_model(get_package_share_directory('livox_lidar_simulation_gz'), value('model'))
    points, imu = sensor_topics(value('namespace'), value('name'))
    arguments = [points + '@sensor_msgs/msg/PointCloud2[gz.msgs.PointCloudPacked',
                 imu + '@sensor_msgs/msg/Imu[gz.msgs.IMU']
    if boolean(value('bridge_clock')):
        arguments.append('/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock')
    return [Node(package='ros_gz_bridge', executable='parameter_bridge',
                 name=value('name') + '_bridge', namespace=value('namespace'),
                 arguments=arguments, parameters=[{'use_sim_time': True}], output='screen')]


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('model', default_value='mid360'),
        DeclareLaunchArgument('name', default_value='mid360'),
        DeclareLaunchArgument('namespace', default_value='livox'),
        DeclareLaunchArgument('bridge_clock', default_value='false'),
        OpaqueFunction(function=_setup),
    ])
