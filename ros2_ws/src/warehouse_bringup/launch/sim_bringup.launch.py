from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def _setup(context):
    world = LaunchConfiguration('world').perform(context)
    model = LaunchConfiguration('model').perform(context)
    sim = LaunchConfiguration('sim').perform(context).lower() == 'true'
    takeoff = LaunchConfiguration('takeoff').perform(context).lower() == 'true'
    camera = LaunchConfiguration('camera').perform(context).lower() == 'true'

    nodes = []
    if sim:
        link = f'/world/{world}/model/{model}/link'
        cam = f'{link}/camera_link/sensor/IMX214'
        imu = f'{link}/base_link/sensor/imu_sensor/imu'

        # (topic Gazebo, topic ROS stabile, tipo ROS, tipo Gazebo)
        bridges = [
            ('/clock', '/clock', 'rosgraph_msgs/msg/Clock', 'gz.msgs.Clock'),
            (imu, '/imu/data', 'sensor_msgs/msg/Imu', 'gz.msgs.IMU'),
        ]
        if camera:
            bridges.extend([
                (f'{cam}/image', '/camera/image_raw', 'sensor_msgs/msg/Image', 'gz.msgs.Image'),
                (f'{cam}/camera_info', '/camera/camera_info', 'sensor_msgs/msg/CameraInfo', 'gz.msgs.CameraInfo'),
            ])
        args = [f'{gz}@{ros_t}[{gz_t}' for gz, _, ros_t, gz_t in bridges]
        remaps = [(gz, ros) for gz, ros, _, _ in bridges if gz != ros]
        nodes.append(Node(
            package='ros_gz_bridge',
            executable='parameter_bridge',
            name='gz_bridge',
            arguments=args,
            remappings=remaps,
            output='screen',
        ))

    if takeoff:
        nodes.append(Node(
            package='warehouse_bringup',
            executable='takeoff_1m',
            name='takeoff_1m',
            output='screen',
        ))

    return nodes


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('sim', default_value='true'),
        DeclareLaunchArgument('world', default_value='warehouse_px4'),
        DeclareLaunchArgument('model', default_value='x500_depth_0'),
        DeclareLaunchArgument('takeoff', default_value='false'),
        DeclareLaunchArgument('camera', default_value='false'),
        OpaqueFunction(function=_setup),
    ])
