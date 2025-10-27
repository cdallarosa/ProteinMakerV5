"""
ODrive Axis Controller for X,Y,Z Gantry System
Complete control interface with torque-based homing and position control
"""

import odrive
from odrive.enums import AxisState as ODriveAxisState
from odrive.enums import ControlMode, InputMode, MotorType, EncoderId, GpioMode, Protocol
from odrive.utils import dump_errors, request_state
import math
import time
import logging
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, Tuple, List, Union
from threading import Thread, Event, Lock

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS AND DATA CLASSES
# ============================================================================

class AxisType(Enum):
    """Axis identification"""
    X_AXIS = "X"
    Y_AXIS = "Y"
    Z_AXIS = "Z"
    
    
class AxisState(Enum):
    """Axis operational states"""
    DISCONNECTED = "disconnected"
    IDLE = "idle"
    HOMING = "homing"
    MOVING = "moving"
    COMPLETED = "completed"
    ERROR = "error"
    TORQUE_LIMIT_REACHED = "torque_limit_reached"
    CALIBRATING = "calibrating"
    

@dataclass
class MotionProfile:
    """Motion control parameters"""
    velocity_limit: float = 10.0  # turns/sec
    acceleration_limit: float = 10.0  # turns/sec^2
    deceleration_limit: float = 10.0  # turns/sec^2
    velocity_ramp_rate: float = 10.0  # turns/sec^2
    

@dataclass
class AxisConfig:
    """Axis configuration parameters"""
    serial_number: str = ""
    axis_type: AxisType = AxisType.X_AXIS
    axis_number: int = 0  # 0 for axis0, 1 for axis1
    
    # Motor configuration
    motor_type: MotorType = MotorType.HIGH_CURRENT
    pole_pairs: int = 4
    torque_constant: float = 0.095
    encoder_cpr: int = 3070
    
    # Current/Torque limits
    current_soft_max: float = 30.0  # Amps
    current_hard_max: float = 49.0  # Amps
    calibration_current: float = 10.0  # Amps
    
    # Torque limits for operation
    torque_soft_limit: float = 2.0  # Nm - normal operation limit
    torque_hard_limit: float = 4.0  # Nm - safety limit
    homing_torque_threshold: float = 1.5  # Nm - torque to detect home
    
    # Position limits (in turns)
    position_min: Optional[float] = None
    position_max: Optional[float] = None
    
    # Motion profile
    motion_profile: MotionProfile = field(default_factory=MotionProfile)
    
    # Homing configuration
    homing_velocity: float = 2.0  # turns/sec
    homing_backoff_turns: float = 0.5  # turns to back off after hitting limit
    
    # Timeouts
    move_timeout: float = 30.0  # seconds
    homing_timeout: float = 60.0  # seconds
    

@dataclass 
class AxisStatus:
    """Current axis status"""
    state: AxisState = AxisState.DISCONNECTED
    position: float = 0.0  # turns
    velocity: float = 0.0  # turns/sec
    current: float = 0.0  # Amps
    torque: float = 0.0  # Nm
    target_position: Optional[float] = None
    is_homed: bool = False
    errors: List[str] = field(default_factory=list)
    last_update: datetime = field(default_factory=datetime.now)
    

# ============================================================================
# MAIN ODRIVE AXIS CLASS
# ============================================================================

