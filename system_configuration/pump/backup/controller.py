"""
XLP6000 Syringe Pump Controller
Handles all pump communication and control logic
"""

import serial
import serial.tools.list_ports
import time
import threading
import numpy as np
from datetime import datetime
from collections import deque
import logging

logger = logging.getLogger(__name__)


class XLP6000Controller:
    """XLP 6000 Syringe Pump Controller with Advanced Manual Control"""

    def __init__(self):
        self.serial_connection = None
        self.is_connected = False
        self.pump_address = 1
        self.baud_rate = 9600
        self.current_position = 0
        self.target_position = 0
        self.valve_position = "Bypass"
        self.syringe_size = 10.0  # mL - Default 10 mL syringe
        self.speed_settings = {
            'start_speed': 50,
            'top_speed': 1000,
            'cutoff_speed': 50
        }
        self.command_history = deque(maxlen=100)
        self.status = "Disconnected"
        self.errors = []
        self.operation_log = deque(maxlen=500)

        # Flow control settings
        self.current_flow_rate = 0.0  # mL/min
        self.target_flow_rate = 0.0  # mL/min
        self.is_continuous_mode = False
        self.flow_direction = "aspirate"  # "aspirate" or "dispense"
        self.operation_state = "idle"  # "idle", "aspirating", "dispensing", "paused"

        # Safety settings
        self.pressure_limit = 150.0  # psi
        self.pressure_alarm = False
        self.emergency_stop_flag = False

        # Wash settings
        self.wash_volume = 500  # μL - configurable wash volume

        # Process tracking
        self.current_step = "IDLE"
        self.step_number = 0
        self.total_steps = 0
        self.step_volume = 0  # μL
        self.total_volume = 0  # μL
        self.target_total_volume = 0  # μL

        # System configuration
        self.inlet_valve_count = 9  # Configurable A1-A9 for 9-port valve
        self.has_column = True
        self.has_fraction_collector = False
        self.column_type = "C18"
        self.system_name = "XLP 6000 Chromatography System"

        # Manual flow control
        self.selected_inlet_valve = "A1"
        self.selected_outlet_valve = "Collect"  # "Waste" or "Collect"
        self.continuous_flow_rate = 0.0  # mL/min
        self.continuous_flow_active = False
        self.calculated_pump_speed = 0  # steps/sec

        # Continuous pumping (new feature)
        self.continuous_pumping_active = False
        self.continuous_pumping_inlet = "A1"
        self.continuous_pumping_outlet = "Waste"
        self.continuous_pumping_flow_rate = 1.0  # mL/min

        # Sequence builder
        self.current_sequence = []
        self.saved_sequences = {}
        self.executing_sequence = False
        self.current_sequence_step = 0

        # Method Configuration Settings
        self.method_config = {
            'column_resin': 'Protein A',
            'column_diameter': 10.0,  # mm
            'column_height': 100.0,  # mm
            'column_volume': 7.854,  # mL (auto-calculated)
            'default_flow_rate': 2.0,  # mL/min
            'default_flow_rate_unit': 'mL/min',
            'default_volume_unit': 'mL',
            'buffer_map': {
                'A1': 'PBS pH 7.4',
                'A2': 'Sample',
                'A3': 'High Salt Wash',
                'A4': 'Elution Buffer',
                'A5': '0.1M NaOH',
                'A6': 'Buffer 6',
                'A7': 'Buffer 7',
                'A8': 'Buffer 8',
                'A9': 'Buffer 9'
            }
        }

        # Pre-defined method templates
        self.method_templates = {
            "Protein A Purification": [
                {"type": "configuration", "name": "Method Configuration", "config": self.method_config.copy()},
                {"type": "equilibrate", "name": "Equilibration", "valve": "A1", "volume": 5000, "flow_rate": 2.0,
                 "buffer": "PBS"},
                {"type": "load", "name": "Sample Load", "valve": "A2", "volume": 10000, "flow_rate": 1.0,
                 "buffer": "Sample"},
                {"type": "wash", "name": "Wash 1", "valve": "A1", "volume": 10000, "flow_rate": 2.0, "buffer": "PBS"},
                {"type": "wash", "name": "Wash 2", "valve": "A3", "volume": 5000, "flow_rate": 2.0,
                 "buffer": "High Salt"},
                {"type": "elute", "name": "Elution", "valve": "A4", "volume": 3000, "flow_rate": 1.0,
                 "buffer": "Elution Buffer", "collect": True},
                {"type": "regenerate", "name": "Regeneration", "valve": "A5", "volume": 5000, "flow_rate": 2.0,
                 "buffer": "0.1M NaOH"},
                {"type": "equilibrate", "name": "Re-equilibration", "valve": "A1", "volume": 10000, "flow_rate": 2.0,
                 "buffer": "PBS"}
            ],
            "IEX Purification": [
                {"type": "configuration", "name": "Method Configuration", "config": self.method_config.copy()},
                {"type": "equilibrate", "name": "Equilibration", "valve": "A1", "volume": 5000, "flow_rate": 2.0,
                 "buffer": "Buffer A"},
                {"type": "load", "name": "Sample Load", "valve": "A2", "volume": 5000, "flow_rate": 0.5,
                 "buffer": "Sample"},
                {"type": "wash", "name": "Wash", "valve": "A1", "volume": 5000, "flow_rate": 2.0, "buffer": "Buffer A"},
                {"type": "elute", "name": "Gradient Elution", "valve": "A1", "volume": 20000, "flow_rate": 1.0,
                 "buffer": "Gradient A-B", "gradient": True, "collect": True},
                {"type": "regenerate", "name": "Strip", "valve": "A6", "volume": 5000, "flow_rate": 2.0,
                 "buffer": "2M NaCl"},
                {"type": "equilibrate", "name": "Re-equilibration", "valve": "A1", "volume": 10000, "flow_rate": 2.0,
                 "buffer": "Buffer A"}
            ],
            "Desalting": [
                {"type": "configuration", "name": "Method Configuration", "config": self.method_config.copy()},
                {"type": "equilibrate", "name": "Equilibration", "valve": "A1", "volume": 3000, "flow_rate": 5.0,
                 "buffer": "Buffer"},
                {"type": "load", "name": "Sample Load", "valve": "A2", "volume": 500, "flow_rate": 1.0,
                 "buffer": "Sample"},
                {"type": "elute", "name": "Elution", "valve": "A1", "volume": 2000, "flow_rate": 2.0,
                 "buffer": "Buffer", "collect": True}
            ]
        }

        # Quick presets
        self.flow_presets = [0.1, 0.5, 1.0, 2.0, 5.0, 10.0]  # mL/min
        self.volume_presets = [10, 50, 100, 500, 1000, 5000]  # μL

        # Real-time data storage
        self.data_buffer = {
            'time': deque(maxlen=1000),
            'pressure': deque(maxlen=1000),
            'flow_rate': deque(maxlen=1000),
            'volume': deque(maxlen=1000),
            'position': deque(maxlen=1000),
            'temperature': deque(maxlen=1000)
        }

        # Method storage
        self.method_steps = []
        self.current_method_step = 0
        self.is_running = False
        self.is_paused = False

        # Gradient mixing
        self.gradient_enabled = False
        self.gradient_profile = []

        # Threading for continuous operations
        self.operation_thread = None
        self.stop_operation = threading.Event()

    def calculate_column_volume(self):
        """Calculate column volume from diameter and height"""
        diameter_mm = self.method_config['column_diameter']
        height_mm = self.method_config['column_height'] * 10  # Convert cm to mm
        radius_mm = diameter_mm / 2
        volume_mm3 = 3.14159 * (radius_mm ** 2) * height_mm
        volume_ml = volume_mm3 / 1000  # Convert mm³ to mL
        self.method_config['column_volume'] = round(volume_ml, 3)
        return volume_ml

    def convert_flow_rate(self, flow_rate, from_unit, to_unit='mL/min'):
        """Convert flow rate between different units"""
        cv = self.method_config['column_volume']
        column_area = 3.14159 * ((self.method_config['column_diameter'] / 2) ** 2)  # mm²

        # Convert everything to mL/min first
        if from_unit == 'mL/min':
            ml_per_min = flow_rate
        elif from_unit == 'cm/hr':
            # cm/hr to mL/min: (cm/hr * column_area_cm² * 1000mm³/mL) / (60 min/hr)
            ml_per_min = (flow_rate * (column_area / 100) * 1000) / 60
        elif from_unit == 'residence_time':
            # Residence time (min) to mL/min: CV / residence_time
            ml_per_min = cv / flow_rate if flow_rate > 0 else 0
        else:
            ml_per_min = flow_rate

        # Convert from mL/min to target unit
        if to_unit == 'mL/min':
            return ml_per_min
        elif to_unit == 'cm/hr':
            return (ml_per_min * 60) / ((column_area / 100) * 1000)
        elif to_unit == 'residence_time':
            return cv / ml_per_min if ml_per_min > 0 else 0
        else:
            return ml_per_min

    def convert_volume(self, volume, from_unit, to_unit='mL'):
        """Convert volume between mL and CV"""
        cv = self.method_config['column_volume']

        if from_unit == 'mL' and to_unit == 'CV':
            return volume / cv if cv > 0 else 0
        elif from_unit == 'CV' and to_unit == 'mL':
            return volume * cv
        else:
            return volume

    def get_available_ports(self):
        """Get list of available serial ports"""
        ports = serial.tools.list_ports.comports()
        return [port.device for port in ports]

    def connect(self, port, baud_rate=9600):
        """Connect to XLP 6000 pump"""
        try:
            self.serial_connection = serial.Serial(
                port=port,
                baudrate=baud_rate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1
            )
            self.is_connected = True
            self.status = "Connected"
            self.baud_rate = baud_rate
            logger.info(f"Connected to XLP 6000 on {port}")

            # Initialize pump
            self.send_command("ZR")  # Initialize command
            return True

        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            self.is_connected = False
            self.status = f"Connection Error: {e}"
            return False

    def disconnect(self):
        """Disconnect from pump"""
        if self.serial_connection and self.serial_connection.is_open:
            self.serial_connection.close()
        self.is_connected = False
        self.status = "Disconnected"
        logger.info("Disconnected from XLP 6000")

    def send_command(self, command):
        """Send command to XLP 6000"""
        if not self.is_connected or not self.serial_connection:
            logger.warning("Not connected to pump")
            return False

        try:
            # Format command with address and proper termination
            full_command = f"/{self.pump_address}{command}\r"
            self.serial_connection.write(full_command.encode())

            # Add to command history
            self.command_history.append({
                'timestamp': datetime.now().strftime('%H:%M:%S'),
                'command': full_command.strip()
            })

            logger.info(f"Sent command: {full_command.strip()}")

            # Read response if available
            time.sleep(0.1)  # Small delay for response
            if self.serial_connection.in_waiting > 0:
                response = self.serial_connection.read(self.serial_connection.in_waiting).decode()
                logger.info(f"Response: {response.strip()}")
                return response

            return True

        except Exception as e:
            logger.error(f"Command failed: {e}")
            return False

    def move_valve(self, position):
        """Move valve to specified position"""
        position_commands = {
            'Input': 'I',
            'Output': 'O',
            'Bypass': 'B'
        }

        if position in position_commands:
            command = f"{position_commands[position]}R"
            if self.send_command(command):
                self.valve_position = position
                return True
        return False

    def set_inlet_valve(self, port):
        """Move valve to specific port number (1-9 for inlet valves)"""
        if 1 <= port <= 9:
            # For XLP 6000, valve ports are controlled with specific commands
            # Port 1-9 typically map to inlet positions A1-A9
            command = f"I{port}R"  # Input valve to port X
            if self.send_command(command):
                self.valve_position = f"Port {port}"
                self.selected_inlet_valve = f"A{port}"
                self.log_operation(f"Valve moved to port {port} ({self.selected_inlet_valve})")
                return True
        return False

    def set_outlet_valve(self, outlet_type):
        """Set outlet valve to Waste or Collect"""
        if outlet_type == "Waste":
            command = "O1R"  # Output valve to waste
        elif outlet_type == "Collect":
            command = "O2R"  # Output valve to collect
        else:
            return False

        if self.send_command(command):
            self.selected_outlet_valve = outlet_type
            self.log_operation(f"Outlet valve set to {outlet_type}")
            return True
        return False

    def home_syringe(self):
        """Home the syringe to position 0"""
        command = "A0R"  # Move to absolute position 0
        if self.send_command(command):
            self.current_position = 0
            self.target_position = 0
            self.log_operation("Syringe homed to position 0")
            return True
        return False

    def move_syringe_absolute(self, position):
        """Move syringe to absolute position (0-6000)"""
        if 0 <= position <= 6000:
            command = f"A{position}R"
            if self.send_command(command):
                self.target_position = position
                return True
        return False

    def aspirate(self, volume_ul):
        """Aspirate specified volume in microliters"""
        increments = int((6000 * volume_ul) / (self.syringe_size * 1000))
        if increments > 0:
            command = f"P{increments}R"
            return self.send_command(command)
        return False

    def dispense(self, volume_ul):
        """Dispense specified volume in microliters"""
        increments = int((6000 * volume_ul) / (self.syringe_size * 1000))
        if increments > 0:
            command = f"D{increments}R"
            return self.send_command(command)
        return False

    def set_speed_profile(self, start_speed, top_speed, cutoff_speed):
        """Set pump speed profile"""
        command = f"v{start_speed}V{top_speed}c{cutoff_speed}"
        if self.send_command(command):
            self.speed_settings.update({
                'start_speed': start_speed,
                'top_speed': top_speed,
                'cutoff_speed': cutoff_speed
            })
            return True
        return False

    def query_status(self):
        """Query pump status"""
        return self.send_command("Q")

    def start_continuous_flow(self, flow_rate, direction="aspirate"):
        """Start continuous flow at specified rate (single direction only)"""
        self.target_flow_rate = flow_rate
        self.flow_direction = direction
        self.is_continuous_mode = True
        self.operation_state = "aspirating" if direction == "aspirate" else "dispensing"

        # Convert flow rate to steps/sec
        steps_per_sec = int((flow_rate * 6000) / (self.syringe_size * 60))

        if direction == "aspirate":
            command = f"v{steps_per_sec}V{steps_per_sec}c{steps_per_sec}P6000R"
        else:
            command = f"v{steps_per_sec}V{steps_per_sec}c{steps_per_sec}D6000R"

        self.log_operation(f"Started continuous {direction} at {flow_rate} mL/min")
        return self.send_command(command)

    def stop_continuous_flow(self):
        """Stop continuous flow"""
        self.is_continuous_mode = False
        self.current_flow_rate = 0.0
        self.target_flow_rate = 0.0
        self.operation_state = "idle"
        self.log_operation("Stopped continuous flow")
        return self.send_command("T")  # Terminate command

    def start_continuous_pumping(self, flow_rate, inlet_valve, outlet_valve):
        """
        Start continuous pumping operation that cycles between aspirate and dispense

        Args:
            flow_rate: Flow rate in mL/min
            inlet_valve: Inlet valve position (e.g., "A1", "A2", etc.)
            outlet_valve: Outlet valve position ("Waste" or "Collect")
        """
        # Stop any existing pumping operation
        self.stop_continuous_pumping()

        # Set parameters
        self.continuous_pumping_flow_rate = flow_rate
        self.continuous_pumping_inlet = inlet_valve
        self.continuous_pumping_outlet = outlet_valve
        self.continuous_pumping_active = True

        # Clear stop event
        self.stop_operation.clear()

        # Start pumping thread
        self.operation_thread = threading.Thread(
            target=self._continuous_pumping_loop,
            daemon=True
        )
        self.operation_thread.start()

        self.log_operation(
            f"Started continuous pumping: {inlet_valve} → {outlet_valve} @ {flow_rate} mL/min"
        )
        return True

    def _continuous_pumping_loop(self):
        """
        Internal loop for continuous pumping operation
        Continuously cycles: aspirate from inlet → dispense to outlet
        """
        # Use 80% of syringe capacity for safety margin (20mL for 25mL syringe)
        cycle_volume_ml = self.syringe_size * 0.8
        cycle_volume_ul = cycle_volume_ml * 1000

        logger.info(f"Continuous pumping loop started. Cycle volume: {cycle_volume_ml} mL")

        try:
            while not self.stop_operation.is_set() and self.continuous_pumping_active:
                # Check safety
                if self.emergency_stop_flag or not self.check_pressure_safety():
                    logger.warning("Safety check failed, stopping pumping")
                    break

                # ASPIRATE PHASE
                # Move to inlet valve
                inlet_port = int(self.continuous_pumping_inlet[1])  # Extract number from "A1", "A2", etc.
                self.move_valve_to_port(inlet_port)
                time.sleep(0.5)  # Allow valve to settle

                # Aspirate
                self.operation_state = "aspirating"
                self.log_operation(f"Aspirating {cycle_volume_ml} mL from {self.continuous_pumping_inlet}")

                # Calculate time for this volume at given flow rate
                cycle_time_min = cycle_volume_ml / self.continuous_pumping_flow_rate
                cycle_time_sec = cycle_time_min * 60

                # Convert flow rate to pump speed
                steps_per_sec = int((self.continuous_pumping_flow_rate * 6000) / (self.syringe_size * 60))

                # Execute aspirate command
                self.set_speed_profile(steps_per_sec, steps_per_sec, steps_per_sec)
                self.aspirate(cycle_volume_ul)

                # Wait for aspirate to complete
                time.sleep(cycle_time_sec + 1)  # Add 1 second buffer

                if self.stop_operation.is_set():
                    break

                # DISPENSE PHASE
                # Move to outlet valve
                self.set_outlet_valve(self.continuous_pumping_outlet)
                time.sleep(0.5)  # Allow valve to settle

                # Dispense
                self.operation_state = "dispensing"
                self.log_operation(f"Dispensing {cycle_volume_ml} mL to {self.continuous_pumping_outlet}")

                # Execute dispense command
                self.dispense(cycle_volume_ul)

                # Wait for dispense to complete
                time.sleep(cycle_time_sec + 1)  # Add 1 second buffer

        except Exception as e:
            logger.error(f"Error in continuous pumping loop: {e}")
            self.log_operation(f"Continuous pumping error: {e}", level="ERROR")

        finally:
            self.continuous_pumping_active = False
            self.operation_state = "idle"
            logger.info("Continuous pumping loop stopped")

    def stop_continuous_pumping(self):
        """Stop continuous pumping operation"""
        if self.continuous_pumping_active:
            self.log_operation("Stopping continuous pumping")
            self.stop_operation.set()
            self.continuous_pumping_active = False

            # Stop any active pump movement
            self.send_command("T")  # Terminate command

            # Wait for thread to finish
            if self.operation_thread and self.operation_thread.is_alive():
                self.operation_thread.join(timeout=5)

            self.operation_state = "idle"
            return True
        return False

    def pause_operation(self):
        """Pause current operation"""
        if self.operation_state in ["aspirating", "dispensing"]:
            self.is_paused = True
            self.operation_state = "paused"
            self.log_operation("Operation paused")
            return self.send_command("T")
        return False

    def resume_operation(self):
        """Resume paused operation"""
        if self.is_paused:
            self.is_paused = False
            if self.is_continuous_mode:
                return self.start_continuous_flow(self.target_flow_rate, self.flow_direction)
            self.log_operation("Operation resumed")
        return False

    def emergency_stop(self):
        """Emergency stop all operations"""
        self.emergency_stop_flag = True
        self.stop_continuous_flow()
        self.stop_continuous_pumping()
        self.is_paused = False
        self.operation_state = "idle"
        self.log_operation("EMERGENCY STOP ACTIVATED", level="ERROR")
        return self.send_command("T")

    def prime_system(self, volume=1000):
        """Prime the system by aspirating and dispensing"""
        self.log_operation(f"Priming system with {volume}μL")
        self.move_valve("Input")
        time.sleep(0.5)
        self.aspirate(volume)
        time.sleep(1)
        self.move_valve("Output")
        time.sleep(0.5)
        self.dispense(volume)
        self.move_valve("Bypass")
        return True

    def purge_system(self, cycles=3):
        """Purge system with multiple cycles"""
        self.log_operation(f"Purging system - {cycles} cycles")
        for i in range(cycles):
            self.prime_system()
            time.sleep(0.5)
        return True

    def wash_valve(self):
        """Wash the current valve with configured wash volume"""
        self.log_operation(f"Washing valve - {self.valve_position} with {self.wash_volume}μL")

        # Store current valve position
        original_position = self.valve_position

        # Move to input for wash solution
        self.move_valve("Input")
        time.sleep(0.5)

        # Aspirate wash volume
        self.aspirate(self.wash_volume)
        time.sleep(0.5)

        # Move to original valve position for wash
        self.move_valve(original_position)
        time.sleep(0.5)

        # Dispense wash solution through valve
        self.dispense(self.wash_volume)
        time.sleep(0.5)

        # Return to bypass
        self.move_valve("Bypass")

        self.log_operation(f"Valve wash completed for {original_position} position")
        return True

    def log_operation(self, message, level="INFO"):
        """Log operation with timestamp"""
        log_entry = {
            'timestamp': datetime.now(),
            'message': message,
            'level': level,
            'pump_position': self.current_position,
            'valve_position': self.valve_position
        }
        self.operation_log.append(log_entry)
        logger.info(f"[{level}] {message}")

    def check_pressure_safety(self):
        """Check if pressure is within safe limits"""
        if self.data_buffer['pressure']:
            current_pressure = self.data_buffer['pressure'][-1]
            if current_pressure > self.pressure_limit:
                self.pressure_alarm = True
                self.log_operation(f"Pressure alarm: {current_pressure:.1f} psi > {self.pressure_limit} psi", "WARNING")
                return False
        return True

    def add_data_point(self):
        """Add simulated data point for real-time plotting"""
        current_time = datetime.now()
        self.data_buffer['time'].append(current_time)

        # Simulate more realistic data based on operation state
        base_pressure = 120 if self.operation_state == "idle" else 140
        pressure_noise = 2 if self.is_continuous_mode else 5
        pressure = np.random.normal(base_pressure, pressure_noise)

        # Add pressure spikes during valve changes
        if self.operation_state in ["aspirating", "dispensing"]:
            pressure += np.random.normal(10, 3)

        self.data_buffer['pressure'].append(max(0, pressure))
        self.data_buffer['flow_rate'].append(self.current_flow_rate + np.random.normal(0, 0.1))
        self.data_buffer['volume'].append(np.random.normal(50, 2))
        self.data_buffer['position'].append(self.current_position + np.random.normal(0, 5))
        self.data_buffer['temperature'].append(np.random.normal(23.5, 0.2))

        # Update current flow rate towards target
        if self.is_continuous_mode or self.continuous_pumping_active:
            if self.continuous_pumping_active:
                target = self.continuous_pumping_flow_rate
            else:
                target = self.target_flow_rate
            flow_diff = target - self.current_flow_rate
            self.current_flow_rate += flow_diff * 0.1  # Smooth ramping
        else:
            self.current_flow_rate *= 0.95  # Decay to zero

        # Check safety
        self.check_pressure_safety()
