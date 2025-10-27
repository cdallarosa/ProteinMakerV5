"""
3-Axis Gantry Controller using multiple ODrive controllers
Provides coordinated control for X, Y, Z axes
"""

import time
import logging
from typing import Optional, Dict, Tuple, List
from dataclasses import dataclass
from enum import Enum
from threading import Thread, Event
from odrive_class import ODriveAxis, AxisConfig, AxisType, AxisState, MotionProfile

logger = logging.getLogger(__name__)


# ============================================================================
# GANTRY SPECIFIC DATA CLASSES
# ============================================================================

class GantryState(Enum):
    """Gantry system states"""
    DISCONNECTED = "disconnected"
    IDLE = "idle"
    HOMING = "homing"
    MOVING = "moving"
    ERROR = "error"
    EMERGENCY_STOP = "emergency_stop"
    

@dataclass
class GantryPosition:
    """3D position in gantry coordinates"""
    x: float = 0.0  # turns or mm
    y: float = 0.0  # turns or mm
    z: float = 0.0  # turns or mm
    
    def __repr__(self):
        return f"Position(X={self.x:.2f}, Y={self.y:.2f}, Z={self.z:.2f})"
    

@dataclass
class GantryConfig:
    """Gantry system configuration"""
    # ODrive serial numbers for each axis
    x_serial: str = ""
    y_serial: str = ""
    z_serial: str = ""
    
    # Axis numbers on each ODrive (0 or 1)
    x_axis_num: int = 0
    y_axis_num: int = 0
    z_axis_num: int = 0
    
    # Mechanical configuration (turns to mm conversion)
    x_turns_per_mm: float = 0.1  # Example: 10 turns = 100mm
    y_turns_per_mm: float = 0.1
    z_turns_per_mm: float = 0.1
    
    # Workspace limits (in mm)
    x_min_mm: float = 0.0
    x_max_mm: float = 300.0
    y_min_mm: float = 0.0
    y_max_mm: float = 300.0
    z_min_mm: float = 0.0
    z_max_mm: float = 150.0
    
    # Default speeds (mm/sec)
    default_xy_speed: float = 50.0
    default_z_speed: float = 30.0
    homing_speed: float = 10.0
    
    # Motor parameters (same for all axes or customize)
    pole_pairs: int = 4
    torque_constant: float = 0.095
    encoder_cpr: int = 3070
    
    # Current limits
    current_soft_max: float = 30.0
    current_hard_max: float = 49.0
    
    # Torque limits
    torque_soft_limit: float = 2.0
    torque_hard_limit: float = 4.0
    homing_torque_threshold: float = 1.5
    

# ============================================================================
# MAIN GANTRY CLASS
# ============================================================================