class ODriveAxis:
    """
    ODrive Axis Controller for Gantry System
    
    Features:
    - Connection by serial number for axis identification
    - Torque-based homing without limit switches
    - Position control with configurable speed
    - Real-time torque monitoring and limits
    - Comprehensive status reporting
    """
    
    def __init__(self, config: AxisConfig):
        """
        Initialize ODrive axis controller
        
        Args:
            config: AxisConfig object with all parameters
        """
        self.config = config
        self.status = AxisStatus()
        self._odrive = None
        self._axis = None
        self._monitoring_thread = None
        self._stop_monitoring = Event()
        self._lock = Lock()
        self._move_start_time = None
        
        # Set up logging
        self.logger = logging.getLogger(f"{__name__}.{config.axis_type.value}")
        
    # ========================================================================
    # CONNECTION AND INITIALIZATION
    # ========================================================================
    
    def connect(self, timeout: float = 10.0) -> bool:
        """
        Connect to ODrive by serial number
        
        Args:
            timeout: Connection timeout in seconds
            
        Returns:
            True if connection successful
        """
        try:
            self.logger.info(f"Connecting to ODrive {self.config.serial_number}...")
            
            # Find ODrive by serial number using synchronous API
            self._odrive = odrive.find_any(serial_number=self.config.serial_number, 
                                          timeout=timeout)
            
            if not self._odrive:
                self.logger.error(f"ODrive {self.config.serial_number} not found")
                self.status.state = AxisState.DISCONNECTED
                return False
                
            # Get axis reference
            if self.config.axis_number == 0:
                self._axis = self._odrive.axis0
            elif self.config.axis_number == 1:
                self._axis = self._odrive.axis1
            else:
                raise ValueError(f"Invalid axis number: {self.config.axis_number}")
                
            # Configure the axis
            self._configure_axis()
            
            # Start monitoring thread
            self._start_monitoring()
            
            self.status.state = AxisState.IDLE
            self.logger.info(f"Connected to {self.config.axis_type.value} axis")
            return True
            
        except Exception as e:
            self.logger.error(f"Connection failed: {e}")
            self.status.state = AxisState.ERROR
            self.status.errors.append(str(e))
            return False
            
    def disconnect(self):
        """Disconnect from ODrive"""
        try:
            self._stop_monitoring.set()
            if self._monitoring_thread:
                self._monitoring_thread.join(timeout=2.0)
                
            if self._axis:
                request_state(self._axis, ODriveAxisState.IDLE)
                
            self._odrive = None
            self._axis = None
            self.status.state = AxisState.DISCONNECTED
            self.logger.info("Disconnected from ODrive")
            
        except Exception as e:
            self.logger.error(f"Error during disconnect: {e}")
            
    def _configure_axis(self):
        """Configure axis parameters"""
        try:
            odrv = self._odrive
            axis = self._axis
            
            self.logger.info("Starting axis configuration...")
            
            # DC bus configuration
            self.logger.debug("Configuring DC bus...")
            odrv.config.dc_bus_overvoltage_trip_level = 50
            odrv.config.dc_bus_undervoltage_trip_level = 10.5
            odrv.config.dc_max_positive_current = 60
            odrv.config.dc_max_negative_current = -60
            
            # Motor configuration
            axis.config.motor.motor_type = self.config.motor_type
            axis.config.motor.pole_pairs = self.config.pole_pairs
            axis.config.motor.torque_constant = self.config.torque_constant
            axis.config.motor.current_soft_max = self.config.current_soft_max
            axis.config.motor.current_hard_max = self.config.current_hard_max
            axis.config.motor.calibration_current = self.config.calibration_current
            axis.config.motor.resistance_calib_max_voltage = 6
            
            # Encoder configuration
            axis.config.load_encoder = EncoderId.INC_ENCODER0
            axis.config.commutation_encoder = EncoderId.INC_ENCODER0
            
            # Set up incremental encoder
            if hasattr(odrv, 'inc_encoder0'):
                odrv.inc_encoder0.config.enabled = True
                odrv.inc_encoder0.config.cpr = self.config.encoder_cpr
            
            # Controller configuration for position control
            axis.controller.config.control_mode = ControlMode.POSITION_CONTROL
            axis.controller.config.input_mode = InputMode.TRAP_TRAJ
            
            # Motion profile
            profile = self.config.motion_profile
            axis.controller.config.vel_limit = profile.velocity_limit
            axis.controller.config.vel_limit_tolerance = 1.2
            axis.trap_traj.config.vel_limit = profile.velocity_limit
            axis.trap_traj.config.accel_limit = profile.acceleration_limit
            axis.trap_traj.config.decel_limit = profile.deceleration_limit
            
            # Torque limits (converted from Nm to Amps)
            soft_current = self.config.torque_soft_limit / self.config.torque_constant
            hard_current = self.config.torque_hard_limit / self.config.torque_constant
            
            axis.config.torque_soft_min = -soft_current * self.config.torque_constant
            axis.config.torque_soft_max = soft_current * self.config.torque_constant
            
            # Disable CAN for now
            odrv.can.config.protocol = Protocol.NONE
            
            # Enable watchdog for safety
            axis.config.enable_watchdog = True
            axis.watchdog_feed()
            
            self.logger.info("Axis configuration complete")
            
        except Exception as e:
            self.logger.error(f"Configuration failed: {e}")
            raise
            
    # ========================================================================
    # HOMING FUNCTIONALITY
    # ========================================================================
    
    def home_with_velocity_control(self, homing_speed: float = 0.01, e_stop_callback=None) -> bool:
        """
        Home the axis using constant velocity control with virtual e-stop
        Finds both end stops and returns to middle
        
        Args:
            homing_speed: Speed for homing in turns/sec (default 0.01 rev/s)
            e_stop_callback: Optional callback function for emergency stop check
            
        Returns:
            True if homing successful
        """
        if not self._axis:
            self.logger.error("Not connected to ODrive")
            return False
            
        try:
            self.logger.info(f"Starting velocity-controlled homing for {self.config.axis_type.value}")
            self.status.state = AxisState.HOMING
            
            # Clear any existing errors first
            try:
                self._axis.clear_errors()
            except AttributeError:
                # Try ODrive-level clear for older firmware
                try:
                    self._odrive.clear_errors()
                except:
                    self.logger.info("Note: Could not clear errors (may not be needed)")
            
            # Enter closed loop control
            request_state(self._axis, ODriveAxisState.CLOSED_LOOP_CONTROL)
            time.sleep(1.0)  # Give more time for state transition
            
            # Verify we're in closed loop
            if self._axis.current_state != ODriveAxisState.CLOSED_LOOP_CONTROL:
                self.logger.error(f"Failed to enter closed loop. State: {self._axis.current_state}, Error: {self._axis.error}")
                self.status.state = AxisState.ERROR
                return False
            
            # Store original settings
            original_vel_limit = self._axis.trap_traj.config.vel_limit
            original_control_mode = self._axis.controller.config.control_mode
            original_input_mode = self._axis.controller.config.input_mode
            
            # Switch to velocity control mode
            self.logger.info("Switching to velocity control mode...")
            try:
                self._axis.controller.config.control_mode = ControlMode.VELOCITY_CONTROL
                self._axis.controller.config.input_mode = InputMode.VEL_RAMP
                self._axis.controller.config.vel_ramp_rate = 10.0  # ramp rate in turns/s^2
                self.logger.info(f"Velocity control configured. Mode: {self._axis.controller.config.control_mode}, Input: {self._axis.controller.config.input_mode}")
            except Exception as e:
                self.logger.error(f"Failed to set velocity control: {e}")
                # Try alternative velocity control setup for older firmware
                try:
                    self._axis.controller.config.control_mode = ControlMode.VELOCITY_CONTROL
                    self._axis.controller.config.input_mode = InputMode.PASSTHROUGH
                    self.logger.info("Using passthrough input mode for velocity control")
                except:
                    self.logger.error("Unable to configure velocity control")
                    self.status.state = AxisState.ERROR
                    return False
            
            # Variables to store end stop positions
            negative_end = None
            positive_end = None
            
            # Find negative end stop
            self.logger.info(f"Finding negative end stop at {homing_speed} rev/s...")
            negative_end = self._find_end_stop(-homing_speed, e_stop_callback)
            
            if negative_end is None:
                self.logger.error("Failed to find negative end stop")
                # Restore settings
                self._axis.controller.config.control_mode = original_control_mode
                self._axis.controller.config.input_mode = original_input_mode
                self._axis.trap_traj.config.vel_limit = original_vel_limit
                self.status.state = AxisState.ERROR
                return False
            
            # Back off from negative end
            self.logger.info("Backing off from negative end stop...")
            self._axis.controller.input_vel = homing_speed * 2  # Back off a bit faster
            time.sleep(1.0)
            self._axis.controller.input_vel = 0
            time.sleep(0.5)
            
            # Find positive end stop
            self.logger.info(f"Finding positive end stop at {homing_speed} rev/s...")
            positive_end = self._find_end_stop(homing_speed, e_stop_callback)
            
            if positive_end is None:
                self.logger.error("Failed to find positive end stop")
                # Restore settings
                self._axis.controller.config.control_mode = original_control_mode
                self._axis.controller.config.input_mode = original_input_mode
                self._axis.trap_traj.config.vel_limit = original_vel_limit
                self.status.state = AxisState.ERROR
                return False
            
            # Calculate middle position
            travel_distance = abs(positive_end - negative_end)
            middle_position = negative_end + (travel_distance / 2)
            
            self.logger.info(f"Found end stops: negative={negative_end:.3f}, positive={positive_end:.3f}")
            self.logger.info(f"Travel distance: {travel_distance:.3f} turns")
            self.logger.info(f"Moving to middle position: {middle_position:.3f}")
            
            # Switch back to position control for accurate middle positioning
            self._axis.controller.config.control_mode = ControlMode.POSITION_CONTROL
            self._axis.controller.config.input_mode = InputMode.TRAP_TRAJ
            self._axis.trap_traj.config.vel_limit = 0.5  # Faster for returning to middle
            
            # Move to middle position
            self._axis.controller.input_pos = middle_position
            
            # Wait for move to complete
            start_time = time.time()
            while time.time() - start_time < 10.0:  # 10 second timeout
                current_pos = self._axis.pos_vel_mapper.pos_rel if hasattr(self._axis, 'pos_vel_mapper') else self._axis.controller.input_pos
                if abs(current_pos - middle_position) < 0.01:  # Within tolerance
                    break
                    
                # Check for e-stop
                if e_stop_callback and e_stop_callback():
                    self.logger.warning("E-stop triggered during return to middle")
                    self._axis.controller.input_vel = 0
                    self._axis.controller.input_pos = current_pos
                    self.status.state = AxisState.ERROR
                    return False
                    
                time.sleep(0.01)
            
            # Set middle as zero position
            self.logger.info("Setting middle position as zero...")
            self._axis.controller.input_pos = 0
            if hasattr(self._axis, 'pos_vel_mapper'):
                self._axis.pos_vel_mapper.set_pos_rel(0)
            
            # Store travel limits
            self.config.position_min = -(travel_distance / 2) + 0.1  # Leave small margin
            self.config.position_max = (travel_distance / 2) - 0.1
            
            # Restore original velocity limit
            self._axis.trap_traj.config.vel_limit = original_vel_limit
            
            self.status.is_homed = True
            self.status.state = AxisState.IDLE
            self.logger.info(f"Homing complete! Working range: [{self.config.position_min:.3f}, {self.config.position_max:.3f}] turns")
            return True
            
        except Exception as e:
            self.logger.error(f"Homing failed: {e}")
            self.status.state = AxisState.ERROR
            self.status.errors.append(str(e))
            return False
    
    def _find_end_stop(self, velocity: float, e_stop_callback=None) -> Optional[float]:
        """
        Find an end stop using velocity control and torque detection
        
        Args:
            velocity: Velocity to move at (positive or negative)
            e_stop_callback: Optional callback for emergency stop
            
        Returns:
            Position where end stop was detected, or None if failed
        """
        # Start moving at constant velocity
        self._axis.controller.input_vel = velocity
        
        # Monitor torque
        start_time = time.time()
        torque_samples = []
        last_position = self._axis.pos_vel_mapper.pos_rel if hasattr(self._axis, 'pos_vel_mapper') else self._axis.controller.input_pos
        position_stable_count = 0
        
        while time.time() - start_time < self.config.homing_timeout:
            # Check for e-stop
            if e_stop_callback and e_stop_callback():
                self.logger.warning("E-stop triggered during homing")
                self._axis.controller.input_vel = 0
                return None
            
            # Get current position
            current_pos = self._axis.pos_vel_mapper.pos_rel if hasattr(self._axis, 'pos_vel_mapper') else self._axis.controller.input_pos
            
            # Check if motor is stalled (position not changing despite velocity command)
            position_change = abs(current_pos - last_position)
            if position_change < 0.0001:  # Very small movement threshold
                position_stable_count += 1
            else:
                position_stable_count = 0
            last_position = current_pos
            
            # If position stable for multiple samples, we've hit the end
            if position_stable_count > 20:  # 200ms of no movement
                self.logger.info(f"End stop detected at position {current_pos:.3f}")
                self._axis.controller.input_vel = 0
                return current_pos
            
            # Also monitor torque as backup detection
            try:
                if hasattr(self._axis.motor, 'current_control'):
                    current = self._axis.motor.current_control.Iq_measured
                elif hasattr(self._axis.motor, 'foc'):
                    current = self._axis.motor.foc.Iq_measured
                else:
                    current = 0.0
            except:
                current = 0.0
            torque = abs(current * self.config.torque_constant)
            
            torque_samples.append(torque)
            if len(torque_samples) > 10:
                torque_samples.pop(0)
            
            avg_torque = sum(torque_samples) / len(torque_samples) if torque_samples else 0
            
            # Check torque threshold
            if avg_torque > self.config.homing_torque_threshold:
                self.logger.info(f"End stop detected via torque ({avg_torque:.2f} Nm) at position {current_pos:.3f}")
                self._axis.controller.input_vel = 0
                return current_pos
            
            # Feed watchdog
            self._axis.watchdog_feed()
            time.sleep(0.01)
        
        # Timeout
        self._axis.controller.input_vel = 0
        return None
    
    def home(self, direction: int = -1) -> bool:
        """
        Legacy home method - redirects to new velocity control method
        
        Args:
            direction: 1 for positive, -1 for negative direction (ignored in new method)
            
        Returns:
            True if homing successful
        """
        return self.home_with_velocity_control()
            
    # ========================================================================
    # MOTION CONTROL
    # ========================================================================
    
    def move_to_position(self, position: float, velocity: Optional[float] = None) -> bool:
        """
        Move to absolute position
        
        Args:
            position: Target position in turns
            velocity: Optional velocity in turns/sec
            
        Returns:
            True if move command accepted
        """
        if not self._axis:
            self.logger.error("Not connected to ODrive")
            return False
            
        if not self.status.is_homed:
            self.logger.warning("Axis not homed - position may be incorrect")
            
        try:
            # Check position limits
            if self.config.position_min is not None and position < self.config.position_min:
                self.logger.error(f"Position {position} below minimum {self.config.position_min}")
                return False
                
            if self.config.position_max is not None and position > self.config.position_max:
                self.logger.error(f"Position {position} above maximum {self.config.position_max}")
                return False
                
            # Set velocity if specified
            if velocity is not None:
                self._axis.trap_traj.config.vel_limit = min(velocity, self.config.motion_profile.velocity_limit)
            
            # Ensure in position control mode
            if self._axis.current_state != ODriveAxisState.CLOSED_LOOP_CONTROL:
                request_state(self._axis, ODriveAxisState.CLOSED_LOOP_CONTROL)
                time.sleep(0.5)
                
            # Set target position
            self._axis.controller.input_pos = position
            self.status.target_position = position
            self.status.state = AxisState.MOVING
            self._move_start_time = time.time()
            
            self.logger.info(f"Moving to position {position:.3f} turns")
            return True
            
        except Exception as e:
            self.logger.error(f"Move command failed: {e}")
            self.status.state = AxisState.ERROR
            self.status.errors.append(str(e))
            return False
            
    def move_relative(self, distance: float, velocity: Optional[float] = None) -> bool:
        """
        Move relative to current position
        
        Args:
            distance: Distance to move in turns
            velocity: Optional velocity in turns/sec
            
        Returns:
            True if move command accepted
        """
        if not self._axis:
            return False
            
        # Get current position
        current_pos = self._axis.pos_vel_mapper.pos_rel if hasattr(self._axis, 'pos_vel_mapper') else self._axis.controller.input_pos
        target_pos = current_pos + distance
        return self.move_to_position(target_pos, velocity)
        
    def stop(self, emergency: bool = False):
        """
        Stop motion
        
        Args:
            emergency: If True, stop immediately; if False, decelerate smoothly
        """
        if not self._axis:
            return
            
        try:
            if emergency:
                # Emergency stop - go to idle immediately
                request_state(self._axis, ODriveAxisState.IDLE)
            else:
                # Smooth stop - set target to current position
                current_pos = self._axis.pos_vel_mapper.pos_rel if hasattr(self._axis, 'pos_vel_mapper') else self._axis.controller.input_pos
                self._axis.controller.input_pos = current_pos
                
            self.status.state = AxisState.IDLE
            self.status.target_position = None
            self.logger.info("Motion stopped")
            
        except Exception as e:
            self.logger.error(f"Stop command failed: {e}")
            
    def is_at_position(self, tolerance: float = 0.01) -> bool:
        """
        Check if axis is at target position
        
        Args:
            tolerance: Position tolerance in turns
            
        Returns:
            True if at position within tolerance
        """
        if not self._axis or self.status.target_position is None:
            return False
            
        # Get current position
        current_pos = self._axis.pos_vel_mapper.pos_rel if hasattr(self._axis, 'pos_vel_mapper') else self._axis.controller.input_pos
        error = abs(current_pos - self.status.target_position)
        return error <= tolerance
        
    def set_velocity_limit(self, velocity: float):
        """
        Set velocity limit for moves
        
        Args:
            velocity: Velocity limit in turns/sec
        """
        if self._axis:
            max_vel = self.config.motion_profile.velocity_limit
            self._axis.trap_traj.config.vel_limit = min(velocity, max_vel)
            self.logger.info(f"Velocity limit set to {velocity:.2f} turns/sec")
            
    # ========================================================================
    # STATUS AND MONITORING
    # ========================================================================
    
    def _start_monitoring(self):
        """Start background monitoring thread"""
        self._stop_monitoring.clear()
        self._monitoring_thread = Thread(target=self._monitor_status, daemon=True)
        self._monitoring_thread.start()
        
    def _monitor_status(self):
        """Background thread to monitor axis status"""
        while not self._stop_monitoring.is_set():
            try:
                if self._axis:
                    with self._lock:
                        # Update position and velocity
                        # Try different methods to get position based on firmware version
                        if hasattr(self._axis, 'pos_vel_mapper'):
                            self.status.position = self._axis.pos_vel_mapper.pos_rel
                            self.status.velocity = self._axis.pos_vel_mapper.vel
                        elif hasattr(self._axis, 'encoder'):
                            # Fallback to encoder estimates if available
                            if hasattr(self._axis.encoder, 'pos_estimate'):
                                self.status.position = self._axis.encoder.pos_estimate
                                self.status.velocity = self._axis.encoder.vel_estimate
                            else:
                                # Last resort - use controller input position
                                self.status.position = self._axis.controller.input_pos
                                self.status.velocity = 0.0  # Can't determine velocity
                        else:
                            # Absolute fallback
                            self.status.position = self._axis.controller.input_pos
                            self.status.velocity = 0.0
                        
                        # Update current and torque - handle different firmware versions
                        try:
                            if hasattr(self._axis.motor, 'current_control'):
                                current = self._axis.motor.current_control.Iq_measured
                            elif hasattr(self._axis.motor, 'foc'):
                                current = self._axis.motor.foc.Iq_measured
                            elif hasattr(self._axis.motor, 'current_meas_phB'):
                                # Rough estimate from phase currents
                                current = abs(self._axis.motor.current_meas_phB)
                            else:
                                # Fallback - can't measure current
                                current = 0.0
                        except:
                            current = 0.0
                        self.status.current = current
                        self.status.torque = current * self.config.torque_constant
                        
                        # Check if move completed
                        if self.status.state == AxisState.MOVING:
                            if self.is_at_position():
                                self.status.state = AxisState.COMPLETED
                                self.logger.info("Move completed")
                                
                            # Check for torque limit
                            if abs(self.status.torque) > self.config.torque_soft_limit:
                                self.status.state = AxisState.TORQUE_LIMIT_REACHED
                                self.logger.warning(f"Torque limit reached: {self.status.torque:.2f} Nm")
                                self.stop()
                                
                            # Check for timeout
                            if self._move_start_time:
                                elapsed = time.time() - self._move_start_time
                                if elapsed > self.config.move_timeout:
                                    self.logger.error("Move timeout")
                                    self.stop()
                                    self.status.state = AxisState.ERROR
                                    
                        # Update timestamp
                        self.status.last_update = datetime.now()
                        
                        # Feed watchdog
                        self._axis.watchdog_feed()
                        
            except Exception as e:
                self.logger.error(f"Monitoring error: {e}")
                
            time.sleep(0.01)  # 100Hz update rate
            
    def get_status(self) -> AxisStatus:
        """Get current axis status"""
        with self._lock:
            return self.status
            
    def get_diagnostics(self) -> Dict:
        """Get comprehensive diagnostics"""
        if not self._axis or not self._odrive:
            return {"connected": False}
            
        try:
            return {
                "connected": True,
                "axis_type": self.config.axis_type.value,
                "serial_number": self.config.serial_number,
                "state": self.status.state.value,
                "position": self.status.position,
                "velocity": self.status.velocity,
                "torque": self.status.torque,
                "current": self.status.current,
                "target_position": self.status.target_position,
                "is_homed": self.status.is_homed,
                "vbus_voltage": self._odrive.vbus_voltage,
                "axis_state": self._axis.current_state,
                "errors": self.status.errors,
                "controller_mode": self._axis.controller.config.control_mode,
                "vel_limit": self._axis.trap_traj.config.vel_limit,
            }
        except Exception as e:
            return {"error": str(e)}
            
    # ========================================================================
    # CALIBRATION AND RESET
    # ========================================================================
    
    def calibrate(self) -> bool:
        """
        Run motor calibration sequence
        
        Returns:
            True if calibration successful
        """
        if not self._axis:
            self.logger.error("Not connected to ODrive")
            return False
            
        try:
            self.logger.info("Starting motor calibration...")
            self.status.state = AxisState.CALIBRATING
            
            # Run full calibration
            request_state(self._axis, ODriveAxisState.FULL_CALIBRATION_SEQUENCE)
            
            # Wait for calibration to complete
            start_time = time.time()
            while self._axis.current_state != ODriveAxisState.IDLE:
                if time.time() - start_time > 30:
                    self.logger.error("Calibration timeout")
                    self.status.state = AxisState.ERROR
                    return False
                time.sleep(0.1)
                
            # Check for errors
            if self._axis.error != 0:
                self.logger.error(f"Calibration failed with error: {self._axis.error}")
                dump_errors(self._odrive)
                self.status.state = AxisState.ERROR
                return False
                
            self.logger.info("Calibration successful")
            self.status.state = AxisState.IDLE
            return True
            
        except Exception as e:
            self.logger.error(f"Calibration failed: {e}")
            self.status.state = AxisState.ERROR
            return False
            
    def reset(self):
        """Reset axis and clear errors"""
        if not self._axis:
            return
            
        try:
            self.logger.info("Resetting axis...")
            
            # Clear errors
            try:
                self._axis.clear_errors()
            except AttributeError:
                # Try ODrive-level clear for older firmware
                try:
                    self._odrive.clear_errors()
                except:
                    pass
            
            # Go to idle state
            request_state(self._axis, ODriveAxisState.IDLE)
            
            # Reset status
            self.status.errors.clear()
            self.status.state = AxisState.IDLE
            self.status.target_position = None
            
            self.logger.info("Reset complete")
            
        except Exception as e:
            self.logger.error(f"Reset failed: {e}")
            
    def save_configuration(self):
        """Save current configuration to ODrive"""
        if self._odrive:
            try:
                self._odrive.save_configuration()
                self.logger.info("Configuration saved to ODrive")
            except Exception as e:
                self.logger.error(f"Failed to save configuration: {e}")