"""
XLP6000 Syringe Pump - Core Hardware Interface
Handles basic pump communication and control operations
"""

import serial
import serial.tools.list_ports
import time
from datetime import datetime
from collections import deque
import logging

logger = logging.getLogger(__name__)



class Pump:
    """
    Core XLP 6000 Syringe Pump Interface

    Provides low-level hardware control
    For advanced operations (continuous pumping, gradients, etc.), use PumpProcessController.
    """

    def __init__(self):
        # Serial connection
        self.serial_connection = None
        self.is_connected = False
        self.port = "COM12"  # Default port, change as needed
        self.address = 1
        self.baud_rate = 9600



        # Syringe Configuration
        self.syringe_type = {
            '50 uL': 0.05,
            '100 uL': 0.1,
            '250 uL': 0.25,
            '500 uL': 0.5,
            '1 mL': 1.0,
            '5 mL': 5.0,
            '10 mL': 10.0,
            '25 mL': 25.0,
            '50 mL': 50.0,
        }
        self.syringe_size = self.syringe_type['1 mL']  # Default syringe size in mL
        self.max_position = 6000  # Max position in increments (depends on syringe size)


        # Valve Configuration
        self.valve_position = {
            "I1": 1,
            "I2": 2,
            "I3": 3,
            "I4": 4,
            "I5": 5,
            "I6": 6,
            "I7": 7,
            "I8": 8,
            "I9": 9,
            "I10": 10,
            "B": 11,
            "O": 12,
        }

        # Pump state
        self.current_position = 0
        self.target_position = 0

        # Speed settings
        self.speed_settings = {
            'start_speed': 50,
            'top_speed': 6000,
            'cutoff_speed': 50
        }
        self.aspirate_speed = 2000  # Default aspirate speed (steps/sec)
        self.dispense_speed = 2000  # Default dispense speed (steps/sec)

        self.max_flowrate = self.syringe_size * self.speed_settings['top_speed']

        # Command history and status
        self.command_history = deque(maxlen=100)
        self.status = "Disconnected"
        self.errors = []

    def connect(self):
        """
        Connect to XLP 6000 pump

        Args:


        Returns:
            bool: True if connection successful
        """
        try:
            print(f"Attempting to connect to {self.port} at {self.baud_rate} baud...")
            self.serial_connection = serial.Serial(
                port=self.port,
                baudrate=self.baud_rate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=2,
                write_timeout=2
            )

            # Give the connection time to stabilize
            time.sleep(0.1)

            self.is_connected = True
            self.status = "Connected"
            logger.info(f"Connected to XLP 6000 on {self.port}")
            print(f"✓ Connected successfully to {self.port}")

            return True

        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            print(f"✗ Connection failed: {e}")
            self.is_connected = False
            self.status = f"Connection Error: {e}"
            self.errors.append(str(e))
            return False

    def check_connection(self):
        """Check if pump connection is still alive"""
        if not self.serial_connection:
            return False
        if not self.serial_connection.is_open:
            self.is_connected = False
            return False
        return self.is_connected

    def disconnect(self):
        """Disconnect from pump"""
        if self.serial_connection and self.serial_connection.is_open:
            self.serial_connection.close()
        self.is_connected = False
        self.status = "Disconnected"
        logger.info("Disconnected from XLP 6000")

    def initialize_pump(self, command="ZR", wait=True, timeout=30):
        """
        Initialize the pump with specified command

        Args:
            command: Initialization command (default "ZR")
            wait: If True, wait until pump is ready before returning (default True)
            timeout: Maximum time to wait in seconds if wait=True (default 30)

        Returns:
            bool: True if successful (and ready if wait=True)
        """
        print(f"🔧 Initializing pump with command: {command}")
        logger.info(f"Initializing pump with command: {command}")

        result = self.send_command(command)
        time.sleep(1)  # Brief wait for initialization to start

        if result:
            if wait:
                logger.info(f"Waiting for pump initialization to complete...")
                ready = self.wait_until_ready(timeout=timeout)
                if ready:
                    print("✓ Pump initialized successfully")
                    logger.info("Pump initialized successfully")
                    return True
                else:
                    print("⚠ Pump initialization timeout")
                    logger.warning("Pump initialization timeout")
                    return False
            else:
                print("✓ Pump initialization command sent")
                logger.info("Pump initialization command sent")
                return True
        else:
            print("⚠ Pump initialization may have failed")
            logger.warning("Pump initialization failed or no response")
            return False



    def send_command(self, command, response_timeout=0.5):
        """
        Send command to XLP 6000 pump

        Args:
            command: Command string (without address or termination)
            response_timeout: How long to wait for response in seconds

        Returns:
            Response string or None
        """
        # Format command with address and proper termination
        full_command = f"/{self.address}{command}\r"

        # Log command to history
        self.command_history.append({
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'command': command,
            'full_command': full_command
        })

        # Send command
        self.serial_connection.write(full_command.encode('ascii'))

        # Wait for response
        time.sleep(response_timeout)

        # Read response if available
        if self.serial_connection.in_waiting > 0:
            response = self.serial_connection.read(self.serial_connection.in_waiting)
            return response.decode('ascii', errors='replace')

        return None

    def home_syringe(self):
        """
        Home the syringe to position 0

        Returns:
            bool: True if successful
        """
        command = "A0R"  # Move to absolute position 0
        if self.send_command(command):
            self.current_position = 0
            self.target_position = 0
            logger.info("Syringe homed to position 0")
            return True
        return False

    def move_syringe_absolute(self, position, wait=False, timeout=30):
        """
        Move syringe to absolute position

        Args:
            position: Target position (0-6000 increments)
            wait: If True, wait until pump is ready before returning (default False)
            timeout: Maximum time to wait in seconds if wait=True (default 30)

        Returns:
            bool: True if successful (and ready if wait=True)
        """
        if 0 <= position <= 6000:
            command = f"A{position}R"
            if self.send_command(command):
                self.target_position = position
                logger.info(f"Moving syringe to position {position}")

                if wait:
                    logger.info(f"Waiting for syringe move to complete...")
                    return self.wait_until_ready(timeout=timeout)

                return True
        return False

    def set_speed_profile(self, start_speed, top_speed, cutoff_speed):
        """
        Set pump speed profile

        Args:
            start_speed: Starting speed (steps/sec)
            top_speed: Maximum speed (steps/sec)
            cutoff_speed: Ending speed (steps/sec)

        Returns:
            bool: True if successful
        """
        command = f"v{start_speed}V{top_speed}c{cutoff_speed}"
        if self.send_command(command):
            self.speed_settings.update({
                'start_speed': start_speed,
                'top_speed': top_speed,
                'cutoff_speed': cutoff_speed
            })
            logger.info(f"Speed profile set: start={start_speed}, top={top_speed}, cutoff={cutoff_speed}")
            return True
        return False

    def continuous_pump(self, volume, flowrate, inlet, outlet, wait=False, timeout=60):
        """
        Execute continuous pump operation

        Args:
            volume: Volume to pump (uL)
            flowrate: Flow rate (uLs/min)
            inlet: Inlet valve position (1-10)
            outlet: Outlet valve position (1-2)
            wait: If True, wait until pump is ready before returning (default False)
            timeout: Maximum time to wait in seconds if wait=True (default 60)

        Returns:
            bool: True if successful (and ready if wait=True)
        """
        #Calculate steps to move based on volume and syringe size
        #volume (µL) -> mL -> steps
        steps = int((volume / 1000 / self.syringe_size) * self.max_position)

        # Convert flowrate from µL/min to steps/sec
        # flowrate (µL/min) -> mL/min -> mL/sec -> steps/sec
        flowrate_ml_min = flowrate / 1000  # Convert µL/min to mL/min
        steps_per_sec = (flowrate_ml_min / 60) * (self.max_position / self.syringe_size)
        dispense_rate = int(steps_per_sec)
        aspirate_rate = self.aspirate_speed

        result = False

        if steps > self.max_position:
            cycles = steps // self.max_position
            remaining = steps % self.max_position

            # First command: pump full cycles
            command1 = f"V{aspirate_rate}IA{self.max_position}OV{dispense_rate}A0G{cycles}R"
            logger.info(f"Continuous pump cycle: {cycles} cycles @ {flowrate}µL/min, inlet={inlet}, outlet={outlet}")
            self.send_command(command1)

            time.sleep(0.5)
            # Second command: pump remaining volume
            if remaining > 0:
                command2 = f"V{aspirate_rate}IA{remaining}OV{dispense_rate}A0R"
                logger.info(f"Continuous pump remaining: {remaining} steps")
                result = self.send_command(command2)
            else:
                result = True
        else:
            # For single operation
            command = f"V{aspirate_rate}IA{steps}OV{dispense_rate}A0GR"
            logger.info(f"Continuous pump: {volume}µL @ {flowrate}µL/min, inlet={inlet}, outlet={outlet}")
            result = self.send_command(command)

        if result and wait:
            logger.info(f"Waiting for continuous pump to complete...")
            return self.wait_until_ready(timeout=timeout)

        return result

    def prime_pump(self, volume, inlet, outlet, wait=False, timeout=60):
        """
        Prime the pump by aspirating and dispensing a specified volume

        Args:
            volume: Volume to prime (uL)
            inlet: Inlet valve position (1-10)
            outlet: Outlet valve position (1-2)
            wait: If True, wait until pump is ready before returning (default False)
            timeout: Maximum time to wait in seconds if wait=True (default 60)

        Returns:
            bool: True if successful (and ready if wait=True)
        """
        # Calculate steps to move based on volume and syringe size
        steps = int((volume / (self.syringe_size * 1000)) * self.max_position)

        result = False

        if steps > self.max_position:
            cycles = steps // self.max_position
            remaining = steps % self.max_position

            # First command: aspirate full cycles
            command1 = f"V{self.aspirate_speed}IA{self.max_position}V{self.dispense_speed}A0R"
            logger.info(f"Priming pump cycle: {cycles} cycles @ inlet={inlet}")
            self.send_command(command1)

            time.sleep(0.5)
            # Second command: aspirate remaining volume
            if remaining > 0:
                command2 = f"V{self.aspirate_speed}IA{remaining}R"
                logger.info(f"Priming pump remaining: {remaining} steps")
                self.send_command(command2)

            time.sleep(0.5)
            # Dispense all aspirated volume
            command3 = f"V{self.dispense_speed}A0GR"
            logger.info(f"Dispensing primed volume @ outlet={outlet}")
            result = self.send_command(command3)

        else:
            # For single operation
            command = f"V{self.aspirate_speed}IA{steps}R"
            logger.info(f"Priming pump: {volume}µL @ inlet={inlet}")
            self.send_command(command)

            time.sleep(0.5)
            dispense_command = f"V{self.dispense_speed}A0GR"
            logger.info(f"Dispensing primed volume @ outlet={outlet}")
            result = self.send_command(dispense_command)

        if result and wait:
            logger.info(f"Waiting for prime pump to complete...")
            return self.wait_until_ready(timeout=timeout)

        return result


    def query_status(self):
        """
        Query pump status

        Returns:
            Status response from pump
        """
        return self.send_command("Q")

    def parse_status_response(self, response):
        """
        Parse status response from pump

        The XLP6000/Cavro pump typically returns status in format:
        /0`NNNN<CR> - Idle, ready for commands (` = backtick)
        /0@NNNN<CR> - Busy, executing command (@ = at sign)

        Where NNNN is the current position

        Args:
            response: Raw response string from pump

        Returns:
            dict: Parsed status with keys 'is_busy', 'is_idle', 'position', 'raw'
        """
        if not response:
            return {
                'is_busy': None,
                'is_idle': None,
                'position': None,
                'raw': None,
                'error': 'No response received'
            }

        # Clean up response - remove control characters and whitespace
        # Keep only printable ASCII characters
        cleaned_response = ''.join(char for char in response if 32 <= ord(char) <= 126)

        # Default status dict
        status = {
            'is_busy': False,
            'is_idle': False,
            'position': None,
            'raw': response,
            'cleaned': cleaned_response,
            'error': None
        }

        try:
            # Check for status indicators
            # Typical format: /0`3000 or /0@3000
            if '`' in cleaned_response:  # Backtick = idle
                status['is_idle'] = True
                status['is_busy'] = False
            elif '@' in cleaned_response:  # @ = busy
                status['is_busy'] = True
                status['is_idle'] = False
            else:
                # Unknown status format, try to extract info
                status['error'] = f'Unknown status format: {repr(cleaned_response)}'

            # Try to extract position (typically numbers after status char)
            # Remove address prefix if present (e.g., /0)
            pos_str = cleaned_response.replace('/', '').replace('\r', '').replace('\n', '')
            # Remove status characters
            pos_str = pos_str.replace('`', '').replace('@', '')
            # Extract digits
            digits = ''.join(filter(str.isdigit, pos_str))
            if digits:
                status['position'] = int(digits)

        except Exception as e:
            status['error'] = f'Error parsing status: {str(e)}'
            logger.warning(f"Failed to parse status response: {repr(response)}, error: {e}")

        return status

    def get_parsed_status(self):
        """
        Get current pump status with parsed information

        Returns:
            dict: Parsed status with keys 'is_busy', 'is_idle', 'position', 'raw', 'error'
        """
        response = self.query_status()
        return self.parse_status_response(response)

    def is_pump_ready(self):
        """
        Check if pump is ready to accept new commands (idle state)

        Returns:
            bool: True if pump is idle/ready, False if busy or error
        """
        if not self.is_connected:
            logger.warning("Cannot check pump status - not connected")
            return False

        status = self.get_parsed_status()

        if status.get('error'):
            logger.warning(f"Status check error: {status['error']}")
            return False

        return status.get('is_idle', False)

    def wait_until_ready(self, timeout=30, poll_interval=0.5):
        """
        Wait until pump is ready (idle) or timeout occurs

        Args:
            timeout: Maximum time to wait in seconds (default 30)
            poll_interval: Time between status checks in seconds (default 0.5)

        Returns:
            bool: True if pump became ready, False if timeout
        """
        if not self.is_connected:
            logger.error("Cannot wait for pump - not connected")
            return False

        start_time = time.time()
        elapsed = 0
        poll_count = 0

        logger.info(f"Waiting for pump to be ready (timeout={timeout}s, interval={poll_interval}s)")

        while elapsed < timeout:
            status = self.get_parsed_status()
            poll_count += 1

            if status.get('error'):
                logger.warning(f"Poll #{poll_count}: Status error - {status['error']}")
            elif status.get('is_idle'):
                elapsed = time.time() - start_time
                logger.info(f"Pump ready after {elapsed:.2f}s ({poll_count} polls)")
                return True
            elif status.get('is_busy'):
                logger.debug(f"Poll #{poll_count}: Pump busy, position={status.get('position')}")
            else:
                logger.debug(f"Poll #{poll_count}: Unknown status - {status.get('raw')}")

            # Wait before next poll
            time.sleep(poll_interval)
            elapsed = time.time() - start_time

        # Timeout occurred
        logger.warning(f"Timeout waiting for pump ({timeout}s elapsed, {poll_count} polls)")
        return False

    def get_command_history(self):
        """
        Get command history

        Returns:
            list: List of command history entries
        """
        return list(self.command_history)

    def terminate(self):
        """
        Send terminate command to stop current operation

        Returns:
            bool: True if successful
        """
        logger.info("Sending terminate command")
        return self.send_command("T")


    def pause(self):
        """
        Send pause command to pause current operation

        Returns:
            bool: True if successful
        """
        logger.info("Sending pause command")
        return self.send_command("H")

    def resume(self):
        """
        Send resume command to resume current operation

        Returns:
            bool: True if successful
        """
        logger.info("Sending resume command")
        return self.send_command("R")
