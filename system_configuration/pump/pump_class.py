"""
Cavro XLP 6000 Syringe Pump - Improved Hardware Interface
Complete pump control with proper device verification and error handling
"""

import serial
import serial.tools.list_ports
import time
import logging
from datetime import datetime
from collections import deque
from typing import Optional, Dict, Tuple, List, Union
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS AND DATA CLASSES
# ============================================================================

class PumpState(Enum):
    """Pump operational states"""
    DISCONNECTED = "disconnected"
    IDLE = "idle"
    BUSY = "busy"
    ERROR = "error"
    INITIALIZING = "initializing"
    ASPIRATING = "aspirating"
    DISPENSING = "dispensing"
    MOVING = "moving"


class ValvePosition(Enum):
    """Standard valve positions"""
    INPUT_1 = 1
    INPUT_2 = 2
    INPUT_3 = 3
    INPUT_4 = 4
    INPUT_5 = 5
    INPUT_6 = 6
    INPUT_7 = 7
    INPUT_8 = 8
    INPUT_9 = 9
    INPUT_10 = 10
    BYPASS = 11
    OUTPUT = 12


@dataclass
class PumpConfig:
    """Pump configuration parameters"""
    port: str = "COM12"
    address: int = 1
    baudrate: int = 9600
    syringe_size_ml: float = 1.0
    max_steps: int = 6000
    default_speed: int = 2000
    timeout: float = 2.0
    retry_attempts: int = 3


@dataclass
class CommandResponse:
    """Response from pump command"""
    success: bool
    raw_response: str
    parsed_data: Optional[Dict] = None
    error_message: Optional[str] = None


# ============================================================================
# MAIN PUMP CLASS
# ============================================================================