class Gantry:
    """
    3-Axis Gantry Controller
    
    Coordinates three ODrive axes for XYZ motion control
    """
    
    def __init__(self, config: GantryConfig):
        """
        Initialize gantry controller
        
        Args:
            config: GantryConfig with all parameters
        """
        self.config = config
        self.state = GantryState.DISCONNECTED
        
        # Create axis configurations
        x_config = self._create_axis_config(AxisType.X_AXIS, config.x_serial, config.x_axis_num)
        y_config = self._create_axis_config(AxisType.Y_AXIS, config.y_serial, config.y_axis_num)
        z_config = self._create_axis_config(AxisType.Z_AXIS, config.z_serial, config.z_axis_num)
        
        # Create axis instances
        self.x_axis = ODriveAxis(x_config)
        self.y_axis = ODriveAxis(y_config)
        self.z_axis = ODriveAxis(z_config)
        
        # Current position in mm
        self.position = GantryPosition()
        
        # Homing status
        self.is_homed = False
        
        self.logger = logging.getLogger(f"{__name__}.Gantry")
        
    def _create_axis_config(self, axis_type: AxisType, serial: str, axis_num: int) -> AxisConfig:
        """Create axis configuration from gantry config"""
        
        # Set position limits based on axis type
        if axis_type == AxisType.X_AXIS:
            pos_min = self.config.x_min_mm * self.config.x_turns_per_mm
            pos_max = self.config.x_max_mm * self.config.x_turns_per_mm
            default_speed = self.config.default_xy_speed * self.config.x_turns_per_mm
        elif axis_type == AxisType.Y_AXIS:
            pos_min = self.config.y_min_mm * self.config.y_turns_per_mm
            pos_max = self.config.y_max_mm * self.config.y_turns_per_mm
            default_speed = self.config.default_xy_speed * self.config.y_turns_per_mm
        else:  # Z_AXIS
            pos_min = self.config.z_min_mm * self.config.z_turns_per_mm
            pos_max = self.config.z_max_mm * self.config.z_turns_per_mm
            default_speed = self.config.default_z_speed * self.config.z_turns_per_mm
        
        return AxisConfig(
            serial_number=serial,
            axis_type=axis_type,
            axis_number=axis_num,
            
            # Motor config
            pole_pairs=self.config.pole_pairs,
            torque_constant=self.config.torque_constant,
            encoder_cpr=self.config.encoder_cpr,
            
            # Current limits
            current_soft_max=self.config.current_soft_max,
            current_hard_max=self.config.current_hard_max,
            
            # Torque limits
            torque_soft_limit=self.config.torque_soft_limit,
            torque_hard_limit=self.config.torque_hard_limit,
            homing_torque_threshold=self.config.homing_torque_threshold,
            
            # Position limits in turns
            position_min=pos_min,
            position_max=pos_max,
            
            # Motion profile
            motion_profile=MotionProfile(
                velocity_limit=default_speed,
                acceleration_limit=default_speed,  # Adjust as needed
                deceleration_limit=default_speed,
            ),
            
            # Homing
            homing_velocity=self.config.homing_speed * self.config.x_turns_per_mm,
            homing_backoff_turns=0.5,
        )
        
    # ========================================================================
    # CONNECTION MANAGEMENT
    # ========================================================================
    
    def connect(self) -> bool:
        """
        Connect to all three ODrive controllers
        
        Returns:
            True if all axes connected successfully
        """
        try:
            self.logger.info("Connecting to gantry axes...")
            
            # Connect to each axis
            if not self.x_axis.connect():
                self.logger.error("Failed to connect to X axis")
                return False
                
            if not self.y_axis.connect():
                self.logger.error("Failed to connect to Y axis")
                self.x_axis.disconnect()
                return False
                
            if not self.z_axis.connect():
                self.logger.error("Failed to connect to Z axis")
                self.x_axis.disconnect()
                self.y_axis.disconnect()
                return False
                
            self.state = GantryState.IDLE
            self.logger.info("All axes connected successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Connection failed: {e}")
            self.disconnect()
            return False
            
    def disconnect(self):
        """Disconnect all axes"""
        self.logger.info("Disconnecting gantry...")
        self.x_axis.disconnect()
        self.y_axis.disconnect()
        self.z_axis.disconnect()
        self.state = GantryState.DISCONNECTED
        self.is_homed = False
        
    # ========================================================================
    # HOMING
    # ========================================================================
    
    def home_all(self, home_order: List[str] = ["z", "x", "y"]) -> bool:
        """
        Home all axes in specified order
        
        Args:
            home_order: List specifying order to home axes
            
        Returns:
            True if all axes homed successfully
        """
        self.logger.info(f"Homing gantry in order: {home_order}")
        self.state = GantryState.HOMING
        
        axis_map = {
            "x": self.x_axis,
            "y": self.y_axis,
            "z": self.z_axis
        }
        
        try:
            for axis_name in home_order:
                axis = axis_map.get(axis_name.lower())
                if not axis:
                    self.logger.error(f"Invalid axis name: {axis_name}")
                    continue
                    
                self.logger.info(f"Homing {axis_name.upper()} axis...")
                
                # Z axis typically homes upward (positive)
                direction = 1 if axis_name.lower() == "z" else -1
                
                if not axis.home(direction=direction):
                    self.logger.error(f"Failed to home {axis_name.upper()} axis")
                    self.state = GantryState.ERROR
                    return False
                    
            # Update position to home
            self.position = GantryPosition(0.0, 0.0, 0.0)
            self.is_homed = True
            self.state = GantryState.IDLE
            self.logger.info("Gantry homing complete")
            return True
            
        except Exception as e:
            self.logger.error(f"Homing failed: {e}")
            self.state = GantryState.ERROR
            return False
            
    def home_axis(self, axis_name: str) -> bool:
        """Home a single axis"""
        axis_map = {
            "x": self.x_axis,
            "y": self.y_axis,
            "z": self.z_axis
        }
        
        axis = axis_map.get(axis_name.lower())
        if not axis:
            self.logger.error(f"Invalid axis name: {axis_name}")
            return False
            
        direction = 1 if axis_name.lower() == "z" else -1
        return axis.home(direction=direction)
        
    # ========================================================================
    # MOTION CONTROL
    # ========================================================================
    
    def move_to(self, x: Optional[float] = None, y: Optional[float] = None, 
                z: Optional[float] = None, speed: Optional[float] = None) -> bool:
        """
        Move to absolute position (in mm)
        
        Args:
            x, y, z: Target positions in mm (None to keep current position)
            speed: Movement speed in mm/sec
            
        Returns:
            True if move started successfully
        """
        if not self.is_homed:
            self.logger.warning("Gantry not homed - positions may be incorrect")
            
        try:
            self.state = GantryState.MOVING
            moves_started = []
            
            # Start X move
            if x is not None:
                x_turns = x * self.config.x_turns_per_mm
                x_speed = (speed * self.config.x_turns_per_mm) if speed else None
                if self.x_axis.move_to_position(x_turns, x_speed):
                    moves_started.append("X")
                    
            # Start Y move
            if y is not None:
                y_turns = y * self.config.y_turns_per_mm
                y_speed = (speed * self.config.y_turns_per_mm) if speed else None
                if self.y_axis.move_to_position(y_turns, y_speed):
                    moves_started.append("Y")
                    
            # Start Z move
            if z is not None:
                z_turns = z * self.config.z_turns_per_mm
                z_speed = (speed * self.config.z_turns_per_mm) if speed else None
                if self.z_axis.move_to_position(z_turns, z_speed):
                    moves_started.append("Z")
                    
            if moves_started:
                self.logger.info(f"Started moves on axes: {moves_started}")
                return True
            else:
                self.logger.warning("No moves started")
                self.state = GantryState.IDLE
                return False
                
        except Exception as e:
            self.logger.error(f"Move failed: {e}")
            self.state = GantryState.ERROR
            return False
            
    def move_relative(self, dx: float = 0, dy: float = 0, dz: float = 0, 
                     speed: Optional[float] = None) -> bool:
        """
        Move relative to current position (in mm)
        
        Args:
            dx, dy, dz: Relative distances in mm
            speed: Movement speed in mm/sec
            
        Returns:
            True if move started successfully
        """
        current = self.get_position()
        return self.move_to(
            x=current.x + dx if dx != 0 else None,
            y=current.y + dy if dy != 0 else None,
            z=current.z + dz if dz != 0 else None,
            speed=speed
        )
        
    def wait_for_moves(self, timeout: float = 60.0) -> bool:
        """
        Wait for all axes to complete their moves
        
        Args:
            timeout: Maximum time to wait in seconds
            
        Returns:
            True if all moves completed successfully
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            # Check if all axes are idle or completed
            x_moving = self.x_axis.status.state == AxisState.MOVING
            y_moving = self.y_axis.status.state == AxisState.MOVING
            z_moving = self.z_axis.status.state == AxisState.MOVING
            
            if not (x_moving or y_moving or z_moving):
                # Check for errors
                if (self.x_axis.status.state == AxisState.ERROR or
                    self.y_axis.status.state == AxisState.ERROR or
                    self.z_axis.status.state == AxisState.ERROR):
                    self.logger.error("One or more axes in error state")
                    self.state = GantryState.ERROR
                    return False
                    
                self.state = GantryState.IDLE
                return True
                
            time.sleep(0.05)
            
        self.logger.error("Move timeout")
        self.stop()
        return False
        
    def stop(self, emergency: bool = False):
        """
        Stop all axes
        
        Args:
            emergency: If True, immediate stop; if False, decelerated stop
        """
        self.logger.info(f"{'Emergency' if emergency else 'Normal'} stop initiated")
        
        self.x_axis.stop(emergency)
        self.y_axis.stop(emergency)
        self.z_axis.stop(emergency)
        
        self.state = GantryState.EMERGENCY_STOP if emergency else GantryState.IDLE
        
    # ========================================================================
    # STATUS AND POSITION
    # ========================================================================
    
    def get_position(self) -> GantryPosition:
        """Get current position in mm"""
        x_mm = self.x_axis.status.position / self.config.x_turns_per_mm
        y_mm = self.y_axis.status.position / self.config.y_turns_per_mm
        z_mm = self.z_axis.status.position / self.config.z_turns_per_mm
        
        self.position = GantryPosition(x_mm, y_mm, z_mm)
        return self.position
        
    def get_status(self) -> Dict:
        """Get comprehensive gantry status"""
        position = self.get_position()
        
        return {
            "state": self.state.value,
            "is_homed": self.is_homed,
            "position": {
                "x": position.x,
                "y": position.y,
                "z": position.z
            },
            "axes": {
                "x": {
                    "state": self.x_axis.status.state.value,
                    "position": position.x,
                    "torque": self.x_axis.status.torque,
                    "velocity": self.x_axis.status.velocity / self.config.x_turns_per_mm
                },
                "y": {
                    "state": self.y_axis.status.state.value,
                    "position": position.y,
                    "torque": self.y_axis.status.torque,
                    "velocity": self.y_axis.status.velocity / self.config.y_turns_per_mm
                },
                "z": {
                    "state": self.z_axis.status.state.value,
                    "position": position.z,
                    "torque": self.z_axis.status.torque,
                    "velocity": self.z_axis.status.velocity / self.config.z_turns_per_mm
                }
            }
        }
        
    def is_moving(self) -> bool:
        """Check if any axis is currently moving"""
        return (self.x_axis.status.state == AxisState.MOVING or
                self.y_axis.status.state == AxisState.MOVING or
                self.z_axis.status.state == AxisState.MOVING)
                
    def reset_all(self):
        """Reset all axes and clear errors"""
        self.x_axis.reset()
        self.y_axis.reset()
        self.z_axis.reset()
        self.state = GantryState.IDLE
        
    # ========================================================================
    # COORDINATED MOVES
    # ========================================================================
    
    def move_linear(self, target: GantryPosition, speed: float) -> bool:
        """
        Coordinated linear move to target position
        Adjusts individual axis speeds to arrive simultaneously
        
        Args:
            target: Target position in mm
            speed: Linear speed in mm/sec
            
        Returns:
            True if move started successfully
        """
        current = self.get_position()
        
        # Calculate distances
        dx = target.x - current.x
        dy = target.y - current.y
        dz = target.z - current.z
        
        # Calculate total distance
        distance = (dx**2 + dy**2 + dz**2) ** 0.5
        
        if distance < 0.01:  # Already at position
            return True
            
        # Calculate time to complete move
        move_time = distance / speed
        
        # Calculate individual axis speeds to arrive simultaneously
        x_speed = abs(dx) / move_time if dx != 0 else 0
        y_speed = abs(dy) / move_time if dy != 0 else 0
        z_speed = abs(dz) / move_time if dz != 0 else 0
        
        # Start moves with calculated speeds
        success = True
        if dx != 0:
            x_turns = target.x * self.config.x_turns_per_mm
            x_vel = x_speed * self.config.x_turns_per_mm
            success &= self.x_axis.move_to_position(x_turns, x_vel)
            
        if dy != 0:
            y_turns = target.y * self.config.y_turns_per_mm
            y_vel = y_speed * self.config.y_turns_per_mm
            success &= self.y_axis.move_to_position(y_turns, y_vel)
            
        if dz != 0:
            z_turns = target.z * self.config.z_turns_per_mm
            z_vel = z_speed * self.config.z_turns_per_mm
            success &= self.z_axis.move_to_position(z_turns, z_vel)
            
        if success:
            self.state = GantryState.MOVING
            self.logger.info(f"Linear move to {target} at {speed} mm/sec")
            
        return success
        
    def jog(self, axis: str, distance: float, speed: Optional[float] = None):
        """
        Jog a single axis
        
        Args:
            axis: 'x', 'y', or 'z'
            distance: Distance to jog in mm (positive or negative)
            speed: Jog speed in mm/sec
        """
        if axis.lower() == 'x':
            self.move_relative(dx=distance, speed=speed)
        elif axis.lower() == 'y':
            self.move_relative(dy=distance, speed=speed)
        elif axis.lower() == 'z':
            self.move_relative(dz=distance, speed=speed)
        else:
            self.logger.error(f"Invalid axis: {axis}")