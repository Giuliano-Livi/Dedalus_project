import math

import rclpy
from px4_msgs.msg import (
    OffboardControlMode,
    TrajectorySetpoint,
    VehicleCommand,
    VehicleLocalPosition,
    VehicleStatus,
)
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy


class TakeoffOneMeter(Node):
    def __init__(self):
        super().__init__('takeoff_1m')
        self._start_position = None
        self._setpoint_count = 0
        self._offboard_active = False
        self._armed = False
        self._last_mode_request_ns = 0
        self._last_arm_request_ns = 0
        self._holding_logged = False

        px4_output_qos = QoSProfile(
            depth=10,
            reliability=ReliabilityPolicy.BEST_EFFORT,
        )
        self._control_mode_pub = self.create_publisher(
            OffboardControlMode, '/fmu/in/offboard_control_mode', 10
        )
        self._setpoint_pub = self.create_publisher(
            TrajectorySetpoint, '/fmu/in/trajectory_setpoint', 10
        )
        self._vehicle_command_pub = self.create_publisher(
            VehicleCommand, '/fmu/in/vehicle_command', 10
        )
        self.create_subscription(
            VehicleLocalPosition,
            '/fmu/out/vehicle_local_position_v1',
            self._on_local_position,
            px4_output_qos,
        )
        self.create_subscription(
            VehicleStatus,
            '/fmu/out/vehicle_status_v4',
            self._on_vehicle_status,
            px4_output_qos,
        )
        self.create_timer(0.1, self._control_loop)
        self.get_logger().info('In attesa di una posizione locale valida da PX4.')

    def _timestamp_us(self):
        return self.get_clock().now().nanoseconds // 1000

    def _on_local_position(self, msg):
        if self._start_position is None and msg.xy_valid and msg.z_valid:
            self._start_position = (msg.x, msg.y, msg.z)
            self.get_logger().info(
                'Posizione iniziale acquisita; target a 1 m sopra il punto di partenza.'
            )

    def _on_vehicle_status(self, msg):
        self._offboard_active = (
            msg.nav_state == VehicleStatus.NAVIGATION_STATE_OFFBOARD
        )
        self._armed = msg.arming_state == VehicleStatus.ARMING_STATE_ARMED

    def _publish_setpoints(self, timestamp):
        control_mode = OffboardControlMode()
        control_mode.timestamp = timestamp
        control_mode.position = True
        self._control_mode_pub.publish(control_mode)

        start_x, start_y, start_z = self._start_position
        setpoint = TrajectorySetpoint()
        setpoint.timestamp = timestamp
        setpoint.position = [start_x, start_y, start_z - 1.0]
        setpoint.velocity = [math.nan, math.nan, math.nan]
        setpoint.acceleration = [math.nan, math.nan, math.nan]
        setpoint.jerk = [math.nan, math.nan, math.nan]
        setpoint.yaw = math.nan
        setpoint.yawspeed = math.nan
        self._setpoint_pub.publish(setpoint)

    def _publish_vehicle_command(self, command, param1=0.0, param2=0.0):
        msg = VehicleCommand()
        msg.timestamp = self._timestamp_us()
        msg.param1 = float(param1)
        msg.param2 = float(param2)
        msg.command = command
        msg.target_system = 1
        msg.target_component = 1
        msg.source_system = 1
        msg.source_component = 1
        msg.from_external = True
        self._vehicle_command_pub.publish(msg)

    def _control_loop(self):
        if self._start_position is None:
            return

        timestamp = self._timestamp_us()
        self._publish_setpoints(timestamp)
        self._setpoint_count += 1
        if self._setpoint_count < 10:
            return

        now_ns = self.get_clock().now().nanoseconds
        if not self._offboard_active:
            if now_ns - self._last_mode_request_ns >= 1_000_000_000:
                self._publish_vehicle_command(
                    VehicleCommand.VEHICLE_CMD_DO_SET_MODE,
                    param1=1.0,
                    param2=6.0,
                )
                self._last_mode_request_ns = now_ns
            return

        if not self._armed:
            if now_ns - self._last_arm_request_ns >= 1_000_000_000:
                self._publish_vehicle_command(
                    VehicleCommand.VEHICLE_CMD_COMPONENT_ARM_DISARM,
                    param1=1.0,
                )
                self._last_arm_request_ns = now_ns
            return

        if not self._holding_logged:
            self.get_logger().info('Drone armato: mantengo il setpoint a 1 m.')
            self._holding_logged = True


def main(args=None):
    rclpy.init(args=args)
    node = TakeoffOneMeter()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()