class Pump:
    """
    Enhanced XLP 6000 Syringe Pump Interface
    
    Features:
    - Proper device verification on connection
    - Complete valve control
    - Robust error handling and retry logic
    - State machine implementation
    - Comprehensive status monitoring
    """
    
    # Syringe size options (in mL)
    SYRINGE_SIZES = {
        '50uL': 0.05,
        '100uL': 0.1,
        '250uL': 0.25,
        '500uL': 0.5,
        '1mL': 1.0,
        '5mL': 5.0,
        '10mL': 10.0,
        '25mL': 25.0,
        '50mL': 50.0,
    }
    
    def __init__(self, config: Optional[PumpConfig] = None):
        """
        Initialize pump with configuration
        
        Args:
            config: Pump configuration object (uses defaults if None)
        """
        self.config = config or PumpConfig()
        
        # Connection management
        self.serial_connection: Optional[serial.Serial] = None
        self.state = PumpState.DISCONNECTED
        
        # Position tracking
        self.current_position = 0
        self.target_position = 0
        self.current_valve = ValvePosition.OUTPUT
        
        # Speed settings
        self.speed_settings = {
            'start': 50,
            'top': 6000,
            'cutoff': 50,
            'current': self.config.default_speed
        }
        
        # Operation tracking
        self.command_history = deque(maxlen=100)
        self.errors = []
        self.last_command_time = None
        self.operation_start_time = None
        
    # ========================================================================
    # CONNECTION MANAGEMENT
    # ========================================================================
    
    def connect(self, verify_device: bool = True) -> bool:
        """
        Connect to pump and verify device response
        
        Args:
            verify_device: If True, verify pump responds correctly
            
        Returns:
            bool: True if connection and verification successful
        """
        try:
            # Close existing connection if any
            if self.serial_connection and self.serial_connection.is_open:
                self.serial_connection.close()
            
            logger.info(f"Connecting to {self.config.port} at {self.config.baudrate} baud...")
            
            # Establish serial connection
            self.serial_connection = serial.Serial(
                port=self.config.port,
                baudrate=self.config.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=self.config.timeout,
                write_timeout=self.config.timeout
            )
            
            # Wait for connection to stabilize
            time.sleep(0.2)
            
            # Clear any pending data
            self.serial_connection.reset_input_buffer()
            self.serial_connection.reset_output_buffer()
            
            if verify_device:
                # Verify pump responds correctly
                logger.info("Verifying device communication...")
                
                # Send status query to verify pump is responding
                response = self._send_command("Q", retry_on_fail=False)
                
                if response.success:
                    logger.info(f"Device verified - Response: {repr(response.raw_response)}")
                    self.state = PumpState.IDLE
                    
                    # Parse initial status
                    status = self._parse_status(response.raw_response)
                    if status['position'] is not None:
                        self.current_position = status['position']
                        logger.info(f"Current pump position: {self.current_position}")
                    
                    logger.info(f"✓ Successfully connected to XLP 6000 on {self.config.port}")
                    return True
                else:
                    logger.error(f"Device verification failed - No valid response from pump")
                    self.disconnect()
                    return False
            else:
                # Skip verification
                self.state = PumpState.IDLE
                logger.info(f"Connected to {self.config.port} (verification skipped)")
                return True
                
        except serial.SerialException as e:
            logger.error(f"Serial connection failed: {e}")
            self.errors.append(f"Connection error: {e}")
            self.state = PumpState.ERROR
            return False
        except Exception as e:
            logger.error(f"Unexpected error during connection: {e}")
            self.errors.append(f"Unexpected error: {e}")
            self.state = PumpState.ERROR
            return False
    
    def disconnect(self):
        """Safely disconnect from pump"""
        if self.serial_connection and self.serial_connection.is_open:
            try:
                self.serial_connection.close()
                logger.info("Disconnected from pump")
            except Exception as e:
                logger.error(f"Error during disconnect: {e}")
        
        self.serial_connection = None
        self.state = PumpState.DISCONNECTED
    
    def is_connected(self) -> bool:
        """Check if pump is connected and responsive"""
        if not self.serial_connection or not self.serial_connection.is_open:
            return False
        
        # Try to query status
        response = self._send_command("Q", retry_on_fail=False)
        return response.success
    
    # ========================================================================
    # LOW-LEVEL COMMUNICATION
    # ========================================================================
    
    def _send_command(self, command: str, retry_on_fail: bool = True) -> CommandResponse:
        """
        Send command to pump with optional retry logic
        
        Args:
            command: Command string (without address or termination)
            retry_on_fail: Whether to retry on failure
            
        Returns:
            CommandResponse object with results
        """
        if not self.serial_connection or not self.serial_connection.is_open:
            return CommandResponse(
                success=False,
                raw_response="",
                error_message="Not connected to pump"
            )
        
        # Format command with address and termination
        full_command = f"/{self.config.address}{command}\r"
        
        # Log command
        self._log_command(command, full_command)
        
        attempts = self.config.retry_attempts if retry_on_fail else 1
        
        for attempt in range(attempts):
            try:
                # Clear buffers before sending
                self.serial_connection.reset_input_buffer()
                
                # Send command
                self.serial_connection.write(full_command.encode('ascii'))
                
                # Wait for response
                time.sleep(0.1)  # Give pump time to process
                
                # Read response
                response_bytes = self.serial_connection.read(self.serial_connection.in_waiting or 1)
                
                if response_bytes:
                    raw_response = response_bytes.decode('ascii', errors='replace')
                    
                    # Check for valid response format
                    if self._is_valid_response(raw_response):
                        return CommandResponse(
                            success=True,
                            raw_response=raw_response
                        )
                    elif attempt < attempts - 1:
                        logger.warning(f"Invalid response on attempt {attempt + 1}: {repr(raw_response)}")
                        time.sleep(0.5)  # Wait before retry
                        continue
                    else:
                        return CommandResponse(
                            success=False,
                            raw_response=raw_response,
                            error_message="Invalid response format"
                        )
                else:
                    if attempt < attempts - 1:
                        logger.warning(f"No response on attempt {attempt + 1}")
                        time.sleep(0.5)
                        continue
                    else:
                        return CommandResponse(
                            success=False,
                            raw_response="",
                            error_message="No response from pump"
                        )
                        
            except Exception as e:
                logger.error(f"Command error on attempt {attempt + 1}: {e}")
                if attempt >= attempts - 1:
                    return CommandResponse(
                        success=False,
                        raw_response="",
                        error_message=str(e)
                    )
        
        return CommandResponse(
            success=False,
            raw_response="",
            error_message="All retry attempts failed"
        )
    
    def _is_valid_response(self, response: str) -> bool:
        """Check if response appears valid"""
        if not response:
            return False
        
        # Response should contain address and status indicator
        # Valid indicators: ` (idle), @ (busy), or error codes
        return any(char in response for char in ['`', '@', '?', '!'])
    
    def _log_command(self, command: str, full_command: str):
        """Log command to history"""
        self.command_history.append({
            'timestamp': datetime.now().isoformat(),
            'command': command,
            'full_command': full_command
        })
        self.last_command_time = time.time()
    
    # ========================================================================
    # INITIALIZATION AND SETUP
    # ========================================================================
    
    def initialize(self, command: str = "ZR", wait: bool = True, timeout: float = 30) -> bool:
        """
        Initialize pump (find home position)
        
        Args:
            command: Initialization command (ZR = initialize with valve rotation)
            wait: Wait for completion
            timeout: Maximum wait time
            
        Returns:
            bool: True if successful
        """
        logger.info(f"Initializing pump with command: {command}")
        self.state = PumpState.INITIALIZING
        
        response = self._send_command(command)
        
        if not response.success:
            logger.error(f"Initialization failed: {response.error_message}")
            self.state = PumpState.ERROR
            return False
        
        if wait:
            if self.wait_until_ready(timeout):
                self.current_position = 0
                self.state = PumpState.IDLE
                logger.info("Pump initialized successfully")
                return True
            else:
                logger.error("Initialization timeout")
                self.state = PumpState.ERROR
                return False
        else:
            return True
    
    def set_syringe_size(self, size_ml: float) -> bool:
        """
        Set syringe size
        
        Args:
            size_ml: Syringe size in mL
            
        Returns:
            bool: True if successful
        """
        if size_ml not in self.SYRINGE_SIZES.values():
            logger.warning(f"Non-standard syringe size: {size_ml} mL")
        
        self.config.syringe_size_ml = size_ml
        logger.info(f"Syringe size set to {size_ml} mL")
        return True
    
    # ========================================================================
    # VALVE CONTROL
    # ========================================================================
    
    def set_valve_position(self, position: Union[ValvePosition, int], wait: bool = False) -> bool:
        """
        Set valve to specified position
        
        Args:
            position: Valve position (ValvePosition enum or integer 1-12)
            wait: Wait for valve movement to complete
            
        Returns:
            bool: True if successful
        """
        if isinstance(position, ValvePosition):
            pos_value = position.value
        else:
            pos_value = int(position)
        
        if not 1 <= pos_value <= 12:
            logger.error(f"Invalid valve position: {pos_value}")
            return False
        
        # Determine valve command based on position
        if pos_value <= 10:
            # Input positions 1-10
            command = f"I{pos_value}R"
        elif pos_value == 11:
            # Bypass position
            command = "BR"
        else:
            # Output position (12)
            command = "OR"
        
        logger.info(f"Setting valve to position {pos_value}")
        response = self._send_command(command)
        
        if response.success:
            self.current_valve = ValvePosition(pos_value)
            
            if wait:
                time.sleep(0.5)  # Typical valve rotation time
                
            return True
        else:
            logger.error(f"Failed to set valve position: {response.error_message}")
            return False
    
    def valve_input(self, input_number: int) -> bool:
        """Set valve to input position (1-10)"""
        return self.set_valve_position(input_number)
    
    def valve_output(self) -> bool:
        """Set valve to output position"""
        return self.set_valve_position(ValvePosition.OUTPUT)
    
    def valve_bypass(self) -> bool:
        """Set valve to bypass position"""
        return self.set_valve_position(ValvePosition.BYPASS)
    
    # ========================================================================
    # SYRINGE MOVEMENT
    # ========================================================================
    
    def move_absolute(self, position: int, wait: bool = True, timeout: float = 30) -> bool:
        """
        Move syringe to absolute position
        
        Args:
            position: Target position (0 to max_steps)
            wait: Wait for movement to complete
            timeout: Maximum wait time
            
        Returns:
            bool: True if successful
        """
        if not 0 <= position <= self.config.max_steps:
            logger.error(f"Invalid position: {position} (must be 0-{self.config.max_steps})")
            return False
        
        command = f"A{position}R"
        logger.info(f"Moving to absolute position {position}")
        self.state = PumpState.MOVING
        
        response = self._send_command(command)
        
        if not response.success:
            logger.error(f"Move command failed: {response.error_message}")
            self.state = PumpState.ERROR
            return False
        
        self.target_position = position
        
        if wait:
            if self.wait_until_ready(timeout):
                self.current_position = position
                self.state = PumpState.IDLE
                return True
            else:
                self.state = PumpState.ERROR
                return False
        else:
            return True
    
    def move_relative(self, steps: int, wait: bool = True, timeout: float = 30) -> bool:
        """
        Move syringe relative to current position
        
        Args:
            steps: Number of steps to move (positive or negative)
            wait: Wait for movement to complete
            timeout: Maximum wait time
            
        Returns:
            bool: True if successful
        """
        new_position = self.current_position + steps
        return self.move_absolute(new_position, wait, timeout)
    
    def home(self, wait: bool = True) -> bool:
        """Move syringe to home position (0)"""
        return self.move_absolute(0, wait)
    
    # ========================================================================
    # ASPIRATION AND DISPENSING
    # ========================================================================
    
    def aspirate(self, volume_ul: float, inlet_valve: Optional[int] = None, 
                 speed: Optional[int] = None, wait: bool = True) -> bool:
        """
        Aspirate specified volume
        
        Args:
            volume_ul: Volume in microliters
            inlet_valve: Inlet valve position (1-10, None to use current)
            speed: Aspiration speed (steps/sec, None for default)
            wait: Wait for completion
            
        Returns:
            bool: True if successful
        """
        # Calculate steps
        steps = self._volume_to_steps(volume_ul)
        
        if steps > (self.config.max_steps - self.current_position):
            logger.error(f"Cannot aspirate {volume_ul}µL - insufficient syringe capacity")
            return False
        
        # Set valve if specified
        if inlet_valve is not None:
            if not self.valve_input(inlet_valve):
                return False
            time.sleep(0.2)  # Wait for valve
        
        # Set speed if specified
        if speed is not None:
            self._set_speed(speed)
        
        # Calculate target position
        target = self.current_position + steps
        
        logger.info(f"Aspirating {volume_ul}µL from valve {inlet_valve or self.current_valve.value}")
        self.state = PumpState.ASPIRATING
        
        # Execute aspiration
        return self.move_absolute(target, wait)
    
    def dispense(self, volume_ul: float, outlet_valve: Optional[int] = None,
                 speed: Optional[int] = None, wait: bool = True) -> bool:
        """
        Dispense specified volume
        
        Args:
            volume_ul: Volume in microliters
            outlet_valve: Outlet valve position (11-12, None to use current)
            speed: Dispense speed (steps/sec, None for default)
            wait: Wait for completion
            
        Returns:
            bool: True if successful
        """
        # Calculate steps
        steps = self._volume_to_steps(volume_ul)
        
        if steps > self.current_position:
            logger.error(f"Cannot dispense {volume_ul}µL - insufficient volume in syringe")
            return False
        
        # Set valve if specified
        if outlet_valve is not None:
            if outlet_valve == 12:
                self.valve_output()
            elif outlet_valve == 11:
                self.valve_bypass()
            else:
                logger.error(f"Invalid outlet valve: {outlet_valve} (use 11 or 12)")
                return False
            time.sleep(0.2)  # Wait for valve
        
        # Set speed if specified
        if speed is not None:
            self._set_speed(speed)
        
        # Calculate target position
        target = self.current_position - steps
        
        logger.info(f"Dispensing {volume_ul}µL to valve {outlet_valve or self.current_valve.value}")
        self.state = PumpState.DISPENSING
        
        # Execute dispensing
        return self.move_absolute(target, wait)
    
    def empty_syringe(self, outlet_valve: int = 12, wait: bool = True) -> bool:
        """Empty entire syringe contents"""
        if outlet_valve:
            self.set_valve_position(outlet_valve)
        return self.move_absolute(0, wait)
    
    # ========================================================================
    # CONTINUOUS OPERATIONS
    # ========================================================================
    
    def continuous_pump(self, volume_ul: float, flowrate_ul_min: float,
                       inlet: int, outlet: int, wait: bool = False) -> bool:
        """
        Execute continuous pumping operation
        
        Args:
            volume_ul: Total volume to pump (microliters)
            flowrate_ul_min: Flow rate (microliters per minute)
            inlet: Inlet valve position (1-10)
            outlet: Outlet valve position (11-12)
            wait: Wait for completion
            
        Returns:
            bool: True if command sent successfully
        """
        # Calculate required steps and rates
        total_steps = self._volume_to_steps(volume_ul)
        steps_per_sec = self._flowrate_to_speed(flowrate_ul_min)
        
        # Determine number of cycles needed
        cycles = total_steps // self.config.max_steps
        remaining = total_steps % self.config.max_steps
        
        logger.info(f"Continuous pump: {volume_ul}µL @ {flowrate_ul_min}µL/min")
        logger.info(f"Cycles: {cycles}, Remaining: {remaining} steps")
        
        # Build command string for continuous operation
        # Format: V[asp_speed]I[valve]A[steps]O[valve]V[disp_speed]A0G[cycles]R
        
        if cycles > 0:
            # Multi-cycle operation
            command = f"V{self.config.default_speed}I{inlet}A{self.config.max_steps}"
            command += f"O{outlet if outlet <= 10 else ''}V{steps_per_sec}A0"
            
            if outlet == 11:
                command = command.replace(f"O{outlet}", "B")
            elif outlet == 12:
                command = command.replace(f"O{outlet}", "O")
            
            command += f"G{cycles}R"
            
            response = self._send_command(command)
            
            if not response.success:
                logger.error(f"Continuous pump failed: {response.error_message}")
                return False
            
            # Handle remaining volume if any
            if remaining > 0 and wait:
                self.wait_until_ready(timeout=cycles * 60)  # Rough estimate
                
                # Pump remaining
                self.valve_input(inlet)
                self.aspirate(self._steps_to_volume(remaining), wait=True)
                self.set_valve_position(outlet)
                self.dispense(self._steps_to_volume(remaining), wait=True)
        else:
            # Single operation
            self.valve_input(inlet)
            self.aspirate(volume_ul, speed=self.config.default_speed, wait=True)
            self.set_valve_position(outlet)
            self.dispense(volume_ul, speed=steps_per_sec, wait=wait)
        
        return True
    
    # ========================================================================
    # SPEED CONTROL
    # ========================================================================
    
    def set_speed_profile(self, start: int, top: int, cutoff: int) -> bool:
        """
        Set pump speed profile
        
        Args:
            start: Starting speed (steps/sec)
            top: Maximum speed (steps/sec)
            cutoff: Ending speed (steps/sec)
            
        Returns:
            bool: True if successful
        """
        command = f"v{start}V{top}c{cutoff}R"
        response = self._send_command(command)
        
        if response.success:
            self.speed_settings.update({
                'start': start,
                'top': top,
                'cutoff': cutoff
            })
            logger.info(f"Speed profile set: start={start}, top={top}, cutoff={cutoff}")
            return True
        else:
            logger.error(f"Failed to set speed profile: {response.error_message}")
            return False
    
    def _set_speed(self, speed: int) -> bool:
        """Set pump speed for next operation"""
        command = f"V{speed}R"
        response = self._send_command(command)
        
        if response.success:
            self.speed_settings['current'] = speed
            return True
        return False
    
    # ========================================================================
    # STATUS AND MONITORING
    # ========================================================================
    
    def get_status(self) -> Dict:
        """
        Get comprehensive pump status
        
        Returns:
            dict: Status information
        """
        response = self._send_command("Q")
        
        status = {
            'connected': self.is_connected(),
            'state': self.state.value,
            'position': self.current_position,
            'valve': self.current_valve.value if self.current_valve else None,
            'syringe_size_ml': self.config.syringe_size_ml,
            'raw_response': response.raw_response if response.success else None
        }
        
        if response.success:
            parsed = self._parse_status(response.raw_response)
            status.update(parsed)
        
        return status
    
    def _parse_status(self, response: str) -> Dict:
        """Parse status response from pump"""
        status = {
            'is_busy': False,
            'is_idle': False,
            'position': None,
            'error': None
        }
        
        if not response:
            status['error'] = 'No response'
            return status
        
        # Clean response
        clean = ''.join(c for c in response if 32 <= ord(c) <= 126)
        
        # Check status indicators
        if '`' in clean:
            status['is_idle'] = True
            self.state = PumpState.IDLE
        elif '@' in clean:
            status['is_busy'] = True
            # Keep current operational state
        else:
            status['error'] = f'Unknown status: {repr(clean)}'
        
        # Extract position
        digits = ''.join(c for c in clean if c.isdigit())
        if digits:
            try:
                status['position'] = int(digits)
            except ValueError:
                pass
        
        return status
    
    def wait_until_ready(self, timeout: float = 30, poll_interval: float = 0.5) -> bool:
        """
        Wait until pump is ready (idle)
        
        Args:
            timeout: Maximum wait time in seconds
            poll_interval: Time between status checks
            
        Returns:
            bool: True if pump became ready, False if timeout
        """
        start_time = time.time()
        
        while (time.time() - start_time) < timeout:
            status = self.get_status()
            
            if status.get('is_idle'):
                return True
            
            time.sleep(poll_interval)
        
        logger.warning(f"Timeout waiting for pump ready ({timeout}s)")
        return False
    
    def is_ready(self) -> bool:
        """Check if pump is ready for new commands"""
        status = self.get_status()
        return status.get('is_idle', False)
    
    # ========================================================================
    # CONTROL COMMANDS
    # ========================================================================
    
    def stop(self) -> bool:
        """Emergency stop - terminate current operation"""
        logger.warning("Sending STOP command")
        response = self._send_command("T")
        
        if response.success:
            self.state = PumpState.IDLE
            return True
        return False
    
    def pause(self) -> bool:
        """Pause current operation"""
        response = self._send_command("H")
        return response.success
    
    def resume(self) -> bool:
        """Resume paused operation"""
        response = self._send_command("R")
        return response.success
    
    # ========================================================================
    # UTILITY METHODS
    # ========================================================================
    
    def _volume_to_steps(self, volume_ul: float) -> int:
        """Convert volume in microliters to pump steps"""
        volume_ml = volume_ul / 1000
        fraction = volume_ml / self.config.syringe_size_ml
        steps = int(fraction * self.config.max_steps)
        return min(steps, self.config.max_steps)
    
    def _steps_to_volume(self, steps: int) -> float:
        """Convert pump steps to volume in microliters"""
        fraction = steps / self.config.max_steps
        volume_ml = fraction * self.config.syringe_size_ml
        return volume_ml * 1000
    
    def _flowrate_to_speed(self, flowrate_ul_min: float) -> int:
        """Convert flow rate (µL/min) to pump speed (steps/sec)"""
        flowrate_ml_sec = (flowrate_ul_min / 1000) / 60
        steps_per_sec = (flowrate_ml_sec / self.config.syringe_size_ml) * self.config.max_steps
        return int(steps_per_sec)
    
    def get_command_history(self, limit: int = 10) -> List[Dict]:
        """Get recent command history"""
        history = list(self.command_history)
        return history[-limit:] if len(history) > limit else history
    
    def clear_errors(self):
        """Clear error list"""
        self.errors.clear()
        if self.state == PumpState.ERROR:
            self.state = PumpState.IDLE