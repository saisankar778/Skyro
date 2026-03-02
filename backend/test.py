from dronekit import connect, VehicleMode
from pymavlink import mavutil
import time

# Connect to the Vehicle over UDP
print("Connecting to vehicle...")
# SITL example: udp:127.0.0.1:14550
# Companion computer example: udp:<IP>:14550
vehicle = connect('udp:127.0.0.1:14550', wait_ready=True)

def set_servo(channel: int, pwm_value: int):
    """
    Sets a servo connected to a specified channel to a given PWM value.
    :param channel: The servo channel (e.g., 9 for SERVO9)
    :param pwm_value: The PWM value (1000–2000 µs typical)
    """
    print(f"Setting servo at channel {channel} to PWM {pwm_value}")
    msg = vehicle.message_factory.command_long_encode(
        0, 0,                                   # target system, target component
        mavutil.mavlink.MAV_CMD_DO_SET_SERVO,   # command
        0,                                      # confirmation
        channel,                                # servo number
        pwm_value,                              # PWM value
        0, 0, 0, 0, 0                           # unused parameters
    )
    vehicle.send_mavlink(msg)
    vehicle.flush()

# Example usage
print("Arming vehicle...")
vehicle.mode = VehicleMode("GUIDED")
vehicle.armed = True
time.sleep(3)

print("Moving servo...")
set_servo(10, 1500)  # Midpoint
time.sleep(2)
set_servo(10, 2000)  # Max
time.sleep(2)
set_servo(10, 1000)  # Min
time.sleep(2)

print("Disarming vehicle...")
vehicle.armed = False
vehicle.close()
