import dash
from dash import dcc, html, Input, Output, State, callback_context, dash_table, MATCH
import dash_bootstrap_components as dbc
import plotly.graph_objs as go
import plotly.express as px
import pandas as pd
import serial
import serial.tools.list_ports
import time
import threading
import json
from datetime import datetime, timedelta
import numpy as np
from collections import deque
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
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
        self.syringe_size = 25.0  # mL - Default 25 mL syringe
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
        self.emergency_stop = False

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
    
    def move_valve_to_port(self, port):
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
        """Start continuous flow at specified rate"""
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
        self.emergency_stop = True
        self.stop_continuous_flow()
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
        if self.is_continuous_mode:
            flow_diff = self.target_flow_rate - self.current_flow_rate
            self.current_flow_rate += flow_diff * 0.1  # Smooth ramping
        else:
            self.current_flow_rate *= 0.95  # Decay to zero

        # Check safety
        self.check_pressure_safety()

    def create_gradient(self, start_flow, end_flow, duration_min, steps=10):
        """Create a gradient profile for flow rate changes"""
        gradient_steps = []
        time_per_step = duration_min / steps

        for i in range(steps + 1):
            progress = i / steps
            current_flow = start_flow + (end_flow - start_flow) * progress
            gradient_steps.append({
                'time_min': i * time_per_step,
                'flow_rate': current_flow,
                'step': i
            })

        self.gradient_profile = gradient_steps
        self.gradient_enabled = True
        self.log_operation(f"Created gradient: {start_flow} to {end_flow} mL/min over {duration_min} min")
        return gradient_steps

    def execute_gradient_step(self, step_index):
        """Execute a specific gradient step"""
        if step_index < len(self.gradient_profile):
            step = self.gradient_profile[step_index]
            self.start_continuous_flow(step['flow_rate'], self.flow_direction)
            self.log_operation(f"Gradient step {step['step']}: {step['flow_rate']:.2f} mL/min")
            return True
        return False

    def get_gradient_status(self):
        """Get current gradient execution status"""
        return {
            'enabled': self.gradient_enabled,
            'profile': self.gradient_profile,
            'current_step': getattr(self, 'current_gradient_step', 0),
            'total_steps': len(self.gradient_profile) if self.gradient_profile else 0
        }


# Initialize controller
controller = XLP6000Controller()

# Initialize Dash app
app = dash.Dash(__name__, external_stylesheets=[
    'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css'
], suppress_callback_exceptions=True)

app.title = "XLP 6000 Control System"

# Custom CSS
app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
            :root {
                --primary-color: #2563eb;
                --primary-hover: #1d4ed8;
                --secondary-color: #64748b;
                --success-color: #059669;
                --success-hover: #047857;
                --warning-color: #d97706;
                --warning-hover: #b45309;
                --danger-color: #dc2626;
                --danger-hover: #b91c1c;
                --info-color: #0891b2;
                --info-hover: #0e7490;
                --background-main: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
                --background-card: rgba(255, 255, 255, 0.95);
                --text-primary: #1e293b;
                --text-secondary: #64748b;
                --border-color: #e2e8f0;
                --shadow-light: 0 1px 3px rgba(0,0,0,0.1);
                --shadow-medium: 0 4px 6px rgba(0,0,0,0.1);
                --shadow-heavy: 0 10px 15px rgba(0,0,0,0.1);
            }

            body { 
                font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
                margin: 0;
                background: var(--background-main);
                color: var(--text-primary);
                line-height: 1.6;
            }

            .main-header {
                background: #f8fafc;
                color: var(--text-primary);
                padding: 1rem 2rem;
                box-shadow: var(--shadow-light);
                border-bottom: 1px solid var(--border-color);
            }

            .main-header h1 {
                color: var(--text-primary);
                margin: 0;
            }

            .status-connected { 
                color: var(--success-color); 
                font-weight: 600;
                text-shadow: 0 0 10px rgba(5, 150, 105, 0.3);
            }

            .status-disconnected { 
                color: var(--danger-color); 
                font-weight: 600;
                text-shadow: 0 0 10px rgba(220, 38, 38, 0.3);
            }

            .card {
                background: var(--background-card);
                border-radius: 16px;
                box-shadow: var(--shadow-medium);
                padding: 1.5rem;
                margin: 0.75rem;
                border: 1px solid var(--border-color);
                backdrop-filter: blur(10px);
                transition: all 0.3s ease;
                height: fit-content;
            }

            .card:hover {
                transform: translateY(-2px);
                box-shadow: var(--shadow-heavy);
            }

            .metric-card {
                background: linear-gradient(135deg, var(--primary-color) 0%, var(--info-color) 100%);
                color: white;
                text-align: center;
                border-radius: 8px;
                padding: 0.5rem;
                box-shadow: var(--shadow-light);
                transition: all 0.3s ease;
                border: 1px solid rgba(255,255,255,0.1);
            }

            .metric-card:hover {
                transform: scale(1.05);
                box-shadow: var(--shadow-heavy);
            }

            .metric-card.pressure {
                background: linear-gradient(135deg, #dc2626 0%, #ef4444 100%);
            }

            .metric-card.flow {
                background: linear-gradient(135deg, #059669 0%, #10b981 100%);
            }

            .metric-card.volume {
                background: linear-gradient(135deg, #7c3aed 0%, #a855f7 100%);
            }

            .metric-card.temperature {
                background: linear-gradient(135deg, #d97706 0%, #f59e0b 100%);
            }

            .control-button {
                background: var(--primary-color);
                color: white;
                border: none;
                padding: 0.75rem 1.5rem;
                border-radius: 8px;
                cursor: pointer;
                margin: 0.25rem;
                font-weight: 600;
                font-size: 0.875rem;
                transition: all 0.2s ease;
                box-shadow: var(--shadow-light);
                display: inline-flex;
                align-items: center;
                gap: 0.5rem;
            }

            .control-button:hover {
                background: var(--primary-hover);
                transform: translateY(-1px);
                box-shadow: var(--shadow-medium);
            }

            .control-button:active {
                transform: translateY(0);
            }

            .control-button.success {
                background: var(--success-color);
            }

            .control-button.success:hover {
                background: var(--success-hover);
            }

            .control-button.warning {
                background: var(--warning-color);
            }

            .control-button.warning:hover {
                background: var(--warning-hover);
            }

            .control-button.danger {
                background: var(--danger-color);
            }

            .control-button.danger:hover {
                background: var(--danger-hover);
            }

            .control-button.info {
                background: var(--info-color);
            }

            .control-button.info:hover {
                background: var(--info-hover);
            }

            .valve-button-active {
                background: var(--success-color) !important;
                box-shadow: 0 0 20px rgba(5, 150, 105, 0.4) !important;
                border: 2px solid rgba(255,255,255,0.3) !important;
            }

            .emergency-button {
                background: var(--danger-color) !important;
                animation: pulse-red 2s infinite;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 1px;
            }

            .emergency-button:hover {
                background: var(--danger-hover) !important;
                box-shadow: 0 0 20px rgba(220, 38, 38, 0.6) !important;
            }

            @keyframes pulse-red {
                0% { box-shadow: 0 0 0 0 rgba(220, 38, 38, 0.7); }
                70% { box-shadow: 0 0 0 10px rgba(220, 38, 38, 0); }
                100% { box-shadow: 0 0 0 0 rgba(220, 38, 38, 0); }
            }

            .pump-visual {
                background: linear-gradient(145deg, #f1f5f9, #e2e8f0);
                border-radius: 12px;
                padding: 1rem;
                margin: 1rem 0;
                border: 2px solid var(--border-color);
                position: relative;
                overflow: hidden;
            }

            .pump-visual::before {
                content: '';
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                height: 4px;
                background: linear-gradient(90deg, var(--primary-color), var(--success-color), var(--warning-color));
            }

            .progress-bar {
                background: var(--border-color);
                border-radius: 10px;
                height: 8px;
                overflow: hidden;
                margin: 0.5rem 0;
            }

            .progress-fill {
                height: 100%;
                background: linear-gradient(90deg, var(--success-color), var(--primary-color));
                transition: width 0.3s ease;
                border-radius: 10px;
            }

            .status-indicator {
                display: inline-block;
                width: 12px;
                height: 12px;
                border-radius: 50%;
                margin-right: 8px;
                animation: pulse 2s infinite;
            }

            .status-idle { background: var(--secondary-color); }
            .status-running { background: var(--success-color); }
            .status-warning { background: var(--warning-color); }
            .status-error { background: var(--danger-color); }

            @keyframes pulse {
                0% { opacity: 1; }
                50% { opacity: 0.5; }
                100% { opacity: 1; }
            }

            .quick-preset {
                display: inline-block;
                background: rgba(37, 99, 235, 0.1);
                border: 2px solid var(--primary-color);
                color: var(--primary-color);
                padding: 0.5rem 1rem;
                border-radius: 20px;
                margin: 0.25rem;
                cursor: pointer;
                transition: all 0.2s ease;
                font-weight: 600;
                font-size: 0.875rem;
            }

            .quick-preset:hover {
                background: var(--primary-color);
                color: white;
                transform: scale(1.05);
            }

            .tabs {
                background: rgba(255, 255, 255, 0.8);
                backdrop-filter: blur(10px);
                border-radius: 12px;
                margin-bottom: 2rem;
                overflow: hidden;
                box-shadow: var(--shadow-light);
            }

            .tab {
                background: transparent !important;
                border: none !important;
                color: var(--text-secondary) !important;
                font-weight: 600 !important;
                padding: 1rem 2rem !important;
                transition: all 0.3s ease !important;
            }

            .tab--selected {
                background: var(--primary-color) !important;
                color: white !important;
                box-shadow: var(--shadow-light) !important;
            }

            .operation-log {
                background: #1e293b;
                color: #e2e8f0;
                border-radius: 8px;
                padding: 1rem;
                max-height: 300px;
                overflow-y: auto;
                font-family: 'Fira Code', monospace;
                font-size: 0.875rem;
                line-height: 1.4;
            }

            .log-entry {
                padding: 0.25rem 0;
                border-bottom: 1px solid rgba(226, 232, 240, 0.1);
            }

            .log-timestamp {
                color: #64748b;
                font-size: 0.75rem;
            }

            .log-info { color: #0891b2; }
            .log-warning { color: #d97706; }
            .log-error { color: #dc2626; }

            .slider-container {
                margin: 0.5rem 0;
                padding: 0.75rem;
                background: rgba(37, 99, 235, 0.05);
                border-radius: 8px;
                border: 1px solid rgba(37, 99, 235, 0.1);
            }

            .layout-row {
                display: flex;
                gap: 1rem;
                margin: 1rem 0;
                align-items: stretch;
            }

            .layout-col {
                flex: 1;
                display: flex;
                flex-direction: column;
            }

            .layout-col-narrow {
                flex: 0 0 300px;
            }

            .layout-col-wide {
                flex: 2;
            }

            .control-group {
                margin-bottom: 1.5rem;
            }

            .control-group:last-child {
                margin-bottom: 0;
            }

            .button-group {
                display: flex;
                gap: 0.5rem;
                flex-wrap: wrap;
                align-items: center;
            }

            .input-group {
                display: flex;
                flex-direction: column;
                gap: 0.5rem;
                margin-bottom: 1rem;
            }

            .input-row {
                display: flex;
                gap: 0.75rem;
                align-items: flex-end;
            }

            .input-label {
                font-weight: 600;
                color: var(--text-primary);
                font-size: 0.875rem;
                margin-bottom: 0.25rem;
                display: block;
            }

            .form-input {
                padding: 0.5rem 0.75rem;
                border: 2px solid var(--border-color);
                border-radius: 6px;
                font-size: 0.875rem;
                transition: border-color 0.2s ease;
                background: white;
            }

            .form-input:focus {
                outline: none;
                border-color: var(--primary-color);
                box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
            }

            .section-title {
                font-size: 1.25rem;
                font-weight: 700;
                color: var(--text-primary);
                margin-bottom: 1rem;
                display: flex;
                align-items: center;
                gap: 0.5rem;
            }

            .metric-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
                gap: 0.5rem;
                margin: 0.5rem 0;
            }

            .pid-component {
                display: inline-block;
                margin: 5px;
                text-align: center;
                transition: all 0.3s ease;
            }

            .pid-valve {
                width: 60px;
                height: 40px;
                background: #e2e8f0;
                border: 3px solid #64748b;
                border-radius: 8px;
                display: flex;
                align-items: center;
                justify-content: center;
                font-weight: 700;
                font-size: 0.75rem;
                transition: all 0.3s ease;
                position: relative;
            }

            .pid-valve.active {
                background: #10b981;
                border-color: #059669;
                color: white;
                box-shadow: 0 0 15px rgba(16, 185, 129, 0.4);
            }

            .pid-pipe {
                height: 8px;
                background: #64748b;
                transition: all 0.3s ease;
                position: relative;
            }

            .pid-pipe.flow-active {
                background: #10b981;
                box-shadow: 0 0 10px rgba(16, 185, 129, 0.3);
                animation: flow-pulse 2s infinite;
            }

            .pid-pump {
                width: 80px;
                height: 80px;
                background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%);
                border: 4px solid #1e40af;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                font-weight: 700;
                color: white;
                font-size: 0.75rem;
                transition: all 0.3s ease;
                position: relative;
                margin: 20px;
            }

            .pid-pump.active {
                animation: pump-pulse 1.5s infinite;
                transform: scale(1.05);
            }

            .pid-syringe {
                width: 60px;
                height: 120px;
                background: linear-gradient(180deg, #f3f4f6 0%, #e5e7eb 100%);
                border: 3px solid #9ca3af;
                border-radius: 8px;
                position: relative;
                margin: 10px;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: flex-end;
                overflow: hidden;
            }

            .pid-syringe-plunger {
                width: 50px;
                height: 10px;
                background: #6b7280;
                border-radius: 2px;
                position: absolute;
                transition: all 0.8s ease;
            }

            .pid-syringe-liquid {
                width: 100%;
                background: linear-gradient(180deg, #3b82f6 0%, #1d4ed8 100%);
                transition: all 0.8s ease;
                border-radius: 0 0 5px 5px;
            }

            @keyframes pump-pulse {
                0% { box-shadow: 0 0 0 0 rgba(59, 130, 246, 0.7); }
                70% { box-shadow: 0 0 0 20px rgba(59, 130, 246, 0); }
                100% { box-shadow: 0 0 0 0 rgba(59, 130, 246, 0); }
            }

            @keyframes flow-pulse {
                0% { 
                    background-position: 0% 50%;
                    opacity: 0.8;
                }
                50% { 
                    background-position: 100% 50%;
                    opacity: 1;
                }
                100% { 
                    background-position: 200% 50%;
                    opacity: 0.8;
                }
            }

            @keyframes valve-glow {
                0% { box-shadow: 0 0 8px rgba(34, 197, 94, 0.4); }
                50% { box-shadow: 0 0 16px rgba(34, 197, 94, 0.8); }
                100% { box-shadow: 0 0 8px rgba(34, 197, 94, 0.4); }
            }

            @keyframes error-flash {
                0% { border-color: #ef4444; }
                50% { border-color: #fca5a5; }
                100% { border-color: #ef4444; }
            }

            @keyframes button-press {
                0% { transform: scale(1); }
                50% { transform: scale(0.95); }
                100% { transform: scale(1); }
            }

            @keyframes arrow-pulse {
                0% { transform: scale(1); opacity: 0.8; }
                50% { transform: scale(1.1); opacity: 1; }
                100% { transform: scale(1); opacity: 0.8; }
            }

            .pid-container {
                display: flex;
                align-items: center;
                justify-content: space-between;
                flex-wrap: wrap;
                gap: 10px;
                min-height: 200px;
            }

            .step-card {
                background: white;
                border: 2px solid #e2e8f0;
                border-radius: 8px;
                padding: 12px;
                text-align: center;
                cursor: move;
                transition: all 0.3s ease;
                font-weight: 600;
                font-size: 0.85rem;
            }

            .step-card:hover {
                transform: translateY(-2px);
                box-shadow: var(--shadow-medium);
                border-color: var(--primary-color);
            }

            .step-card.dragging {
                opacity: 0.5;
            }

            .sequence-step {
                background: white;
                border: 2px solid #3b82f6;
                border-radius: 8px;
                padding: 15px;
                margin-bottom: 10px;
                display: flex;
                align-items: center;
                transition: all 0.3s ease;
                cursor: pointer;
            }

            .sequence-step:hover {
                box-shadow: var(--shadow-medium);
                transform: translateX(5px);
            }

            .sequence-step.selected {
                background: #eff6ff;
                border-color: #1d4ed8;
            }
            
            .sequence-step.configuration-step {
                background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
                border-color: #0891b2;
                border-width: 2px;
            }
            
            .sequence-step.configuration-step .step-number {
                background: #0891b2;
            }

            .step-number {
                background: #3b82f6;
                color: white;
                width: 30px;
                height: 30px;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                font-weight: 700;
                margin-right: 15px;
            }

            .sequence-dropzone {
                min-height: 400px;
                transition: all 0.3s ease;
            }

            .sequence-dropzone.drag-over {
                background: #e0f2fe !important;
                border: 2px dashed #3b82f6 !important;
            }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
'''

# Layout
app.layout = html.Div([
    # Header
    html.Div([
        html.Div([
            html.H1([
                html.I(className="fas fa-flask", style={'marginRight': '10px'}),
                "XLP 6000 Control System"
            ], style={'margin': '0', 'fontSize': '1.5rem'}),
            html.P("Advanced Syringe Pump Controller",
                   style={'margin': '0', 'opacity': '0.8', 'fontSize': '0.9rem'})
        ], style={'flex': '1'}),

        html.Div([
            html.Div(id='connection-status', style={'marginRight': '1rem'}),
            html.Button([
                html.I(className="fas fa-play", style={'marginRight': '5px'}),
                "Run Method"
            ], id='run-method-btn', className='control-button'),
            html.Button([
                html.I(className="fas fa-pause", style={'marginRight': '5px'}),
                "Pause"
            ], id='pause-method-btn', className='control-button'),
            html.Button([
                html.I(className="fas fa-stop", style={'marginRight': '5px'}),
                "Stop"
            ], id='stop-method-btn', className='control-button emergency-button'),
        ], style={'display': 'flex', 'alignItems': 'center'})
    ], className='main-header', style={'display': 'flex', 'alignItems': 'center'}),

    # Navigation Tabs
    dcc.Tabs(id='main-tabs', value='dashboard', className='tabs', children=[
        dcc.Tab(label='📊 Live Dashboard & Control', value='dashboard', className='tab'),
        dcc.Tab(label='🧪 Method Editor', value='sequence', className='tab'),
        dcc.Tab(label='🔧 Manual Control', value='manual', className='tab'),
        dcc.Tab(label='⚙️ Configuration', value='config', className='tab'),
        dcc.Tab(label='📋 Operation Log', value='log', className='tab'),
    ], style={'marginBottom': '20px'}),

    # Main content area
    html.Div(id='tab-content'),

    # Interval components for real-time updates
    dcc.Interval(id='realtime-interval', interval=1000, n_intervals=0),
    dcc.Interval(id='status-interval', interval=5000, n_intervals=0),

    # Storage components
    dcc.Store(id='method-store', data=[]),
    dcc.Store(id='pump-state-store', data={}),
])


# Dashboard Layout
def create_dashboard_layout():
    return html.Div([
        # UNICORN-Style Run Data Table (Top Section)
        html.Div([
            html.H3("Run Data", style={
                'color': '#2d3748', 'fontSize': '1.1rem', 'fontWeight': '600',
                'marginBottom': '10px', 'borderBottom': '2px solid #e2e8f0', 'paddingBottom': '5px'
            }),

            # Status Grid - UNICORN Style
            html.Table([
                html.Thead([
                    html.Tr([
                        html.Th("Process Volume", style={'textAlign': 'center', 'padding': '8px', 'fontSize': '0.9rem',
                                                         'fontWeight': '600'}),
                        html.Th("Block Volume", style={'textAlign': 'center', 'padding': '8px', 'fontSize': '0.9rem',
                                                       'fontWeight': '600'}),
                        html.Th("Time", style={'textAlign': 'center', 'padding': '8px', 'fontSize': '0.9rem',
                                               'fontWeight': '600'}),
                        html.Th("Sample Flow", style={'textAlign': 'center', 'padding': '8px', 'fontSize': '0.9rem',
                                                      'fontWeight': '600'}),
                        html.Th("Sample Pressure", style={'textAlign': 'center', 'padding': '8px', 'fontSize': '0.9rem',
                                                          'fontWeight': '600'}),
                        html.Th("UV 280", style={'textAlign': 'center', 'padding': '8px', 'fontSize': '0.9rem',
                                                 'fontWeight': '600'}),
                    ])
                ]),
                html.Tbody([
                    html.Tr([
                        html.Td(id='process-volume-display', children="0.0 ml",
                                style={'textAlign': 'center', 'padding': '8px', 'fontSize': '1rem',
                                       'fontWeight': '700'}),
                        html.Td(id='block-volume-display', children="0.0 ml",
                                style={'textAlign': 'center', 'padding': '8px', 'fontSize': '1rem',
                                       'fontWeight': '700'}),
                        html.Td(id='time-display', children="0.0 min",
                                style={'textAlign': 'center', 'padding': '8px', 'fontSize': '1rem',
                                       'fontWeight': '700'}),
                        html.Td(id='sample-flow-display', children="0.0 ml/min",
                                style={'textAlign': 'center', 'padding': '8px', 'fontSize': '1rem',
                                       'fontWeight': '700'}),
                        html.Td(id='sample-pressure-display', children="0.0 MPa",
                                style={'textAlign': 'center', 'padding': '8px', 'fontSize': '1rem',
                                       'fontWeight': '700'}),
                        html.Td(id='uv-280-display', children="0 mAU",
                                style={'textAlign': 'center', 'padding': '8px', 'fontSize': '1rem',
                                       'fontWeight': '700'}),
                    ])
                ])
            ], style={
                'width': '100%', 'borderCollapse': 'collapse',
                'border': '1px solid #e2e8f0', 'backgroundColor': 'white'
            }),

        ], style={
            'backgroundColor': '#f7fafc', 'padding': '15px', 'borderRadius': '8px',
            'border': '1px solid #e2e8f0', 'marginBottom': '20px'
        }),

        # Chromatogram Section (Middle)
        html.Div([
            html.Div([
                html.H3("Chromatogram", style={
                    'color': '#2d3748', 'fontSize': '1.1rem', 'fontWeight': '600',
                    'marginBottom': '10px', 'borderBottom': '2px solid #e2e8f0', 'paddingBottom': '5px',
                    'display': 'inline-block', 'marginRight': '20px'
                }),
                html.Div([
                    html.Label("Show: ", style={'fontWeight': '600', 'marginRight': '10px'}),
                    dcc.Checklist(
                        id='chromatogram-variables',
                        options=[
                            {'label': 'UV 280', 'value': 'uv280'},
                            {'label': 'Conductivity', 'value': 'cond'},
                            {'label': 'Pressure', 'value': 'pressure'},
                            {'label': 'Flow Rate', 'value': 'flow'}
                        ],
                        value=['uv280', 'cond'],  # Default selections
                        inline=True,
                        style={'display': 'inline-block'}
                    )
                ], style={'display': 'inline-block', 'verticalAlign': 'bottom', 'marginBottom': '10px'})
            ], style={'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'flex-end'}),

            dcc.Graph(
                id='realtime-chromatogram',
                style={'height': '350px', 'backgroundColor': 'white'}
            )
        ], style={
            'backgroundColor': '#f7fafc', 'padding': '15px', 'borderRadius': '8px',
            'border': '1px solid #e2e8f0', 'marginBottom': '20px'
        }),

        # Process Picture Section (Bottom)
        html.Div([
            html.H3("Process Picture", style={
                'color': '#2d3748', 'fontSize': '1.1rem', 'fontWeight': '600',
                'marginBottom': '15px', 'borderBottom': '2px solid #e2e8f0', 'paddingBottom': '5px'
            }),

            # Interactive P&ID Diagram
            html.Div(id='pid-diagram', style={
                'padding': '20px', 'minHeight': '300px', 'backgroundColor': 'white',
                'border': '1px solid #e2e8f0', 'borderRadius': '8px'
            }),

        ], style={
            'backgroundColor': 'white', 'padding': '15px', 'borderRadius': '8px',
            'border': '1px solid #e2e8f0'
        }),

    ], style={'margin': '15px'})


# Sequence Builder Layout
def create_sequence_builder_layout():
    return html.Div([
        html.Div([
            # Left Panel - Step Library and Templates
            html.Div([
                # Method Templates
                html.Div([
                    html.H3([html.I(className="fas fa-book", style={'marginRight': '8px'}), "Method Templates"],
                            className='section-title'),
                    dcc.Dropdown(
                        id='template-dropdown',
                        options=[{'label': name, 'value': name} for name in controller.method_templates.keys()],
                        placeholder="Select a template...",
                        style={'marginBottom': '10px'}
                    ),
                    html.Button("Load Template", id='load-template-btn', className='control-button',
                                style={'width': '100%', 'marginBottom': '20px'})
                ], className='card', style={'marginBottom': '20px'}),

                # Step Library
                html.Div([
                    html.H3([html.I(className="fas fa-cube", style={'marginRight': '8px'}), "Step Library"],
                            className='section-title'),
                    html.P("Click to add steps to your sequence:",
                           style={'marginBottom': '1rem', 'color': 'var(--text-secondary)', 'fontSize': '0.9rem'}),
                    html.Div([
                        # Clickable step buttons
                        html.Div([
                            html.Button([
                                html.Div("🔄", style={'fontSize': '1.2rem', 'marginBottom': '5px'}),
                                html.Div("Equilibrate", style={'fontSize': '0.8rem', 'fontWeight': '600'})
                            ], className='step-card', id='add-equilibrate-btn',
                                style={'cursor': 'pointer', 'border': 'none', 'background': 'white'}),

                            html.Button([
                                html.Div("💉", style={'fontSize': '1.2rem', 'marginBottom': '5px'}),
                                html.Div("Load Sample", style={'fontSize': '0.8rem', 'fontWeight': '600'})
                            ], className='step-card', id='add-load-btn',
                                style={'cursor': 'pointer', 'border': 'none', 'background': 'white'}),

                            html.Button([
                                html.Div("🚿", style={'fontSize': '1.2rem', 'marginBottom': '5px'}),
                                html.Div("Wash", style={'fontSize': '0.8rem', 'fontWeight': '600'})
                            ], className='step-card', id='add-wash-btn',
                                style={'cursor': 'pointer', 'border': 'none', 'background': 'white'}),

                            html.Button([
                                html.Div("🧪", style={'fontSize': '1.2rem', 'marginBottom': '5px'}),
                                html.Div("Elute", style={'fontSize': '0.8rem', 'fontWeight': '600'})
                            ], className='step-card', id='add-elute-btn',
                                style={'cursor': 'pointer', 'border': 'none', 'background': 'white'}),

                            html.Button([
                                html.Div("♻️", style={'fontSize': '1.2rem', 'marginBottom': '5px'}),
                                html.Div("Regenerate", style={'fontSize': '0.8rem', 'fontWeight': '600'})
                            ], className='step-card', id='add-regenerate-btn',
                                style={'cursor': 'pointer', 'border': 'none', 'background': 'white'}),

                            html.Button([
                                html.Div("⏸️", style={'fontSize': '1.2rem', 'marginBottom': '5px'}),
                                html.Div("Hold", style={'fontSize': '0.8rem', 'fontWeight': '600'})
                            ], className='step-card', id='add-hold-btn',
                                style={'cursor': 'pointer', 'border': 'none', 'background': 'white'}),

                            html.Button([
                                html.Div("📊", style={'fontSize': '1.2rem', 'marginBottom': '5px'}),
                                html.Div("Gradient", style={'fontSize': '0.8rem', 'fontWeight': '600'})
                            ], className='step-card', id='add-gradient-btn',
                                style={'cursor': 'pointer', 'border': 'none', 'background': 'white'}),
                        ], style={'display': 'grid', 'gridTemplateColumns': 'repeat(2, 1fr)', 'gap': '10px'})
                    ])
                ], className='card'),
            ], style={'width': '25%', 'marginRight': '20px'}),

            # Center Panel - Sequence Builder
            html.Div([
                html.H3([html.I(className="fas fa-list-ol", style={'marginRight': '8px'}), "Current Sequence"],
                        className='section-title'),

                # Sequence steps container (droppable area)
                html.Div(id='sequence-container', className='sequence-dropzone', children=[
                    html.Div("Drop steps here to build your sequence",
                             style={'padding': '40px', 'textAlign': 'center', 'color': '#94a3b8',
                                    'border': '2px dashed #cbd5e1', 'borderRadius': '8px'})
                ], style={'minHeight': '400px', 'padding': '20px', 'background': '#f8fafc',
                          'borderRadius': '8px', 'marginBottom': '20px'}),

                # Sequence controls
                html.Div([
                    html.Button("Clear All", id='clear-sequence-btn', className='control-button warning',
                                style={'marginRight': '10px'}),
                    html.Button("Save Sequence", id='save-sequence-btn', className='control-button',
                                style={'marginRight': '10px'}),
                    html.Button("Run Sequence", id='run-sequence-btn', className='control-button success'),
                ], style={'display': 'flex', 'justifyContent': 'center'})
            ], className='card', style={'flex': '1', 'marginRight': '20px'}),

            # Right Panel - Step Parameters
            html.Div([
                html.H3([html.I(className="fas fa-sliders-h", style={'marginRight': '8px'}), "Step Parameters"],
                        className='section-title'),
                html.Div(id='step-parameters', children=[
                    html.P("Select a step to edit parameters",
                           style={'textAlign': 'center', 'color': '#94a3b8', 'padding': '20px'})
                ])
            ], className='card', style={'width': '30%'})
        ], style={'display': 'flex', 'height': 'calc(100vh - 300px)'}),

        # Hidden stores for sequence data - start with configuration step by default
        dcc.Store(id='sequence-store', data=[{"type": "configuration", "name": "Method Configuration", "config": controller.method_config.copy(), "id": 0}]),
        dcc.Store(id='selected-step-index', data=None),
    ])


# Manual Control Layout
def create_manual_control_layout():
    return html.Div([
        # Top Row - Valve and Syringe Control
        html.Div([
            # Valve Control
            html.Div([
                html.H3([html.I(className="fas fa-exchange-alt", style={'marginRight': '8px'}), "Valve Control"],
                        className='section-title'),
                html.Div([
                    html.Label("Select Valve Position:", className='input-label'),
                    html.Div([
                        html.Button("Input", id='valve-input-btn', className='control-button',
                                    style={'width': '90px'}),
                        html.Button("Output", id='valve-output-btn', className='control-button',
                                    style={'width': '90px'}),
                        html.Button("Bypass", id='valve-bypass-btn', className='control-button valve-button-active',
                                    style={'width': '90px'}),
                    ], className='button-group', style={'marginBottom': '1rem'})
                ], className='control-group'),
                html.Div([
                    html.Label("Direct Port Access:", className='input-label'),
                    html.Div([
                        dcc.Input(id='direct-port-input', type='number', min=1, max=9,
                                  className='form-input', style={'width': '80px'}),
                        html.Button("Move", id='move-port-btn', className='control-button')
                    ], className='input-row')
                ], className='control-group')
            ], className='card layout-col'),

            # Syringe Control
            html.Div([
                html.H3([html.I(className="fas fa-syringe", style={'marginRight': '8px'}), "Syringe Control"],
                        className='section-title'),
                html.Div([
                    html.Label("Absolute Position (0-6000 steps):", className='input-label'),
                    html.Div([
                        dcc.Input(id='absolute-position-input', type='number', min=0, max=6000, value=0,
                                  className='form-input', style={'width': '120px'}),
                        html.Button("Move", id='move-absolute-btn', className='control-button')
                    ], className='input-row')
                ], className='control-group'),
                html.Div([
                    html.Label("Quick Positions:", className='input-label'),
                    html.Div([
                        html.Button("Bottom (0)", id='move-bottom-btn', className='control-button',
                                    style={'width': '110px'}),
                        html.Button("Top (6000)", id='move-top-btn', className='control-button',
                                    style={'width': '110px'}),
                    ], className='button-group')
                ], className='control-group')
            ], className='card layout-col')
        ], className='layout-row'),

        # Bottom Row - Volume and Speed Control
        html.Div([
            # Aspirate/Dispense Control
            html.Div([
                html.H3([html.I(className="fas fa-tint", style={'marginRight': '8px'}), "Volume Control"],
                        className='section-title'),
                html.Div([
                    html.Label("Volume (μL):", className='input-label'),
                    dcc.Input(id='volume-input', type='number', min=1, max=50000, value=100,
                              className='form-input', style={'width': '120px'})
                ], className='input-group'),
                html.Div([
                    html.Button([html.I(className="fas fa-arrow-up", style={'marginRight': '6px'}), "Aspirate"],
                                id='aspirate-btn', className='control-button success',
                                style={'width': '130px'}),
                    html.Button([html.I(className="fas fa-arrow-down", style={'marginRight': '6px'}), "Dispense"],
                                id='dispense-btn', className='control-button danger',
                                style={'width': '130px'}),
                ], className='button-group')
            ], className='card layout-col'),

            # Speed Control
            html.Div([
                html.H3([html.I(className="fas fa-tachometer-alt", style={'marginRight': '8px'}), "Speed Settings"],
                        className='section-title'),
                html.Div([
                    html.Label("Start Speed:", className='input-label'),
                    html.Div([
                        dcc.Slider(id='start-speed-slider', min=1, max=1000, value=50, step=1,
                                   tooltip={"placement": "bottom", "always_visible": True})
                    ], className='slider-container')
                ], className='control-group'),
                html.Div([
                    html.Label("Top Speed:", className='input-label'),
                    html.Div([
                        dcc.Slider(id='top-speed-slider', min=1, max=5800, value=1000, step=1,
                                   tooltip={"placement": "bottom", "always_visible": True})
                    ], className='slider-container')
                ], className='control-group'),
                html.Div([
                    html.Label("Cutoff Speed:", className='input-label'),
                    html.Div([
                        dcc.Slider(id='cutoff-speed-slider', min=1, max=1000, value=50, step=1,
                                   tooltip={"placement": "bottom", "always_visible": True})
                    ], className='slider-container')
                ], className='control-group'),
                html.Button([html.I(className="fas fa-check", style={'marginRight': '8px'}), "Apply Settings"],
                            id='apply-speed-btn', className='control-button success',
                            style={'width': '100%', 'marginTop': '1rem'})
            ], className='card layout-col')
        ], className='layout-row'),

        # P&ID Diagram and Flow Control Section
        html.Div([
            html.H3([html.I(className="fas fa-project-diagram", style={'marginRight': '8px'}),
                     "System P&ID & Flow Control"],
                    className='section-title'),

            # P&ID Diagram
            html.Div(id='manual-pid-diagram', style={'padding': '20px', 'minHeight': '250px', 'marginBottom': '20px'}),

            # Flow Control Panel
            html.Div([
                # Inlet Valve Selection
                html.Div([
                    html.Label("Inlet Valve Selection:", className='input-label'),
                    dcc.Dropdown(
                        id='inlet-valve-dropdown',
                        options=[{'label': f'A{i}', 'value': f'A{i}'} for i in range(1, 10)],  # Support 9-port valve
                        value='A1',
                        style={'width': '100px'}
                    )
                ], style={'marginBottom': '15px'}),

                # Outlet Valve Selection
                html.Div([
                    html.Label("Outlet Valve:", className='input-label'),
                    dcc.RadioItems(
                        id='outlet-valve-radio',
                        options=[
                            {'label': 'Collect', 'value': 'Collect'},
                            {'label': 'Waste', 'value': 'Waste'}
                        ],
                        value='Collect',
                        inline=True,
                        style={'marginTop': '5px'}
                    )
                ], style={'marginBottom': '15px'}),

                # Flow Rate Setting
                html.Div([
                    html.Label("Flow Rate (mL/min):", className='input-label'),
                    html.Div([
                        dcc.Input(id='continuous-flow-rate', type='number', min=0.1, max=10.0,
                                  value=1.0, step=0.1, className='form-input', style={'width': '100px'}),
                        html.Span(id='calculated-pump-speed',
                                  children="Pump Speed: 0 steps/sec",
                                  style={'marginLeft': '15px', 'fontSize': '0.9rem', 'color': 'var(--text-secondary)'})
                    ], className='input-row')
                ], style={'marginBottom': '15px'}),

                # Syringe Size Setting
                html.Div([
                    html.Label("Syringe Size (mL):", className='input-label'),
                    dcc.Dropdown(
                        id='syringe-size-dropdown',
                        options=[
                            {'label': '1 mL', 'value': 1.0},
                            {'label': '2.5 mL', 'value': 2.5},
                            {'label': '5 mL', 'value': 5.0},
                            {'label': '10 mL', 'value': 10.0},
                            {'label': '25 mL', 'value': 25.0},
                        ],
                        value=5.0,
                        style={'width': '120px'}
                    )
                ], style={'marginBottom': '20px'}),

                # Flow Control Buttons
                html.Div([
                    html.Button(
                        [html.I(className="fas fa-play", style={'marginRight': '6px'}), "Start Continuous Flow"],
                        id='start-flow-btn', className='control-button success',
                        style={'width': '180px', 'marginRight': '10px'}),
                    html.Button([html.I(className="fas fa-stop", style={'marginRight': '6px'}), "Stop Flow"],
                                id='stop-flow-btn', className='control-button danger',
                                style={'width': '120px'}),
                ], className='button-group'),

                # Flow Status Display
                html.Div(id='flow-control-status',
                         children="Flow Control: Stopped",
                         style={'marginTop': '15px', 'padding': '10px', 'backgroundColor': '#f8fafc',
                                'borderRadius': '8px', 'textAlign': 'center', 'fontWeight': '600'})
            ], style={'padding': '20px', 'backgroundColor': '#f8fafc', 'borderRadius': '8px'})

        ], className='card', style={'marginTop': '1.5rem'})
    ], style={'margin': '1.5rem', 'maxWidth': '1400px', 'marginLeft': 'auto', 'marginRight': 'auto'})


# Method Editor Layout
def create_method_editor_layout():
    return html.Div([
        html.Div([
            # Method Steps Display
            html.Div([
                html.H3([html.I(className="fas fa-list"), " Method Steps"]),
                html.Div([
                    html.Button([html.I(className="fas fa-upload"), " Load"], className='control-button',
                                style={'margin': '5px'}),
                    html.Button([html.I(className="fas fa-download"), " Save"], className='control-button',
                                style={'margin': '5px'}),
                    html.Button([html.I(className="fas fa-trash"), " Clear"], id='clear-method-btn',
                                className='control-button', style={'margin': '5px', 'background': '#ef4444'}),
                ]),
                html.Div(id='method-steps-display',
                         style={'marginTop': '20px', 'maxHeight': '400px', 'overflowY': 'auto'})
            ], className='card', style={'width': '60%', 'display': 'inline-block', 'verticalAlign': 'top'}),

            # Step Editor
            html.Div([
                html.H3("Add Method Step"),
                html.Div([
                    html.Label("Step Type:"),
                    dcc.Dropdown(
                        id='step-type-dropdown',
                        options=[
                            {'label': 'Aspirate', 'value': 'aspirate'},
                            {'label': 'Dispense', 'value': 'dispense'},
                            {'label': 'Move Valve', 'value': 'move_valve'},
                            {'label': 'Wait/Delay', 'value': 'wait'},
                            {'label': 'Wash', 'value': 'wash'}
                        ],
                        value='aspirate'
                    )
                ], style={'marginBottom': '15px'}),

                html.Div([
                    html.Label("Volume (μL):"),
                    dcc.Input(id='step-volume-input', type='number', value=100, min=1, max=50000)
                ], style={'marginBottom': '15px'}),

                html.Div([
                    html.Label("Speed (steps/sec):"),
                    dcc.Input(id='step-speed-input', type='number', value=1000, min=1, max=5800)
                ], style={'marginBottom': '15px'}),

                html.Div([
                    html.Label("Valve Position:"),
                    dcc.Dropdown(
                        id='step-valve-dropdown',
                        options=[
                            {'label': 'Input', 'value': 'Input'},
                            {'label': 'Output', 'value': 'Output'},
                            {'label': 'Bypass', 'value': 'Bypass'}
                        ],
                        value='Input'
                    )
                ], style={'marginBottom': '15px'}),

                html.Div([
                    html.Label("Description:"),
                    dcc.Input(id='step-description-input', type='text', placeholder="Step description")
                ], style={'marginBottom': '15px'}),

                html.Button("Add Step", id='add-step-btn', className='control-button', style={'width': '100%'})
            ], className='card',
                style={'width': '35%', 'display': 'inline-block', 'verticalAlign': 'top', 'marginLeft': '5%'})
        ])
    ], style={'margin': '20px'})


# Configuration Layout
def create_configuration_layout():
    return dbc.Container([
        # Row 1 - Communication and Pump Configuration
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.H4(
                            [html.I(className="fas fa-plug", style={'marginRight': '10px'}), "Communication Settings"],
                            className="text-center mb-0")
                    ]),
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("Serial Port:"),
                                dcc.Dropdown(id='port-dropdown', placeholder="Select port", value='COM12'),
                            ], className="mb-3"),
                        ]),
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("Baud Rate:"),
                                dcc.Dropdown(
                                    id='baud-dropdown',
                                    options=[
                                        {'label': '9600', 'value': 9600},
                                        {'label': '38400', 'value': 38400}
                                    ],
                                    value=9600
                                )
                            ], className="mb-3"),
                        ]),
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("Pump Address:"),
                                dbc.Input(id='pump-address-input', type='number', min=0, max=14, value=1)
                            ], className="mb-3"),
                        ]),
                        dbc.Row([
                            dbc.Col([
                                dbc.ButtonGroup([
                                    dbc.Button("Connect", id='connect-btn', color="success", className="me-2"),
                                    dbc.Button("Disconnect", id='disconnect-btn', color="danger")
                                ], className="d-flex justify-content-center")
                            ])
                        ])
                    ])
                ])
            ], md=6, className="mb-4"),

            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.H4([html.I(className="fas fa-cog", style={'marginRight': '10px'}), "Pump Configuration"],
                                className="text-center mb-0")
                    ]),
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("Valve Type:"),
                                dcc.Dropdown(
                                    id='valve-type-dropdown',
                                    options=[
                                        {'label': '3-Port Valve', 'value': '3-port'},
                                        {'label': '4-Port Valve', 'value': '4-port'},
                                        {'label': 'T-Valve', 'value': 't-valve'},
                                        {'label': '6-Port Distribution', 'value': '6-port'},
                                        {'label': '9-Port Distribution', 'value': '9-port'}
                                    ],
                                    value='9-port'
                                )
                            ], className="mb-3"),
                        ]),
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("Syringe Size:"),
                                dcc.Dropdown(
                                    id='syringe-size-dropdown',
                                    options=[
                                        {'label': '50 μL', 'value': 0.05},
                                        {'label': '100 μL', 'value': 0.1},
                                        {'label': '250 μL', 'value': 0.25},
                                        {'label': '500 μL', 'value': 0.5},
                                        {'label': '1.0 mL', 'value': 1.0},
                                        {'label': '2.5 mL', 'value': 2.5},
                                        {'label': '5.0 mL', 'value': 5.0},
                                        {'label': '10 mL', 'value': 10.0},
                                        {'label': '25 mL', 'value': 25.0},
                                        {'label': '50 mL', 'value': 50.0}
                                    ],
                                    value=25.0
                                )
                            ], className="mb-3"),
                        ]),
                        dbc.Row([
                            dbc.Col([
                                dbc.ButtonGroup([
                                    dbc.Button("Initialize Pump", id='init-pump-btn', color="warning",
                                               className="me-2"),
                                    dbc.Button("Query Status", id='query-status-btn', color="primary")
                                ], className="d-flex justify-content-center")
                            ])
                        ])
                    ])
                ])
            ], md=6, className="mb-4")
        ]),

        # Row 2 - System Information and Status
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.H4([html.I(className="fas fa-info-circle", style={'marginRight': '10px'}),
                                 "System Information"],
                                className="text-center mb-0")
                    ]),
                    dbc.CardBody([
                        html.Div(id='system-info-display')
                    ])
                ])
            ], md=6, className="mb-4"),

            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.H4([html.I(className="fas fa-exclamation-triangle", style={'marginRight': '10px'}),
                                 "Status & Errors"],
                                className="text-center mb-0")
                    ]),
                    dbc.CardBody([
                        html.Div(id='error-log-display')
                    ])
                ])
            ], md=6, className="mb-4")
        ])
    ], fluid=True)


# Callbacks

# Quick Actions Layout
def create_quick_actions_layout():
    return html.Div([
        html.H2([html.I(className="fas fa-bolt", style={'marginRight': '10px'}), "Quick Actions"],
                className='section-title', style={'marginBottom': '2rem'}),

        # Emergency Controls
        html.Div([
            html.H3(
                [html.I(className="fas fa-exclamation-triangle", style={'marginRight': '8px'}), "Emergency Controls"],
                className='section-title'),
            html.Div([
                html.Button([
                    html.I(className="fas fa-stop", style={'marginRight': '8px'}),
                    "EMERGENCY STOP"
                ], id='emergency-stop-btn', className='control-button emergency-button',
                    style={'padding': '1rem 2rem', 'fontSize': '1.1rem'}),

                html.Button([
                    html.I(className="fas fa-pause", style={'marginRight': '8px'}),
                    "Pause Operation"
                ], id='pause-operation-btn', className='control-button warning'),

                html.Button([
                    html.I(className="fas fa-play", style={'marginRight': '8px'}),
                    "Resume Operation"
                ], id='resume-operation-btn', className='control-button success')
            ], className='button-group')
        ], className='card'),

        # Flow Control Section
        html.Div([
            html.Div([
                html.H3([html.I(className="fas fa-tint", style={'marginRight': '8px'}), "Flow Rate Presets"],
                        className='section-title'),
                html.P("Click to start continuous flow at preset rate:",
                       style={'marginBottom': '1rem', 'color': 'var(--text-secondary)'}),
                html.Div([
                    html.Div(f"{rate} mL/min",
                             id={'type': 'flow-preset', 'index': i},
                             className='quick-preset')
                    for i, rate in enumerate(controller.flow_presets)
                ], style={'marginBottom': '1.5rem'}),

                html.Div([
                    html.Label("Custom Flow Rate:", className='input-label'),
                    html.Div([
                        dcc.Input(id='custom-flow-input', type='number', value=1.0, min=0.01, max=50.0, step=0.01,
                                  className='form-input', style={'width': '120px'}),
                        html.Span("mL/min", style={'marginLeft': '8px', 'color': 'var(--text-secondary)'})
                    ], className='input-row', style={'marginBottom': '1rem'}),
                    html.Div([
                        html.Button(
                            [html.I(className="fas fa-arrow-up", style={'marginRight': '6px'}), "Start Aspirate"],
                            id='start-aspirate-btn', className='control-button success'),
                        html.Button(
                            [html.I(className="fas fa-arrow-down", style={'marginRight': '6px'}), "Start Dispense"],
                            id='start-dispense-btn', className='control-button info'),
                        html.Button([html.I(className="fas fa-stop", style={'marginRight': '6px'}), "Stop Flow"],
                                    id='stop-flow-btn', className='control-button danger')
                    ], className='button-group')
                ])
            ], className='card layout-col'),

            # Volume Presets
            html.Div([
                html.H3([html.I(className="fas fa-flask", style={'marginRight': '8px'}), "Volume Presets"],
                        className='section-title'),
                html.P("Quick volume operations (aspirate):",
                       style={'marginBottom': '1rem', 'color': 'var(--text-secondary)'}),
                html.Div([
                    html.Div(f"{vol} μL",
                             id={'type': 'volume-preset', 'index': i},
                             className='quick-preset')
                    for i, vol in enumerate(controller.volume_presets)
                ])
            ], className='card layout-col')
        ], className='layout-row'),

        # System Operations
        html.Div([
            html.H3([html.I(className="fas fa-tools", style={'marginRight': '8px'}), "System Operations"],
                    className='section-title'),
            html.Div([
                html.Button([
                    html.I(className="fas fa-fill-drip", style={'marginRight': '8px'}),
                    "Prime System"
                ], id='prime-system-btn', className='control-button info'),

                html.Button([
                    html.I(className="fas fa-sync-alt", style={'marginRight': '8px'}),
                    "Purge System"
                ], id='purge-system-btn', className='control-button warning'),

                html.Button([
                    html.I(className="fas fa-home", style={'marginRight': '8px'}),
                    "Home Position"
                ], id='home-position-btn', className='control-button'),

                html.Button([
                    html.I(className="fas fa-question-circle", style={'marginRight': '8px'}),
                    "Query Status"
                ], id='query-status-quick-btn', className='control-button')
            ], className='button-group')
        ], className='card')
    ], style={'margin': '1.5rem', 'maxWidth': '1400px', 'marginLeft': 'auto', 'marginRight': 'auto'})


# Operation Log Layout
def create_manual_control_layout():
    """Create manual control tab for pump and valve operations"""
    return html.Div([
        html.H2([html.I(className="fas fa-sliders-h", style={'marginRight': '10px'}), "Manual Control"],
                className='page-title'),
        
        # Connection Status Card
        html.Div([
            html.Div([
                html.H3("System Status", className='section-title'),
                html.Div([
                    html.Div([
                        html.Span("Connection: ", style={'fontWeight': '600'}),
                        html.Span(
                            "Connected" if controller.is_connected else "Disconnected",
                            style={'color': '#16a34a' if controller.is_connected else '#dc2626'}
                        )
                    ], style={'marginBottom': '10px'}),
                    html.Div([
                        html.Span("Current Position: ", style={'fontWeight': '600'}),
                        html.Span(f"{controller.current_position} steps", id='manual-current-position')
                    ], style={'marginBottom': '10px'}),
                    html.Div([
                        html.Span("Valve Position: ", style={'fontWeight': '600'}),
                        html.Span(controller.valve_position, id='manual-valve-position')
                    ])
                ], style={'padding': '15px', 'backgroundColor': '#f8fafc', 'borderRadius': '8px'})
            ])
        ], className='card', style={'marginBottom': '20px'}),
        
        # Manual Pump Control Card
        html.Div([
            html.H3([html.I(className="fas fa-syringe", style={'marginRight': '8px'}), "Pump Control"],
                    className='section-title'),
            
            # Continuous Flow Control
            html.Div([
                html.H4("Continuous Flow Control", style={'marginBottom': '15px', 'fontSize': '1.1rem'}),
                
                # Flow Rate Input
                html.Div([
                    html.Label("Flow Rate (mL/min):", className='input-label'),
                    html.Div([
                        dcc.Input(
                            id='manual-flow-rate',
                            type='number',
                            min=0.01,
                            max=50.0,
                            step=0.01,
                            value=1.0,
                            className='form-input',
                            style={'width': '150px', 'marginRight': '15px'}
                        ),
                        html.Span(
                            id='manual-pump-speed',
                            children="0 steps/sec",
                            style={'color': 'var(--text-secondary)', 'fontSize': '0.9rem'}
                        )
                    ], style={'display': 'flex', 'alignItems': 'center'})
                ], style={'marginBottom': '20px'}),
                
                # Flow Direction
                html.Div([
                    html.Label("Flow Direction:", className='input-label'),
                    dcc.RadioItems(
                        id='manual-flow-direction',
                        options=[
                            {'label': ' Aspirate (Draw In)', 'value': 'aspirate'},
                            {'label': ' Dispense (Push Out)', 'value': 'dispense'}
                        ],
                        value='aspirate',
                        labelStyle={'display': 'inline-block', 'marginRight': '20px'}
                    )
                ], style={'marginBottom': '20px'}),
                
                # Control Buttons
                html.Div([
                    html.Button(
                        [html.I(className="fas fa-play", style={'marginRight': '6px'}), "Start Flow"],
                        id='manual-start-flow',
                        className='control-button success',
                        style={'marginRight': '10px'}
                    ),
                    html.Button(
                        [html.I(className="fas fa-stop", style={'marginRight': '6px'}), "Stop Flow"],
                        id='manual-stop-flow',
                        className='control-button danger',
                        style={'marginRight': '10px'}
                    ),
                    html.Button(
                        [html.I(className="fas fa-pause", style={'marginRight': '6px'}), "Pause"],
                        id='manual-pause-flow',
                        className='control-button warning'
                    )
                ], className='button-group', style={'marginBottom': '20px'}),
                
                # Flow Status
                html.Div(
                    id='manual-flow-status',
                    children="Flow Status: Idle",
                    style={
                        'padding': '12px',
                        'backgroundColor': '#f1f5f9',
                        'borderRadius': '8px',
                        'textAlign': 'center',
                        'fontWeight': '600'
                    }
                )
            ], style={'padding': '20px', 'backgroundColor': '#fafbfc', 'borderRadius': '8px', 'marginBottom': '20px'}),
            
            # Manual Volume Control
            html.Div([
                html.H4("Volume Control", style={'marginBottom': '15px', 'fontSize': '1.1rem'}),
                
                html.Div([
                    html.Div([
                        html.Label("Volume (μL):", className='input-label'),
                        dcc.Input(
                            id='manual-volume',
                            type='number',
                            min=1,
                            max=25000,
                            step=1,
                            value=100,
                            className='form-input',
                            style={'width': '150px'}
                        )
                    ], style={'marginRight': '30px'}),
                    
                    html.Div([
                        html.Label("Speed (μL/sec):", className='input-label'),
                        dcc.Input(
                            id='manual-speed',
                            type='number',
                            min=1,
                            max=5000,
                            step=10,
                            value=100,
                            className='form-input',
                            style={'width': '150px'}
                        )
                    ])
                ], style={'display': 'flex', 'marginBottom': '20px'}),
                
                html.Div([
                    html.Button(
                        [html.I(className="fas fa-arrow-up", style={'marginRight': '6px'}), "Aspirate"],
                        id='manual-aspirate',
                        className='control-button primary',
                        style={'marginRight': '10px'}
                    ),
                    html.Button(
                        [html.I(className="fas fa-arrow-down", style={'marginRight': '6px'}), "Dispense"],
                        id='manual-dispense',
                        className='control-button primary'
                    )
                ], className='button-group'),
                
                # Volume operation status
                html.Div(id='manual-volume-status', style={'marginTop': '10px', 'textAlign': 'center'})
            ], style={'padding': '20px', 'backgroundColor': '#fafbfc', 'borderRadius': '8px'})
        ], className='card', style={'marginBottom': '20px'}),
        
        # Valve Control Card
        html.Div([
            html.H3([html.I(className="fas fa-exchange-alt", style={'marginRight': '8px'}), "Valve Control"],
                    className='section-title'),
            
            # Inlet Valve Selection
            html.Div([
                html.H4("Inlet Valve Selection", style={'marginBottom': '15px', 'fontSize': '1.1rem'}),
                html.Div([
                    html.Button(
                        f"A{i}",
                        id={'type': 'manual-inlet-valve', 'index': i},
                        className='valve-button' + (' valve-button-active' if f'A{i}' == controller.selected_inlet_valve else ''),
                        style={'width': '60px', 'marginRight': '10px', 'marginBottom': '10px'}
                    )
                    for i in range(1, 10)
                ]),
                html.Div(id='manual-inlet-status', style={'marginTop': '10px', 'textAlign': 'center'})
            ], style={'marginBottom': '25px'}),
            
            # Outlet Valve Selection
            html.Div([
                html.H4("Outlet Valve Selection", style={'marginBottom': '15px', 'fontSize': '1.1rem'}),
                html.Div([
                    html.Button(
                        "Waste",
                        id='manual-outlet-waste',
                        className='valve-button' + (' valve-button-active' if controller.selected_outlet_valve == 'Waste' else ''),
                        style={'width': '100px', 'marginRight': '10px'}
                    ),
                    html.Button(
                        "Collect",
                        id='manual-outlet-collect',
                        className='valve-button' + (' valve-button-active' if controller.selected_outlet_valve == 'Collect' else ''),
                        style={'width': '100px'}
                    )
                ]),
                html.Div(id='manual-outlet-status', style={'marginTop': '10px', 'textAlign': 'center'})
            ], style={'marginBottom': '25px'}),
            
            # System Operations
            html.Div([
                html.H4("System Operations", style={'marginBottom': '15px', 'fontSize': '1.1rem'}),
                html.Div([
                    html.Button(
                        [html.I(className="fas fa-fill-drip", style={'marginRight': '6px'}), "Prime System"],
                        id='manual-prime',
                        className='control-button secondary',
                        style={'marginRight': '10px'}
                    ),
                    html.Button(
                        [html.I(className="fas fa-tint", style={'marginRight': '6px'}), "Wash Valve"],
                        id='manual-wash',
                        className='control-button secondary',
                        style={'marginRight': '10px'}
                    ),
                    html.Button(
                        [html.I(className="fas fa-home", style={'marginRight': '6px'}), "Home"],
                        id='manual-home',
                        className='control-button secondary'
                    )
                ]),
                html.Div(id='manual-system-status', style={'marginTop': '10px', 'textAlign': 'center'})
            ])
        ], className='card'),
        
        # Update interval for real-time status
        dcc.Interval(id='manual-update-interval', interval=1000, n_intervals=0)
        
    ], style={'margin': '1.5rem', 'maxWidth': '1200px', 'marginLeft': 'auto', 'marginRight': 'auto'})


def create_operation_log_layout():
    return html.Div([
        html.H2([html.I(className="fas fa-clipboard-list", style={'marginRight': '10px'}), "Operation Log"],
                className='section-title', style={'marginBottom': '2rem'}),

        html.Div([
            html.Div([
                html.Button([
                    html.I(className="fas fa-download", style={'marginRight': '8px'}),
                    "Export CSV"
                ], id='export-log-btn', className='control-button info'),

                html.Button([
                    html.I(className="fas fa-trash", style={'marginRight': '8px'}),
                    "Clear Log"
                ], id='clear-log-btn', className='control-button danger'),

                dcc.Dropdown(
                    id='log-filter-dropdown',
                    options=[
                        {'label': 'All Messages', 'value': 'all'},
                        {'label': 'Info Only', 'value': 'info'},
                        {'label': 'Warnings Only', 'value': 'warning'},
                        {'label': 'Errors Only', 'value': 'error'}
                    ],
                    value='all',
                    style={'width': '150px', 'marginLeft': '1rem'}
                )
            ], className='button-group', style={'marginBottom': '1.5rem'}),

            html.Div(id='operation-log-display', className='operation-log')
        ], className='card')
    ], style={'margin': '1.5rem', 'maxWidth': '1400px', 'marginLeft': 'auto', 'marginRight': 'auto'})


@app.callback(
    Output('tab-content', 'children'),
    Input('main-tabs', 'value')
)
def update_tab_content(active_tab):
    if active_tab == 'dashboard':
        return create_dashboard_layout()
    elif active_tab == 'sequence':
        return create_sequence_builder_layout()
    elif active_tab == 'manual':
        return create_manual_control_layout()
    elif active_tab == 'config':
        return create_configuration_layout()
    elif active_tab == 'log':
        return create_operation_log_layout()
    return html.Div("Select a tab")


@app.callback(
    Output('connection-status', 'children'),
    Input('status-interval', 'n_intervals')
)
def update_connection_status(n):
    if controller.is_connected:
        return html.Span([
            html.I(className="fas fa-circle", style={'color': '#10b981', 'marginRight': '5px'}),
            f"Connected - {controller.status}"
        ], className='status-connected')
    else:
        return html.Span([
            html.I(className="fas fa-circle", style={'color': '#ef4444', 'marginRight': '5px'}),
            f"Disconnected - {controller.status}"
        ], className='status-disconnected')


@app.callback(
    [Output('process-volume-display', 'children'),
     Output('block-volume-display', 'children'),
     Output('time-display', 'children'),
     Output('sample-flow-display', 'children'),
     Output('sample-pressure-display', 'children'),
     Output('uv-280-display', 'children'),
     Output('pid-diagram', 'children')],
    Input('realtime-interval', 'n_intervals')
)
def update_metrics(n):
    controller.add_data_point()

    if controller.data_buffer['pressure']:
        pressure_val = controller.data_buffer['pressure'][-1]
        flow_val = controller.data_buffer['flow_rate'][-1]
        volume_val = controller.data_buffer['volume'][-1]

        pressure = f"{pressure_val:.1f} psi"
        flow = f"{flow_val:.2f} mL/min"
        volume = f"{volume_val:.0f} μL"

        # Status indicators
        pressure_status = "ALARM" if pressure_val > controller.pressure_limit else "Normal"
        flow_status = "Active" if abs(flow_val) > 0.1 else "Idle"

        # Process tracking
        step_volume = f"{controller.step_volume} μL"
        total_volume = f"{controller.total_volume} μL"
        process_step = controller.current_step
        step_status = f"Step {controller.step_number}"
        total_percentage = (
                controller.total_volume / controller.target_total_volume * 100) if controller.target_total_volume > 0 else 0
        total_status = f"{total_percentage:.1f}%"
        step_progress = f"{controller.step_number}/{controller.total_steps}"

        # UNICORN-Style Parameters
        process_volume = f"{controller.total_volume / 1000:.2f} ml"  # Convert μL to ml
        block_volume = f"{controller.step_volume / 1000:.2f} ml"  # Convert μL to ml
        elapsed_time = f"{n * 0.5:.1f} min" if n else "0.0 min"  # Assuming 0.5 min intervals
        sample_flow = f"{abs(flow_val):.2f} ml/min"
        sample_pressure = f"{pressure_val * 0.00689476:.2f} MPa"  # Convert psi to MPa
        uv_280 = f"{volume_val * 0.1:.0f} mAU"  # Simulated UV signal


    else:
        # UNICORN-Style Default values when offline
        process_volume = "0.00 ml"
        block_volume = "0.00 ml"
        elapsed_time = "0.0 min"
        sample_flow = "0.00 ml/min"
        sample_pressure = "0.00 MPa"
        uv_280 = "0 mAU"

    # P&ID Diagram - Enhanced UNICORN-Style with Visual Feedback
    is_flow_active = abs(flow_val if 'flow_val' in locals() else 0) > 0.1
    is_pump_active = controller.operation_state in ['aspirating', 'dispensing']
    current_inlet = getattr(controller, 'current_inlet_valve', 'A1')  # Default to A1
    error_state = controller.operation_state == 'error'

    # Enhanced valve styling with color feedback
    def get_valve_style(valve_name, is_active=False, is_error=False):
        base_style = {
            'width': '45px', 'height': '35px', 'margin': '2px', 'cursor': 'pointer',
            'border': '2px solid', 'borderRadius': '6px', 'fontSize': '0.65rem',
            'fontWeight': '700', 'display': 'flex', 'flexDirection': 'column',
            'alignItems': 'center', 'justifyContent': 'center', 'transition': 'all 0.3s ease',
            'boxShadow': '0 2px 4px rgba(0,0,0,0.1)'
        }

        if is_error:
            base_style.update({
                'backgroundColor': '#fef2f2', 'borderColor': '#ef4444', 'color': '#dc2626'
            })
        elif is_active:
            base_style.update({
                'backgroundColor': '#dcfce7', 'borderColor': '#16a34a', 'color': '#15803d',
                'boxShadow': '0 0 12px rgba(34, 197, 94, 0.4)'
            })
        else:
            base_style.update({
                'backgroundColor': '#f8fafc', 'borderColor': '#64748b', 'color': '#475569'
            })

        return base_style

    # Enhanced pump styling - Made bigger
    pump_style = {
        'width': '120px', 'height': '90px', 'border': '4px solid', 'borderRadius': '12px',
        'display': 'flex', 'flexDirection': 'column', 'alignItems': 'center', 'justifyContent': 'center',
        'cursor': 'pointer', 'transition': 'all 0.3s ease', 'boxShadow': '0 6px 12px rgba(0,0,0,0.2)'
    }

    if error_state:
        pump_style.update({
            'backgroundColor': '#fef2f2', 'borderColor': '#ef4444', 'color': '#dc2626'
        })
    elif is_pump_active:
        pump_style.update({
            'backgroundColor': '#dbeafe', 'borderColor': '#2563eb', 'color': '#1d4ed8',
            'boxShadow': '0 0 16px rgba(37, 99, 235, 0.5)'
        })
    else:
        pump_style.update({
            'backgroundColor': '#f1f5f9', 'borderColor': '#64748b', 'color': '#475569'
        })

    # Thick arrow styling for clean flow visualization
    def get_thick_arrow(direction='right', length='100px'):
        base_style = {
            'display': 'flex', 'alignItems': 'center', 'justifyContent': 'center',
            'fontWeight': '900', 'fontSize': '2.5rem', 'transition': 'all 0.3s ease'
        }

        if direction == 'right':
            base_style.update({
                'width': length, 'height': '40px', 'margin': '0 15px'
            })
            arrow_symbol = '▶'
        elif direction == 'down':
            base_style.update({
                'width': '40px', 'height': length, 'margin': '10px auto',
                'flexDirection': 'column'
            })
            arrow_symbol = '▼'
        else:
            arrow_symbol = '▶'
            base_style.update({
                'width': length, 'height': '40px', 'margin': '0 15px'
            })

        # Color based on flow state
        if is_flow_active and not error_state:
            base_style.update({
                'color': '#2563eb',
                'filter': 'drop-shadow(0 2px 8px rgba(37, 99, 235, 0.4))',
                'animation': 'arrow-pulse 1.5s ease-in-out infinite'
            })
        elif error_state:
            base_style.update({
                'color': '#ef4444',
                'filter': 'drop-shadow(0 2px 8px rgba(239, 68, 68, 0.4))'
            })
        else:
            base_style.update({
                'color': '#9ca3af',
                'filter': 'drop-shadow(0 1px 3px rgba(0, 0, 0, 0.1))'
            })

        return html.Div(arrow_symbol, style=base_style)

    # Create professional SVG-based P&ID diagram
    pid_diagram = html.Div([
        html.Svg([
            # Background grid pattern for professional look
            html.Defs([
                html.Pattern([
                    html.Path(d="M 10 0 L 0 0 0 10", fill="none", stroke="#f1f5f9", strokeWidth="0.5")
                ], id="grid", width="10", height="10", patternUnits="userSpaceOnUse")
            ]),
            html.Rect(x="0", y="0", width="100%", height="100%", fill="url(#grid)"),
            
            # Buffer vessels (top row)
            html.G([
                html.Text("BUFFER VESSELS", x="150", y="25", 
                         style={'fontSize': '11px', 'fontWeight': '700', 'fill': '#374151', 'textAnchor': 'middle'}),
                # Individual buffer vessels A1-A9
                *[html.G([
                    html.Circle(cx=50 + i * 25, cy=50, r=10,
                               fill='#3b82f6' if f'A{i + 1}' == current_inlet else '#e2e8f0',
                               stroke='#1e40af' if f'A{i + 1}' == current_inlet else '#9ca3af', 
                               strokeWidth=2,
                               style={'cursor': 'pointer', 'transition': 'all 0.3s ease'},
                               id=f'pid-inlet-a{i + 1}'),
                    html.Text(f'A{i + 1}', x=50 + i * 25, y=55, textAnchor='middle',
                             style={'fontSize': '8px', 'fontWeight': '600', 'fill': 'white' if f'A{i + 1}' == current_inlet else '#374151'}),
                    # Buffer lines going down
                    html.Line(x1=50 + i * 25, y1=60, x2=50 + i * 25, y2=80, 
                             stroke='#3b82f6' if f'A{i + 1}' == current_inlet and is_flow_active else '#9ca3af', 
                             strokeWidth=2)
                ]) for i in range(9)]
            ]),
            
            # Manifold collection line (horizontal)
            html.Line(x1="40", y1="80", x2="260", y2="80", 
                     stroke='#3b82f6' if is_flow_active else '#6b7280', strokeWidth=3,
                     strokeDasharray="0" if is_flow_active else "5,5"),
            
            # Main flow line to pump
            html.Line(x1="260", y1="80", x2="320", y2="80", 
                     stroke='#3b82f6' if is_flow_active else '#6b7280', strokeWidth=4),
            
            # Flow direction arrow to pump
            *([html.Polygon(points="315,75 325,80 315,85", 
                           fill='#3b82f6', opacity=0.9)] if is_flow_active else []),
            
            # XLP 6000 Syringe Pump (enhanced design)
            html.G([
                # Pump body
                html.Rect(x="330", y="60", width="60", height="40", rx="8", 
                         fill='linear-gradient(135deg, #1e40af 0%, #3b82f6 100%)' if is_pump_active else '#64748b',
                         stroke='#1e3a8a', strokeWidth=2,
                         style={'cursor': 'pointer', 'filter': 'drop-shadow(0 4px 8px rgba(0,0,0,0.2))'},
                         id='pid-pump-main'),
                # Syringe representation
                html.Rect(x="335", y="50", width="8", height="15", rx="2", fill='#f3f4f6', stroke='#9ca3af'),
                html.Rect(x="337", y="52", width="4", height=f"{8 * (controller.current_position / 6000) if controller.current_position else 2}", 
                         fill='#3b82f6'),
                # Pump labels
                html.Text("XLP 6000", x="360", y="75", textAnchor='middle',
                         style={'fontSize': '9px', 'fontWeight': '700', 'fill': 'white'}),
                html.Text("SYRINGE PUMP", x="360", y="88", textAnchor='middle',
                         style={'fontSize': '6px', 'fontWeight': '500', 'fill': 'white'}),
                
                # Direct waste line from pump
                html.Line(x1="360", y1="100", x2="360", y2="130", stroke='#ef4444', strokeWidth=2,
                         opacity=0.7 if controller.valve_position == 'Waste' else 0.3),
                html.Circle(cx="360", cy="135", r="6", 
                           fill='#ef4444' if controller.valve_position == 'Waste' else '#fca5a5',
                           stroke='#dc2626', strokeWidth=1, style={'cursor': 'pointer'}, id='pid-pump-waste'),
                html.Text("WASTE", x="360", y="150", textAnchor='middle',
                         style={'fontSize': '7px', 'fontWeight': '600', 'fill': '#dc2626'})
            ]),
            
            # Flow line from pump to column
            html.Line(x1="390", y1="80", x2="480", y2="80", 
                     stroke='#3b82f6' if is_flow_active else '#6b7280', strokeWidth=4),
            
            # Flow arrow to column
            *([html.Polygon(points="475,75 485,80 475,85", 
                           fill='#3b82f6', opacity=0.9)] if is_flow_active else []),
            
            # Chromatography Column (more realistic design)
            html.G([
                html.Text("COLUMN", x="520", y="35", textAnchor='middle',
                         style={'fontSize': '9px', 'fontWeight': '700', 'fill': '#1e40af'}),
                # Column body
                html.Rect(x="500", y="50", width="40", height="80", rx="4",
                         fill='linear-gradient(180deg, #f0f9ff 0%, #dbeafe 50%, #3b82f6 100%)',
                         stroke='#1e40af', strokeWidth=2,
                         style={'filter': 'drop-shadow(0 2px 4px rgba(0,0,0,0.1))'}),
                # Packed bed representation
                html.Rect(x="505", y="60", width="30", height="60", rx="2",
                         fill='url(#beadPattern)', opacity=0.6),
                # Inlet/outlet ports
                html.Circle(cx="495", cy="80", r="3", fill='#1e40af'),
                html.Circle(cx="545", cy="80", r="3", fill='#1e40af'),
                # Flow indicators
                html.Text("IN", x="485", y="85", style={'fontSize': '6px', 'fill': '#1e40af'}),
                html.Text("OUT", x="550", y="85", style={'fontSize': '6px', 'fill': '#1e40af'})
            ]),
            
            # Define bead pattern for packed column
            html.Defs([
                html.Pattern([
                    *[html.Circle(cx=2 + (i % 5) * 3, cy=2 + (i // 5) * 3, r="0.8", 
                                 fill='#60a5fa', opacity=0.7) for i in range(25)]
                ], id="beadPattern", width="15", height="15", patternUnits="userSpaceOnUse")
            ]),
            
            # Flow line from column to selector valve
            html.Line(x1="545", y1="80", x2="600", y2="80", 
                     stroke='#3b82f6' if is_flow_active else '#6b7280', strokeWidth=4),
            
            # 3-way selector valve
            html.G([
                html.Circle(cx="620", cy="80", r="20", 
                           fill='#8b5cf6' if is_flow_active else '#a78bfa',
                           stroke='#7c3aed', strokeWidth=2,
                           style={'cursor': 'pointer', 'filter': 'drop-shadow(0 2px 4px rgba(0,0,0,0.15))'}),
                html.Text("3-WAY", x="620", y="85", textAnchor='middle',
                         style={'fontSize': '8px', 'fontWeight': '700', 'fill': 'white'}),
                
                # Waste line (upward)
                html.Line(x1="620", y1="60", x2="620", y2="30", 
                         stroke='#ef4444' if controller.valve_position == 'Bypass' else '#fca5a5', 
                         strokeWidth=3),
                html.Circle(cx="620", cy="25", r="8", 
                           fill='#ef4444' if controller.valve_position == 'Bypass' else '#fca5a5',
                           stroke='#dc2626', strokeWidth=2, style={'cursor': 'pointer'}, id='pid-outlet-waste'),
                html.Text("WASTE", x="620", y="15", textAnchor='middle',
                         style={'fontSize': '8px', 'fontWeight': '600', 'fill': '#dc2626'}),
                
                # Collection line (rightward)
                html.Line(x1="640", y1="80", x2="700", y2="80", 
                         stroke='#10b981' if controller.valve_position == 'Output' else '#86efac', 
                         strokeWidth=3),
                html.Circle(cx="705", cy="80", r="8", 
                           fill='#10b981' if controller.valve_position == 'Output' else '#86efac',
                           stroke='#059669', strokeWidth=2, style={'cursor': 'pointer'}, id='pid-outlet-collect'),
                html.Text("COLLECT", x="705", y="100", textAnchor='middle',
                         style={'fontSize': '8px', 'fontWeight': '600', 'fill': '#059669'})
            ]),
            
            # Flow direction arrows in waste/collect lines
            *([
                html.Polygon(points="617,35 620,30 623,35", fill='#ef4444', opacity=0.8) 
                if controller.valve_position == 'Bypass' else
                html.Polygon(points="690,75 700,80 690,85", fill='#10b981', opacity=0.8)
            ] if is_flow_active else []),
            
            # Real-time flow animation (moving dots)
            *([
                html.Circle(cx="280", cy="80", r="2", fill='#3b82f6', opacity=0.8),
                html.Circle(cx="450", cy="80", r="2", fill='#3b82f6', opacity=0.6),
                html.Circle(cx="570", cy="80", r="2", fill='#3b82f6', opacity=0.4),
                html.AnimateTransform(attributeName="transform", attributeType="XML",
                                    type="translate", values="0 0; 400 0; 0 0", dur="3s", repeatCount="indefinite")
            ] if is_flow_active else []),
            
            # Pressure and flow indicators
            html.G([
                html.Text("SYSTEM STATUS", x="400", y="160", textAnchor='middle',
                         style={'fontSize': '10px', 'fontWeight': '700', 'fill': '#374151'}),
                html.Text(f"Pressure: {controller.data_buffer['pressure'][-1]:.1f} psi" if controller.data_buffer['pressure'] else "Pressure: 0.0 psi", 
                         x="300", y="175", style={'fontSize': '8px', 'fill': '#6b7280'}),
                html.Text(f"Flow: {controller.current_flow_rate:.2f} mL/min", 
                         x="300", y="185", style={'fontSize': '8px', 'fill': '#6b7280'}),
                html.Text(f"Position: {controller.current_position} steps", 
                         x="500", y="175", style={'fontSize': '8px', 'fill': '#6b7280'}),
                html.Text(f"Mode: {controller.operation_state.title()}", 
                         x="500", y="185", style={'fontSize': '8px', 'fill': '#6b7280'})
            ])
            
        ], viewBox="0 0 750 200", 
           style={'width': '100%', 'height': '280px', 'background': '#ffffff', 'border': '1px solid #e5e7eb', 'borderRadius': '8px'})
    ])

    # Operation status
    operation_status = html.Div([
        html.Div([
            html.Span("Status: ", style={'fontWeight': '600'}),
            html.Span(controller.operation_state.title(), style={
                'color': '#059669' if controller.operation_state == 'idle' else '#d97706',
                'fontWeight': '700'
            })
        ], style={'marginBottom': '8px', 'fontSize': '0.875rem'}),
        html.Div([
            html.Span("Flow Mode: ", style={'fontWeight': '600'}),
            html.Span("Continuous" if controller.is_continuous_mode else "Discrete", style={
                'color': '#2563eb' if controller.is_continuous_mode else '#64748b'
            })
        ], style={'marginBottom': '8px', 'fontSize': '0.875rem'}),
        html.Div([
            html.Span("Target Flow: ", style={'fontWeight': '600'}),
            html.Span(f"{controller.target_flow_rate:.2f} mL/min")
        ], style={'fontSize': '0.875rem'}) if controller.target_flow_rate > 0 else html.Div()
    ])

    return (process_volume, block_volume, elapsed_time, sample_flow, sample_pressure,
            uv_280, pid_diagram)


# UNICORN-Style Chromatogram with Variable Selection
@app.callback(
    Output('realtime-chromatogram', 'figure'),
    [Input('realtime-interval', 'n_intervals'),
     Input('chromatogram-variables', 'value')]
)
def update_chromatogram(n, selected_vars):
    if not selected_vars:
        selected_vars = ['uv280']  # Default if none selected

    if not controller.data_buffer['time']:
        # Create empty chromatogram
        fig = go.Figure()
        if 'uv280' in selected_vars:
            fig.add_trace(go.Scatter(x=[0], y=[0], name='UV_1_280', line=dict(color='#3b82f6', width=2)))
        fig.update_layout(
            title="",
            xaxis_title="Volume (ml)",
            yaxis_title="Signal",
            height=350,
            showlegend=True,
            template="plotly_white",
            margin=dict(l=60, r=60, t=30, b=40)
        )
        return fig

    fig = go.Figure()

    # Convert time to volume (assuming flow rate)
    times = list(controller.data_buffer['time'])
    # Convert datetime to minutes from start
    if times:
        start_time = times[0]
        time_minutes = [(t - start_time).total_seconds() / 60.0 for t in times]
        volumes = [t * 1.0 for t in time_minutes]  # Assuming 1 ml/min flow rate
    else:
        volumes = [0]

    # Add traces based on selection
    if 'uv280' in selected_vars:
        # UV 280 trace (simulated from volume data)
        uv_values = [vol * 0.1 * (1 + 0.1 * abs(vol - 10)) for vol in controller.data_buffer['volume']]
        fig.add_trace(go.Scatter(
            x=volumes,
            y=uv_values,
            name='UV_1_280',
            line=dict(color='#3b82f6', width=2)
        ))

    if 'cond' in selected_vars:
        # Conductivity trace (simulated)
        cond_values = [100 + 10 * (vol % 5) for vol in volumes]
        fig.add_trace(go.Scatter(
            x=volumes,
            y=cond_values,
            name='Cond',
            line=dict(color='#f59e0b', width=2),
            yaxis='y2'
        ))

    if 'pressure' in selected_vars:
        # Pressure trace
        pressure_values = list(controller.data_buffer['pressure'])
        fig.add_trace(go.Scatter(
            x=volumes,
            y=pressure_values,
            name='Pressure',
            line=dict(color='#ef4444', width=2),
            yaxis='y3'
        ))

    if 'flow' in selected_vars:
        # Flow rate trace
        flow_values = list(controller.data_buffer['flow_rate'])
        fig.add_trace(go.Scatter(
            x=volumes,
            y=flow_values,
            name='Flow Rate',
            line=dict(color='#10b981', width=2),
            yaxis='y4'
        ))

    # Configure layout based on selected variables
    fig.update_layout(
        title="",
        xaxis_title="Volume (ml)",
        height=350,
        showlegend=True,
        legend=dict(x=0, y=1),
        template="plotly_white",
        margin=dict(l=60, r=60, t=30, b=40),
        plot_bgcolor='white'
    )

    # Configure y-axes based on what's selected
    if 'uv280' in selected_vars:
        fig.update_layout(yaxis=dict(title="mAU", side="left", color='#3b82f6'))
    if 'cond' in selected_vars:
        fig.update_layout(yaxis2=dict(title="mS/cm", side="right", overlaying="y", color='#f59e0b'))
    if 'pressure' in selected_vars:
        fig.update_layout(yaxis3=dict(title="psi", side="left", overlaying="y", position=0.05, color='#ef4444'))
    if 'flow' in selected_vars:
        fig.update_layout(yaxis4=dict(title="mL/min", side="right", overlaying="y", position=0.95, color='#10b981'))

    return fig


@app.callback(
    [Output('port-dropdown', 'options'),
     Output('port-dropdown', 'value')],
    [Input('main-tabs', 'value'),  # Trigger when config tab is accessed
     Input('status-interval', 'n_intervals')]  # Also trigger on page load/refresh
)
def update_port_options(active_tab, n_intervals):
    if active_tab == 'config' or n_intervals == 1:  # On config tab or first load
        ports = controller.get_available_ports()
        options = [{'label': port, 'value': port} for port in ports]
        # Default to COM12 if available, otherwise use first port
        if 'COM12' in ports:
            value = 'COM12'
        else:
            value = ports[0] if ports else None
        return options, value
    return [], None


# Manual control callbacks - removed duplicate, using interactive P&ID callbacks instead


@app.callback(
    Output('aspirate-btn', 'children'),
    Input('aspirate-btn', 'n_clicks'),
    State('volume-input', 'value')
)
def handle_aspirate(n_clicks, volume):
    if n_clicks and volume:
        controller.aspirate(volume)
        return [html.I(className="fas fa-arrow-up"), f" Aspirated {volume}μL"]
    return [html.I(className="fas fa-arrow-up"), " Aspirate"]


@app.callback(
    Output('dispense-btn', 'children'),
    Input('dispense-btn', 'n_clicks'),
    State('volume-input', 'value')
)
def handle_dispense(n_clicks, volume):
    if n_clicks and volume:
        controller.dispense(volume)
        return [html.I(className="fas fa-arrow-down"), f" Dispensed {volume}μL"]
    return [html.I(className="fas fa-arrow-down"), " Dispense"]


@app.callback(
    Output('move-absolute-btn', 'children'),
    Input('move-absolute-btn', 'n_clicks'),
    State('absolute-position-input', 'value')
)
def handle_absolute_move(n_clicks, position):
    if n_clicks and position is not None:
        controller.move_syringe_absolute(position)
        return f"Moved to {position}"
    return "Move"


# Configuration callbacks
@app.callback(
    Output('connect-btn', 'children'),
    Input('connect-btn', 'n_clicks'),
    State('port-dropdown', 'value'),
    State('baud-dropdown', 'value'),
    State('pump-address-input', 'value')
)
def handle_connect(n_clicks, port, baud, address):
    if n_clicks and port:
        controller.pump_address = address or 1
        if controller.connect(port, baud):
            return [html.I(className="fas fa-check"), " Connected"]
        else:
            return [html.I(className="fas fa-times"), " Connection Failed"]
    return "Connect"


@app.callback(
    Output('disconnect-btn', 'children'),
    Input('disconnect-btn', 'n_clicks')
)
def handle_disconnect(n_clicks):
    if n_clicks:
        controller.disconnect()
        return [html.I(className="fas fa-check"), " Disconnected"]
    return "Disconnect"


@app.callback(
    Output('command-history-display', 'children'),
    Input('realtime-interval', 'n_intervals')
)
def update_command_history(n):
    if not controller.command_history:
        return html.Div("No recent commands", style={'color': 'var(--text-secondary)', 'fontStyle': 'italic'})

    history_items = []
    for cmd in list(controller.command_history)[-6:]:  # Show last 6 commands
        history_items.append(
            html.Div([
                html.Div([
                    html.Code(cmd['command'], style={
                        'fontFamily': 'Fira Code, monospace',
                        'fontSize': '0.75rem',
                        'background': 'rgba(37, 99, 235, 0.1)',
                        'padding': '2px 6px',
                        'borderRadius': '4px',
                        'color': 'var(--primary-color)'
                    }),
                    html.Small(cmd['timestamp'], style={
                        'color': 'var(--text-secondary)',
                        'marginLeft': '8px',
                        'fontSize': '0.7rem'
                    })
                ])
            ], style={
                'marginBottom': '6px',
                'padding': '6px',
                'background': 'rgba(248, 249, 250, 0.5)',
                'borderRadius': '4px',
                'border': '1px solid var(--border-color)'
            })
        )

    return history_items


@app.callback(
    Output('pump-status-display', 'children'),
    Input('status-interval', 'n_intervals')
)
def update_pump_status(n):
    status_items = [
        {'label': 'Pump Address', 'value': str(controller.pump_address), 'icon': 'fas fa-hashtag'},
        {'label': 'Syringe Size', 'value': f"{controller.syringe_size} mL", 'icon': 'fas fa-flask'},
        {'label': 'Communication', 'value': f"{controller.baud_rate} baud", 'icon': 'fas fa-wifi'},
        {'label': 'Top Speed', 'value': f"{controller.speed_settings['top_speed']} steps/sec",
         'icon': 'fas fa-tachometer-alt'},
        {'label': 'Safety Limit', 'value': f"{controller.pressure_limit} psi", 'icon': 'fas fa-shield-alt'},
    ]

    return html.Div([
        html.Div([
            html.Div([
                html.I(className=item['icon'],
                       style={'marginRight': '8px', 'color': 'var(--primary-color)', 'width': '16px'}),
                html.Span(item['label'], style={'fontWeight': '600', 'fontSize': '0.875rem'})
            ], style={'marginBottom': '4px'}),
            html.Div(item['value'],
                     style={'marginLeft': '24px', 'color': 'var(--text-secondary)', 'fontSize': '0.875rem'})
        ], style={'marginBottom': '12px'}) for item in status_items
    ])


# Additional callbacks for new functionality
@app.callback(
    Output('emergency-stop-btn', 'children'),
    Input('emergency-stop-btn', 'n_clicks')
)
def handle_emergency_stop(n_clicks):
    if n_clicks:
        controller.emergency_stop()
        return [html.I(className="fas fa-stop"), " STOPPED"]
    return [html.I(className="fas fa-stop"), " EMERGENCY STOP"]


@app.callback(
    [Output('start-aspirate-btn', 'children'),
     Output('start-dispense-btn', 'children')],
    [Input('start-aspirate-btn', 'n_clicks'),
     Input('start-dispense-btn', 'n_clicks')],
    State('custom-flow-input', 'value')
)
def handle_continuous_flow(aspirate_clicks, dispense_clicks, flow_rate):
    ctx = callback_context
    if ctx.triggered and flow_rate:
        button_id = ctx.triggered[0]['prop_id'].split('.')[0]
        if button_id == 'start-aspirate-btn' and aspirate_clicks:
            controller.start_continuous_flow(flow_rate, "aspirate")
            return [html.I(className="fas fa-arrow-up"), f" Aspirating {flow_rate} mL/min"], [
                html.I(className="fas fa-arrow-down"), " Start Dispense"]
        elif button_id == 'start-dispense-btn' and dispense_clicks:
            controller.start_continuous_flow(flow_rate, "dispense")
            return [html.I(className="fas fa-arrow-up"), " Start Aspirate"], [html.I(className="fas fa-arrow-down"),
                                                                              f" Dispensing {flow_rate} mL/min"]

    return [html.I(className="fas fa-arrow-up"), " Start Aspirate"], [html.I(className="fas fa-arrow-down"),
                                                                      " Start Dispense"]


@app.callback(
    Output('stop-flow-btn', 'children'),
    Input('stop-flow-btn', 'n_clicks')
)
def handle_stop_flow(n_clicks):
    if n_clicks:
        controller.stop_continuous_flow()
        return [html.I(className="fas fa-stop"), " Flow Stopped"]
    return [html.I(className="fas fa-stop"), " Stop Flow"]


@app.callback(
    Output('prime-system-btn', 'children'),
    Input('prime-system-btn', 'n_clicks')
)
def handle_prime_system(n_clicks):
    if n_clicks:
        controller.prime_system()
        return [html.I(className="fas fa-check"), " System Primed"]
    return [html.I(className="fas fa-fill-drip"), " Prime System"]


@app.callback(
    Output('purge-system-btn', 'children'),
    Input('purge-system-btn', 'n_clicks')
)
def handle_purge_system(n_clicks):
    if n_clicks:
        controller.purge_system()
        return [html.I(className="fas fa-check"), " System Purged"]
    return [html.I(className="fas fa-sync-alt"), " Purge System"]


@app.callback(
    Output('home-position-btn', 'children'),
    Input('home-position-btn', 'n_clicks')
)
def handle_home_position(n_clicks):
    if n_clicks:
        controller.move_syringe_absolute(0)
        return [html.I(className="fas fa-check"), " At Home"]
    return [html.I(className="fas fa-home"), " Home Position"]


@app.callback(
    Output('wash-valve-btn', 'children'),
    Input('wash-valve-btn', 'n_clicks')
)
def handle_wash_valve(n_clicks):
    if n_clicks:
        controller.wash_valve()
        return [html.I(className="fas fa-check"), " Valve Washed"]
    return [html.I(className="fas fa-tint"), " Wash Valve"]


@app.callback(
    Output('wash-volume-display', 'children'),
    Input('wash-volume-input', 'value')
)
def update_wash_volume(wash_volume):
    if wash_volume:
        controller.wash_volume = wash_volume
        return f"Wash Volume: {wash_volume} μL"
    return f"Wash Volume: {controller.wash_volume} μL"


# Combined Sequence Builder Callback - handles templates, clearing, and adding steps
@app.callback(
    Output('sequence-store', 'data'),
    [Input('load-template-btn', 'n_clicks'),
     Input('clear-sequence-btn', 'n_clicks'),
     Input('add-equilibrate-btn', 'n_clicks'),
     Input('add-load-btn', 'n_clicks'),
     Input('add-wash-btn', 'n_clicks'),
     Input('add-elute-btn', 'n_clicks'),
     Input('add-regenerate-btn', 'n_clicks'),
     Input('add-hold-btn', 'n_clicks'),
     Input('add-gradient-btn', 'n_clicks')],
    [State('template-dropdown', 'value'),
     State('sequence-store', 'data')]
)
def update_sequence(load_clicks, clear_clicks, equilibrate_clicks, load_clicks_step,
                    wash_clicks, elute_clicks, regenerate_clicks, hold_clicks, gradient_clicks,
                    template_name, current_sequence):
    ctx = callback_context
    if not ctx.triggered:
        return current_sequence or []

    button_id = ctx.triggered[0]['prop_id'].split('.')[0]

    # Handle template loading and clearing
    if button_id == 'load-template-btn' and load_clicks and template_name:
        return controller.method_templates[template_name]
    elif button_id == 'clear-sequence-btn' and clear_clicks:
        # When clearing, still keep the configuration as first step
        return [{"type": "configuration", "name": "Method Configuration", "config": controller.method_config.copy(), "id": 0}]

    # Define step templates for adding from library
    step_templates = {
        'add-equilibrate-btn': {
            'name': 'Equilibrate',
            'valve': 'A1',
            'volume': 5000,
            'flow_rate': 1.0,
            'buffer': 'Equilibration Buffer'
        },
        'add-load-btn': {
            'name': 'Load Sample',
            'valve': 'A2',
            'volume': 1000,
            'flow_rate': 0.5,
            'buffer': 'Sample'
        },
        'add-wash-btn': {
            'name': 'Wash',
            'valve': 'A1',
            'volume': 3000,
            'flow_rate': 1.0,
            'buffer': 'Wash Buffer'
        },
        'add-elute-btn': {
            'name': 'Elute',
            'valve': 'A3',
            'volume': 2000,
            'flow_rate': 0.75,
            'buffer': 'Elution Buffer'
        },
        'add-regenerate-btn': {
            'name': 'Regenerate',
            'valve': 'A4',
            'volume': 3000,
            'flow_rate': 1.0,
            'buffer': 'Regeneration Buffer'
        },
        'add-hold-btn': {
            'name': 'Hold',
            'valve': 'A1',
            'volume': 0,
            'flow_rate': 0,
            'buffer': 'Hold'
        },
        'add-gradient-btn': {
            'name': 'Gradient',
            'valve': 'A3',
            'volume': 10000,
            'flow_rate': 1.0,
            'buffer': 'Gradient'
        }
    }

    if button_id in step_templates:
        new_sequence = current_sequence.copy() if current_sequence else []
        
        # Ensure configuration is always the first step
        if not new_sequence or new_sequence[0].get('type') != 'configuration':
            # Add configuration as first step if it's missing
            new_sequence.insert(0, {"type": "configuration", "name": "Method Configuration", 
                                   "config": controller.method_config.copy(), "id": 0})
            # Re-index all existing steps
            for i, step in enumerate(new_sequence[1:], 1):
                step['id'] = i
        
        new_step = step_templates[button_id].copy()
        new_step['id'] = len(new_sequence)  # Add unique ID for tracking
        new_sequence.append(new_step)
        return new_sequence

    return current_sequence or []


@app.callback(
    Output('sequence-container', 'children'),
    Input('sequence-store', 'data')
)
def update_sequence_display(sequence):
    if not sequence:
        return html.Div("Drop steps here to build your sequence",
                        style={'padding': '40px', 'textAlign': 'center', 'color': '#94a3b8',
                               'border': '2px dashed #cbd5e1', 'borderRadius': '8px'})

    sequence_steps = []
    for i, step in enumerate(sequence):
        # Check if this is a configuration step
        if step.get('type') == 'configuration':
            step_icon = '⚙️'
        else:
            step_icon = {
                'Equilibrate': '🔄',
                'Load Sample': '💉',
                'Wash': '🚿',
                'Elute': '🧪',
                'Regenerate': '♻️',
                'Hold': '⏸️',
                'Gradient': '📊',
                'Method Configuration': '⚙️'
            }.get(step.get('name', ''), '⚙️')

        # Create appropriate display based on step type
        if step.get('type') == 'configuration':
            config = step.get('config', {})
            step_details = f"Column: {config.get('column_resin', 'N/A')} | CV: {config.get('column_volume', 0):.2f}mL | Flow: {config.get('default_flow_rate', 0)}{config.get('default_flow_rate_unit', 'mL/min')}"
            # Configuration step shouldn't be deletable
            action_buttons = html.Div([
                html.Button("✏️", id={'type': 'edit-step', 'index': i},
                            className='control-button', style={'padding': '5px 8px', 'margin': '0 5px'})
            ])
        else:
            step_details = f"Valve: {step.get('valve', 'N/A')} | Volume: {step.get('volume', 0)}μL | Flow: {step.get('flow_rate', 0)}mL/min"
            action_buttons = html.Div([
                html.Button("✏️", id={'type': 'edit-step', 'index': i},
                            className='control-button', style={'padding': '5px 8px', 'margin': '0 5px'}),
                html.Button("🗑️", id={'type': 'delete-step', 'index': i},
                            className='control-button warning', style={'padding': '5px 8px'})
            ])
        
        sequence_steps.append(
            html.Div([
                html.Div(str(i + 1), className='step-number'),
                html.Div([
                    html.H4(f"{step_icon} {step['name']}", style={'margin': '0', 'fontSize': '1rem'}),
                    html.P(step_details, style={'margin': '5px 0 0 0', 'fontSize': '0.8rem', 'color': '#64748b'})
                ], style={'flex': '1'}),
                action_buttons
            ], className='sequence-step' + (' configuration-step' if step.get('type') == 'configuration' else ''), 
            id=f'step-{i}')
        )

    return sequence_steps


# Callback to handle edit and delete buttons for steps
@app.callback(
    [Output('selected-step-index', 'data'),
     Output('sequence-store', 'data', allow_duplicate=True)],
    [Input({'type': 'edit-step', 'index': dash.dependencies.ALL}, 'n_clicks'),
     Input({'type': 'delete-step', 'index': dash.dependencies.ALL}, 'n_clicks')],
    [State('sequence-store', 'data'),
     State('selected-step-index', 'data')],
    prevent_initial_call=True
)
def handle_step_actions(edit_clicks, delete_clicks, sequence, current_selected):
    ctx = callback_context
    if not ctx.triggered:
        return current_selected, sequence

    # Parse which button was clicked
    prop_id = ctx.triggered[0]['prop_id']
    if 'edit-step' in prop_id:
        # Extract index from the pattern-matching ID
        import json
        button_info = json.loads(prop_id.split('.')[0])
        return button_info['index'], sequence  # Set selected index for editing
    elif 'delete-step' in prop_id:
        # Extract index and delete the step
        import json
        button_info = json.loads(prop_id.split('.')[0])
        if sequence and 0 <= button_info['index'] < len(sequence):
            # Don't allow deletion of configuration step (first step)
            if button_info['index'] == 0 and sequence[0].get('type') == 'configuration':
                return current_selected, sequence  # Can't delete configuration
            
            new_sequence = sequence.copy()
            del new_sequence[button_info['index']]
            # Re-index remaining steps
            for i, step in enumerate(new_sequence):
                step['id'] = i
            return None, new_sequence  # Clear selection and return updated sequence

    return current_selected, sequence


# Callback to save edited step parameters
@app.callback(
    Output('sequence-store', 'data', allow_duplicate=True),
    Input('save-step-params-btn', 'n_clicks'),
    [State('selected-step-index', 'data'),
     State('sequence-store', 'data')] +
    # Configuration parameters
    [State('param-column-resin', 'value'),
     State('param-column-diameter', 'value'),
     State('param-column-height', 'value'),
     State('param-default-flow-rate', 'value'),
     State('param-flow-rate-unit', 'value'),
     State('param-volume-unit', 'value')] +
    [State(f'param-buffer-a{i}', 'value') for i in range(1, 10)] +
    # Regular step parameters
    [State('param-name', 'value'),
     State('param-valve', 'value'),
     State('param-volume', 'value'),
     State('param-flow-rate', 'value'),
     State('param-buffer', 'value')],
    prevent_initial_call=True
)
def save_step_parameters(n_clicks, selected_index, sequence, 
                        column_resin, column_diameter, column_height, 
                        default_flow_rate, flow_rate_unit, volume_unit,
                        *args):
    if not n_clicks or selected_index is None or not sequence or selected_index >= len(sequence):
        return sequence
    
    # Extract buffer values and regular step parameters from args
    buffer_values = args[:9]  # First 9 are buffer A1-A9
    name, valve, volume, flow_rate, buffer = args[9:14]  # Next 5 are regular parameters
    
    new_sequence = sequence.copy()
    current_step = new_sequence[selected_index]
    
    # Handle configuration step
    if current_step.get('type') == 'configuration':
        # Create updated configuration
        new_config = controller.method_config.copy()
        new_config['column_resin'] = column_resin or 'Protein A'
        new_config['column_diameter'] = column_diameter or 10.0
        new_config['column_height'] = (column_height or 10.0) * 10  # Convert cm to mm
        new_config['default_flow_rate'] = default_flow_rate or 2.0
        new_config['default_flow_rate_unit'] = flow_rate_unit or 'mL/min'
        new_config['default_volume_unit'] = volume_unit or 'mL'
        
        # Update buffer mapping
        for i, buffer_name in enumerate(buffer_values):
            valve_key = f'A{i + 1}'
            new_config['buffer_map'][valve_key] = buffer_name or f'Buffer A{i + 1}'
        
        # Recalculate column volume
        controller.method_config = new_config
        new_config['column_volume'] = controller.calculate_column_volume()
        
        # Update the configuration step
        new_sequence[selected_index] = {
            'type': 'configuration',
            'name': 'Method Configuration',
            'config': new_config,
            'id': selected_index
        }
    else:
        # Handle regular step
        new_sequence[selected_index] = {
            'id': selected_index,
            'name': name,
            'valve': valve,
            'volume': volume,
            'flow_rate': flow_rate,
            'buffer': buffer
        }
    
    return new_sequence


@app.callback(
    Output('step-parameters', 'children'),
    Input('selected-step-index', 'data'),
    State('sequence-store', 'data')
)
def update_step_parameters(selected_index, sequence):
    if selected_index is None or not sequence or selected_index >= len(sequence):
        return html.P("Select a step to edit parameters",
                      style={'textAlign': 'center', 'color': '#94a3b8', 'padding': '20px'})

    step = sequence[selected_index]

    # Handle configuration step differently
    if step.get('type') == 'configuration':
        config = step.get('config', controller.method_config.copy())
        return html.Div([
            html.H4(f"Edit Step {selected_index + 1}: {step['name']}", 
                   style={'marginBottom': '20px', 'color': '#0891b2'}),

            # Row 1: Column Configuration
            html.Div([
                html.Label("Column Resin:", className='input-label'),
                dcc.Input(id='param-column-resin', value=config.get('column_resin', 'Protein A'),
                          className='form-input', style={'width': '100%'})
            ], style={'marginBottom': '15px'}),

            html.Div([
                html.Div([
                    html.Label("Column Diameter (mm):", className='input-label'),
                    dcc.Input(id='param-column-diameter', type='number', step=0.1,
                              value=config.get('column_diameter', 10.0),
                              className='form-input', style={'width': '100%'})
                ], style={'width': '48%', 'marginRight': '4%', 'display': 'inline-block'}),

                html.Div([
                    html.Label("Column Height (cm):", className='input-label'),
                    dcc.Input(id='param-column-height', type='number', step=0.1,
                              value=config.get('column_height', 100.0) / 10,  # Convert to cm
                              className='form-input', style={'width': '100%'})
                ], style={'width': '48%', 'display': 'inline-block'})
            ], style={'marginBottom': '15px'}),

            html.Div([
                html.Label("Column Volume (auto-calculated):", className='input-label'),
                html.Div(id='param-column-volume-display',
                         children=f"{config.get('column_volume', 7.854):.3f} mL",
                         style={'padding': '8px', 'background': '#f0f9ff', 'borderRadius': '4px',
                                'fontSize': '0.9rem', 'fontWeight': '600', 'color': '#0c4a6e'})
            ], style={'marginBottom': '20px'}),

            # Default Settings
            html.Div([
                html.Label("Default Flow Rate:", className='input-label'),
                html.Div([
                    dcc.Input(id='param-default-flow-rate', type='number', step=0.1,
                              value=config.get('default_flow_rate', 2.0),
                              className='form-input', 
                              style={'width': '55%', 'marginRight': '10px'}),
                    dcc.Dropdown(id='param-flow-rate-unit',
                                 options=[
                                     {'label': 'mL/min', 'value': 'mL/min'},
                                     {'label': 'cm/hr', 'value': 'cm/hr'},
                                     {'label': 'Residence Time (min)', 'value': 'residence_time'}
                                 ],
                                 value=config.get('default_flow_rate_unit', 'mL/min'),
                                 style={'width': '40%'})
                ], style={'display': 'flex', 'alignItems': 'center'})
            ], style={'marginBottom': '15px'}),

            html.Div([
                html.Label("Default Volume Unit:", className='input-label'),
                dcc.Dropdown(id='param-volume-unit',
                             options=[
                                 {'label': 'mL', 'value': 'mL'},
                                 {'label': 'Column Volumes (CV)', 'value': 'CV'}
                             ],
                             value=config.get('default_volume_unit', 'mL'),
                             style={'width': '100%'})
            ], style={'marginBottom': '20px'}),

            # Buffer Mapping
            html.Div([
                html.H5("Buffer Assignment", style={'marginBottom': '15px', 'color': '#374151'}),
                html.Div([
                    # First 5 valves
                    html.Div([
                        html.Div([
                            html.Label(f"A{i + 1}:", className='input-label',
                                       style={'fontSize': '0.8rem', 'marginBottom': '5px'}),
                            dcc.Input(id=f'param-buffer-a{i + 1}',
                                      value=config.get('buffer_map', {}).get(f'A{i + 1}', f'Buffer A{i + 1}'),
                                      className='form-input', style={'width': '100%', 'fontSize': '0.85rem'})
                        ], style={'marginBottom': '10px'}) for i in range(5)
                    ], style={'width': '48%', 'marginRight': '4%', 'display': 'inline-block'}),

                    # Last 4 valves
                    html.Div([
                        html.Div([
                            html.Label(f"A{i + 6}:", className='input-label',
                                       style={'fontSize': '0.8rem', 'marginBottom': '5px'}),
                            dcc.Input(id=f'param-buffer-a{i + 6}',
                                      value=config.get('buffer_map', {}).get(f'A{i + 6}', f'Buffer A{i + 6}'),
                                      className='form-input', style={'width': '100%', 'fontSize': '0.85rem'})
                        ], style={'marginBottom': '10px'}) for i in range(4)
                    ], style={'width': '48%', 'display': 'inline-block'})
                ], style={'display': 'block'})
            ], style={'marginBottom': '25px'}),

            html.Button([html.I(className="fas fa-save", style={'marginRight': '8px'}), "Save Configuration"],
                        id='save-step-params-btn', className='control-button success',
                        style={'width': '100%'})
        ])

    # Determine if this is an elution step for special options
    is_elution = 'elute' in step.get('name', '').lower() or step.get('type') == 'elute'

    return html.Div([
        html.H4(f"Edit Step {selected_index + 1}: {step['name']}", style={'marginBottom': '20px'}),

        html.Div([
            html.Label("Step Name:", className='input-label'),
            dcc.Input(id='param-name', value=step['name'], className='form-input', style={'width': '100%'})
        ], style={'marginBottom': '15px'}),

        # Buffer/Valve Selection with auto-populated buffer names
        html.Div([
            html.Label("Valve & Buffer:", className='input-label'),
            html.Div([
                dcc.Dropdown(
                    id='param-valve',
                    options=[{
                        'label': f'{valve} - {controller.method_config["buffer_map"][valve]}',
                        'value': valve
                    } for valve in [f'A{i}' for i in range(1, controller.inlet_valve_count + 1)]],
                    value=step.get('valve', 'A1'),
                    style={'width': '70%', 'marginRight': '10px'}
                ),
                dcc.Input(
                    id='param-buffer-override',
                    placeholder="Override buffer name...",
                    value=step.get('buffer_override', ''),
                    className='form-input',
                    style={'width': '28%'}
                )
            ], style={'display': 'flex', 'alignItems': 'center'})
        ], style={'marginBottom': '15px'}),

        # Volume with unit selection
        html.Div([
            html.Label("Volume:", className='input-label'),
            html.Div([
                dcc.Input(
                    id='param-volume',
                    type='number',
                    value=step.get('volume', 1000 if controller.method_config['default_volume_unit'] == 'mL' else 1.0),
                    step=0.1,
                    className='form-input',
                    style={'width': '60%', 'marginRight': '10px'}
                ),
                dcc.Dropdown(
                    id='param-volume-unit',
                    options=[
                        {'label': 'mL', 'value': 'mL'},
                        {'label': 'CV', 'value': 'CV'}
                    ],
                    value=step.get('volume_unit', controller.method_config['default_volume_unit']),
                    style={'width': '35%'}
                )
            ], style={'display': 'flex', 'alignItems': 'center'})
        ], style={'marginBottom': '15px'}),

        # Flow Rate with unit selection
        html.Div([
            html.Label("Flow Rate:", className='input-label'),
            html.Div([
                dcc.Input(
                    id='param-flow-rate',
                    type='number',
                    value=step.get('flow_rate', controller.method_config['default_flow_rate']),
                    step=0.1,
                    className='form-input',
                    style={'width': '45%', 'marginRight': '10px'}
                ),
                dcc.Dropdown(
                    id='param-flow-rate-unit',
                    options=[
                        {'label': 'mL/min', 'value': 'mL/min'},
                        {'label': 'cm/hr', 'value': 'cm/hr'},
                        {'label': 'Residence Time (min)', 'value': 'residence_time'}
                    ],
                    value=step.get('flow_rate_unit', controller.method_config['default_flow_rate_unit']),
                    style={'width': '40%'}
                )
            ], style={'display': 'flex', 'alignItems': 'center'})
        ], style={'marginBottom': '15px'}),

        # Pump Wash Option
        html.Div([
            dcc.Checklist(
                id='param-pump-wash',
                options=[{'label': ' Pump Wash Before Step', 'value': 'pump_wash'}],
                value=['pump_wash'] if step.get('pump_wash', False) else [],
                style={'marginBottom': '10px'}
            )
        ], style={'marginBottom': '15px'}),

        # Outlet Valve Selection
        html.Div([
            html.Label("Outlet Valve:", className='input-label'),
            dcc.Dropdown(
                id='param-outlet-valve',
                options=[
                    {'label': 'Waste', 'value': 'waste'},
                    {'label': 'Collect', 'value': 'collect'}
                ],
                value=step.get('outlet_valve', 'waste'),
                style={'width': '100%'}
            )
        ], style={'marginBottom': '15px' if not is_elution else '20px'}),

        # Special Elution Options (only show for elution steps)
        html.Div([
            html.H5("Elution Collection Settings", style={'color': '#2563eb', 'marginBottom': '15px'}),

            html.Div([
                html.Label("Collection Type:", className='input-label'),
                dcc.Dropdown(
                    id='param-collection-type',
                    options=[
                        {'label': 'Peak Collection (UV cutoffs)', 'value': 'peak'},
                        {'label': 'Fixed Volume Fractions', 'value': 'fixed_volume'}
                    ],
                    value=step.get('collection_type', 'peak'),
                    style={'width': '100%'}
                )
            ], style={'marginBottom': '15px'}),

            # Peak Collection Settings
            html.Div(id='peak-collection-settings', children=[
                html.Div([
                    html.Label("UV Start Cutoff (mAU):", className='input-label'),
                    dcc.Input(
                        id='param-uv-start',
                        type='number',
                        value=step.get('uv_start_cutoff', 10),
                        step=0.1,
                        className='form-input',
                        style={'width': '100%'}
                    )
                ], style={'width': '48%', 'marginRight': '4%', 'display': 'inline-block'}),

                html.Div([
                    html.Label("UV End Cutoff (mAU):", className='input-label'),
                    dcc.Input(
                        id='param-uv-end',
                        type='number',
                        value=step.get('uv_end_cutoff', 5),
                        step=0.1,
                        className='form-input',
                        style={'width': '100%'}
                    )
                ], style={'width': '48%', 'display': 'inline-block'})
            ], style={'marginBottom': '15px'}),

            # Fixed Volume Collection Settings
            html.Div(id='fixed-volume-settings', children=[
                html.Div([
                    html.Label("Fraction Volume:", className='input-label'),
                    html.Div([
                        dcc.Input(
                            id='param-fraction-volume',
                            type='number',
                            value=step.get('fraction_volume', 1.0),
                            step=0.1,
                            className='form-input',
                            style={'width': '60%', 'marginRight': '10px'}
                        ),
                        dcc.Dropdown(
                            id='param-fraction-unit',
                            options=[
                                {'label': 'mL', 'value': 'mL'},
                                {'label': 'CV', 'value': 'CV'}
                            ],
                            value=step.get('fraction_unit', 'mL'),
                            style={'width': '35%'}
                        )
                    ], style={'display': 'flex', 'alignItems': 'center'})
                ], style={'marginBottom': '15px'})
            ])
        ], style={'display': 'block' if is_elution else 'none', 'padding': '15px',
                  'background': '#f0f9ff', 'borderRadius': '8px', 'marginBottom': '20px'}),

        html.Button([html.I(className="fas fa-save", style={'marginRight': '8px'}), "Save Changes"],
                    id='save-step-params-btn', className='control-button success',
                    style={'width': '100%'})
    ])


@app.callback(
    Output('system-info-display', 'children'),
    [Input('inlet-valve-count-dropdown', 'value'),
     Input('column-type-input', 'value')]
)
def update_system_config(inlet_count, column_type):
    if inlet_count:
        controller.inlet_valve_count = inlet_count
    if column_type:
        controller.column_type = column_type

    # Update system info display
    return create_system_info_display()


# Manual Control P&ID Diagram Callback
@app.callback(
    Output('manual-pid-diagram', 'children'),
    [Input('inlet-valve-dropdown', 'value'),
     Input('outlet-valve-radio', 'value')]
)
def update_manual_pid(inlet_valve, outlet_valve):
    """Update the P&ID diagram in manual control based on selected valves"""

    # Create the P&ID diagram with highlighted selected valves
    pid_diagram = html.Div([
        html.Svg([
            # Valve Manifold (A1-A6)
            html.G([
                html.Text("Valve Manifold", x=20, y=15,
                          style={'fontSize': '10px', 'fontWeight': '600', 'fill': '#374151'}),
                # A1-A6 valve positions
                *[html.G([
                    html.Circle(cx=30 + i * 25, cy=40, r=8,
                                fill='#10b981' if f'A{i + 1}' == inlet_valve else '#e5e7eb',
                                stroke='#374151', strokeWidth=2,
                                style={'cursor': 'pointer'},
                                id=f'inlet-valve-{i + 1}'),
                    html.Text(f'A{i + 1}', x=30 + i * 25, y=45, textAnchor='middle',
                              style={'fontSize': '8px', 'fontWeight': '600', 'fill': '#374151'})
                ]) for i in range(6)]
            ]),

            # Horizontal pipe from valve manifold to pump
            html.Line(x1=180, y1=40, x2=250, y2=40, stroke='#374151', strokeWidth=3),

            # Pump
            html.G([
                html.Rect(x=250, y=25, width=40, height=30, fill='#3b82f6',
                          stroke='#1e40af', strokeWidth=2, rx=4),
                html.Text("PUMP", x=270, y=42, textAnchor='middle',
                          style={'fontSize': '8px', 'fontWeight': '600', 'fill': 'white'})
            ]),

            # Horizontal pipe from pump to column
            html.Line(x1=290, y1=40, x2=350, y2=40, stroke='#374151', strokeWidth=3),

            # Column
            html.G([
                html.Rect(x=350, y=20, width=20, height=40, fill='#f59e0b',
                          stroke='#d97706', strokeWidth=2, rx=4),
                html.Text("COL", x=360, y=42, textAnchor='middle',
                          style={'fontSize': '7px', 'fontWeight': '600', 'fill': 'white'})
            ]),

            # Horizontal pipe from column to 3-way valve
            html.Line(x1=370, y1=40, x2=430, y2=40, stroke='#374151', strokeWidth=3),

            # 3-Way Valve
            html.G([
                html.Circle(cx=450, cy=40, r=15, fill='#8b5cf6',
                            stroke='#7c3aed', strokeWidth=2),
                html.Text("3-WAY", x=450, y=42, textAnchor='middle',
                          style={'fontSize': '6px', 'fontWeight': '600', 'fill': 'white'})
            ]),

            # Outlet pipes
            # Waste outlet (up)
            html.Line(x1=450, y1=25, x2=450, y2=5, stroke='#374151', strokeWidth=3),
            html.G([
                html.Circle(cx=450, cy=5, r=8,
                            fill='#ef4444' if outlet_valve == 'Waste' else '#e5e7eb',
                            stroke='#374151', strokeWidth=2),
                html.Text("WASTE", x=450, y=-10, textAnchor='middle',
                          style={'fontSize': '8px', 'fontWeight': '600', 'fill': '#374151'})
            ]),

            # Collect outlet (right)
            html.Line(x1=465, y1=40, x2=485, y2=40, stroke='#374151', strokeWidth=3),
            html.G([
                html.Circle(cx=485, cy=40, r=8,
                            fill='#10b981' if outlet_valve == 'Collect' else '#e5e7eb',
                            stroke='#374151', strokeWidth=2),
                html.Text("COLLECT", x=485, y=55, textAnchor='middle',
                          style={'fontSize': '8px', 'fontWeight': '600', 'fill': '#374151'})
            ]),

            # Flow direction arrows when flow is active
            *([
                  # Arrow from selected inlet to pump
                  html.Polygon(points="240,35 245,40 240,45", fill='#10b981', opacity=0.8),
                  # Arrow from pump to column
                  html.Polygon(points="340,35 345,40 340,45", fill='#10b981', opacity=0.8),
                  # Arrow from column to 3-way
                  html.Polygon(points="420,35 425,40 420,45", fill='#10b981', opacity=0.8),
                  # Arrow to selected outlet
                  html.Polygon(points="475,35 480,40 475,45" if outlet_valve == 'Collect'
                  else "445,15 450,10 455,15", fill='#10b981', opacity=0.8),
              ] if controller.continuous_flow_active else [])

        ], viewBox="0 0 520 80", style={'width': '100%', 'height': '200px'})
    ])

    return pid_diagram


# Pump Speed Calculation Callback
@app.callback(
    Output('calculated-pump-speed', 'children'),
    [Input('continuous-flow-rate', 'value'),
     Input('syringe-size-dropdown', 'value')]
)
def calculate_pump_speed(flow_rate, syringe_size):
    """Calculate pump speed based on desired flow rate and syringe size"""
    if not flow_rate or not syringe_size:
        return "Pump Speed: 0 steps/sec"

    # Pump specifications: 6000 steps = full syringe volume
    steps_per_ml = 6000 / syringe_size

    # Convert flow rate from mL/min to mL/sec
    flow_rate_per_sec = flow_rate / 60

    # Calculate required steps per second
    pump_speed = steps_per_ml * flow_rate_per_sec

    # Store calculated speed in controller
    controller.calculated_pump_speed = int(pump_speed)

    return f"Pump Speed: {pump_speed:.1f} steps/sec ({steps_per_ml:.0f} steps/mL)"


# Flow Control Status Callback
@app.callback(
    [Output('flow-control-status', 'children'),
     Output('flow-control-status', 'style'),
     Output('start-flow-btn', 'disabled'),
     Output('stop-flow-btn', 'disabled')],
    [Input('start-flow-btn', 'n_clicks'),
     Input('stop-flow-btn', 'n_clicks')],
    [State('inlet-valve-dropdown', 'value'),
     State('outlet-valve-radio', 'value'),
     State('continuous-flow-rate', 'value')]
)
def control_continuous_flow(start_clicks, stop_clicks, inlet_valve, outlet_valve, flow_rate):
    """Control continuous flow operation"""
    ctx = dash.callback_context

    if not ctx.triggered:
        # Initial state
        return ("Flow Control: Stopped",
                {'marginTop': '15px', 'padding': '10px', 'backgroundColor': '#fef2f2',
                 'borderRadius': '8px', 'textAlign': 'center', 'fontWeight': '600', 'color': '#dc2626'},
                False, True)

    button_id = ctx.triggered[0]['prop_id'].split('.')[0]

    if button_id == 'start-flow-btn' and start_clicks:
        # Start continuous flow
        controller.continuous_flow_active = True
        controller.selected_inlet_valve = inlet_valve
        controller.selected_outlet_valve = outlet_valve
        controller.continuous_flow_rate = flow_rate

        # Set valve position and start continuous flow
        # First, move to selected inlet valve (assuming A1-A6 maps to ports 1-6)
        inlet_port = int(inlet_valve[1])  # Extract number from A1, A2, etc.
        controller.move_valve_to_port(inlet_port)

        # Start continuous aspirate/dispense cycle at specified flow rate
        controller.start_continuous_flow(flow_rate, "aspirate")

        return (f"Flow Control: ACTIVE - {inlet_valve} → {outlet_valve} @ {flow_rate} mL/min",
                {'marginTop': '15px', 'padding': '10px', 'backgroundColor': '#f0fdf4',
                 'borderRadius': '8px', 'textAlign': 'center', 'fontWeight': '600', 'color': '#166534'},
                True, False)

    elif button_id == 'stop-flow-btn' and stop_clicks:
        # Stop continuous flow
        controller.continuous_flow_active = False
        controller.stop_continuous_flow()

        return ("Flow Control: Stopped",
                {'marginTop': '15px', 'padding': '10px', 'backgroundColor': '#fef2f2',
                 'borderRadius': '8px', 'textAlign': 'center', 'fontWeight': '600', 'color': '#dc2626'},
                False, True)

    # Default state
    return ("Flow Control: Stopped",
            {'marginTop': '15px', 'padding': '10px', 'backgroundColor': '#fef2f2',
             'borderRadius': '8px', 'textAlign': 'center', 'fontWeight': '600', 'color': '#dc2626'},
            False, True)


# Clickable Valve Selection Callback
@app.callback(
    Output('inlet-valve-dropdown', 'value'),
    [Input(f'inlet-valve-{i}', 'n_clicks') for i in range(1, 10)],  # Support 9 valves
    prevent_initial_call=True
)
def update_inlet_valve_from_pid(*clicks):
    """Update inlet valve selection when clicking on P&ID valves"""
    ctx = dash.callback_context

    if not ctx.triggered:
        return dash.no_update

    # Extract valve number from button id
    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    valve_num = button_id.split('-')[-1]

    return f'A{valve_num}'


# Interactive P&ID Callbacks
@app.callback(
    Output('valve-input-btn', 'style'),
    Output('valve-output-btn', 'style'),
    Output('valve-bypass-btn', 'style'),
    [Input('pid-inlet-a1', 'n_clicks'),
     Input('pid-inlet-a2', 'n_clicks'),
     Input('pid-inlet-a3', 'n_clicks'),
     Input('pid-outlet-waste', 'n_clicks'),
     Input('pid-outlet-collect', 'n_clicks'),
     Input('valve-input-btn', 'n_clicks'),
     Input('valve-output-btn', 'n_clicks'),
     Input('valve-bypass-btn', 'n_clicks')],
    prevent_initial_call=True
)
def handle_interactive_valve_clicks(*clicks):
    ctx = callback_context
    base_style = {'margin': '3px', 'width': '100px'}
    active_style = {**base_style, 'background': '#10b981'}

    input_style = output_style = bypass_style = base_style

    if ctx.triggered:
        button_id = ctx.triggered[0]['prop_id'].split('.')[0]
        if button_id in ['pid-inlet-a1', 'pid-inlet-a2', 'pid-inlet-a3', 'valve-input-btn']:
            input_style = active_style
            controller.move_valve('Input')
        elif button_id in ['pid-outlet-collect', 'valve-output-btn']:
            output_style = active_style
            controller.move_valve('Output')
        elif button_id in ['pid-outlet-waste', 'valve-bypass-btn']:
            bypass_style = active_style
            controller.move_valve('Bypass')
    else:
        # Default to bypass active
        bypass_style = active_style

    return input_style, output_style, bypass_style


# Enhanced P&ID Control Callbacks with Visual Feedback
@app.callback(
    Output('notification-div', 'children', allow_duplicate=True),
    [Input('pid-inlet-a1', 'n_clicks'),
     Input('pid-inlet-a2', 'n_clicks'),
     Input('pid-inlet-a3', 'n_clicks'),
     Input('pid-inlet-a4', 'n_clicks'),
     Input('pid-inlet-a5', 'n_clicks'),
     Input('pid-inlet-a6', 'n_clicks'),
     Input('pid-inlet-a7', 'n_clicks'),
     Input('pid-inlet-a8', 'n_clicks'),
     Input('pid-inlet-a9', 'n_clicks'),
     Input('pid-pump-waste', 'n_clicks'),
     Input('pid-outlet-waste', 'n_clicks'),
     Input('pid-outlet-collect', 'n_clicks'),
     Input('pid-pump-main', 'n_clicks')],
    prevent_initial_call=True
)
def handle_pid_controls(*clicks):
    ctx = callback_context
    if not ctx.triggered:
        return dash.no_update

    button_id = ctx.triggered[0]['prop_id'].split('.')[0]

    # Handle inlet valve selections (works offline too)
    if button_id.startswith('pid-inlet-'):
        valve = button_id.split('-')[-1].upper()  # Extract A1, A2, etc.
        controller.selected_inlet_valve = valve
        if hasattr(controller, 'current_inlet_valve'):
            controller.current_inlet_valve = valve

        # Try to set valve position, but don't fail if offline
        try:
            if hasattr(controller, 'set_valve_position'):
                controller.set_valve_position('Input')
        except:
            pass  # Ignore errors when offline

        return dbc.Alert([
            html.I(className="fas fa-check-circle me-2"),
            f"Inlet valve switched to {valve} {'(OFFLINE MODE)' if not controller.is_connected else ''}"
        ], color="success", duration=2000, dismissable=True, className="alert-notification")

    # Handle pump waste valve
    elif button_id == 'pid-pump-waste':
        controller.selected_outlet_valve = 'Waste'
        try:
            if hasattr(controller, 'set_valve_position'):
                controller.set_valve_position('Waste')
        except:
            pass

        return dbc.Alert([
            html.I(className="fas fa-trash me-2"),
            f"Direct pump waste activated {'(OFFLINE MODE)' if not controller.is_connected else ''}"
        ], color="warning", duration=2000, dismissable=True, className="alert-notification")

    # Handle outlet waste valve
    elif button_id == 'pid-outlet-waste':
        controller.selected_outlet_valve = 'Waste'
        try:
            if hasattr(controller, 'set_valve_position'):
                controller.set_valve_position('Bypass')
        except:
            pass

        return dbc.Alert([
            html.I(className="fas fa-exchange-alt me-2"),
            f"Flow redirected to WASTE line {'(OFFLINE MODE)' if not controller.is_connected else ''}"
        ], color="warning", duration=2000, dismissable=True, className="alert-notification")

    # Handle outlet collect valve
    elif button_id == 'pid-outlet-collect':
        controller.selected_outlet_valve = 'Collect'
        try:
            if hasattr(controller, 'set_valve_position'):
                controller.set_valve_position('Output')
        except:
            pass

        return dbc.Alert([
            html.I(className="fas fa-flask me-2"),
            f"Flow redirected to COLLECTION line {'(OFFLINE MODE)' if not controller.is_connected else ''}"
        ], color="info", duration=2000, dismissable=True, className="alert-notification")

    # Handle pump control (works offline too)
    elif button_id == 'pid-pump-main':
        if controller.is_connected:
            if controller.operation_state == 'idle':
                try:
                    controller.prime_system(volume=100)  # Small prime
                    return dbc.Alert([
                        html.I(className="fas fa-play me-2"),
                        "Pump priming initiated"
                    ], color="primary", duration=2000, dismissable=True, className="alert-notification")
                except:
                    return dbc.Alert([
                        html.I(className="fas fa-exclamation-triangle me-2"),
                        "Failed to start pump operation"
                    ], color="danger", duration=2000, dismissable=True, className="alert-notification")
            else:
                try:
                    controller.stop_operation()
                    return dbc.Alert([
                        html.I(className="fas fa-stop me-2"),
                        "Pump operation stopped"
                    ], color="secondary", duration=2000, dismissable=True, className="alert-notification")
                except:
                    return dbc.Alert([
                        html.I(className="fas fa-exclamation-triangle me-2"),
                        "Failed to stop pump operation"
                    ], color="danger", duration=2000, dismissable=True, className="alert-notification")
        else:
            # Offline mode - just show notification
            return dbc.Alert([
                html.I(className="fas fa-info-circle me-2"),
                "Pump clicked (OFFLINE MODE) - Connect pump to control"
            ], color="info", duration=3000, dismissable=True, className="alert-notification")

    return dash.no_update


# Enhanced tooltips and hover effects for P&ID components
@app.callback(
    Output('pid-status-tooltip', 'children', allow_duplicate=True),
    [Input('realtime-interval', 'n_intervals')],
    prevent_initial_call=True
)
def update_pid_tooltips(n):
    """Update dynamic tooltips for P&ID components"""
    if controller.is_connected:
        flow_status = "Active" if abs(controller.current_flow_rate) > 0.1 else "Idle"
        pressure_psi = controller.current_pressure
        position = controller.current_position

        tooltip_data = {
            'pump_status': f"XLP 6000 | Status: {controller.operation_state.title()} | Flow: {controller.current_flow_rate:.2f} mL/min | Pressure: {pressure_psi:.1f} psi | Position: {position}",
            'inlet_status': f"Current Inlet: {controller.selected_inlet_valve} | Path: {controller.valve_position}",
            'outlet_status': f"Current Outlet: {controller.selected_outlet_valve} | Collection Mode: {'Collect' if controller.valve_position == 'Output' else 'Waste'}"
        }

        return tooltip_data
    else:
        return {
            'pump_status': "XLP 6000 - OFFLINE | Click to reconnect",
            'inlet_status': "Inlet valves - OFFLINE",
            'outlet_status': "Outlet valve - OFFLINE"
        }


# Method Configuration Callbacks
@app.callback(
    [Output('config-column-volume-display', 'children'),
     Output('notification-div', 'children', allow_duplicate=True)],
    [Input('save-method-config-btn', 'n_clicks')],
    [State('config-column-resin', 'value'),
     State('config-column-diameter', 'value'),
     State('config-column-height', 'value'),
     State('config-default-flow-rate', 'value'),
     State('config-flow-rate-unit', 'value'),
     State('config-volume-unit', 'value')] +
    [State(f'config-buffer-a{i}', 'value') for i in range(1, 10)],
    prevent_initial_call=True
)
def update_method_configuration(save_clicks, resin, diameter, height, flow_rate, flow_unit, vol_unit, *buffer_values):
    """Update method configuration and auto-calculate column volume"""
    if not save_clicks:
        return dash.no_update, dash.no_update

    # Update controller configuration
    controller.method_config['column_resin'] = resin or 'Protein A'
    controller.method_config['column_diameter'] = diameter or 10.0
    controller.method_config['column_height'] = (height or 10.0) * 10  # Convert cm to mm
    controller.method_config['default_flow_rate'] = flow_rate or 2.0
    controller.method_config['default_flow_rate_unit'] = flow_unit or 'mL/min'
    controller.method_config['default_volume_unit'] = vol_unit or 'mL'

    # Update buffer mapping
    for i, buffer_name in enumerate(buffer_values):
        valve_key = f'A{i + 1}'
        controller.method_config['buffer_map'][valve_key] = buffer_name or f'Buffer {i + 1}'

    # Recalculate column volume
    column_volume = controller.calculate_column_volume()
    volume_display = f"{column_volume:.3f} mL"

    # Success notification
    notification = dbc.Alert([
        html.I(className="fas fa-check-circle me-2"),
        f"Method configuration updated! Column Volume: {column_volume:.3f} mL"
    ], color="success", duration=3000, dismissable=True, className="alert-notification")

    return volume_display, notification


# Auto-calculate column volume in step parameters
@app.callback(
    Output('param-column-volume-display', 'children'),
    [Input('param-column-diameter', 'value'),
     Input('param-column-height', 'value')],
    prevent_initial_call=True
)
def auto_calculate_param_column_volume(diameter, height):
    """Auto-calculate column volume in step parameters when diameter or height changes"""
    if diameter and height:
        # Calculate volume: π * (d/2)² * h
        # diameter in mm, height in cm (convert to mm)
        radius_mm = diameter / 2
        height_mm = height * 10
        volume_mm3 = 3.14159 * (radius_mm ** 2) * height_mm
        volume_ml = volume_mm3 / 1000
        return f"{volume_ml:.3f} mL"
    return "0.000 mL"


# Auto-calculate column volume when diameter or height changes
@app.callback(
    Output('config-column-volume-display', 'children', allow_duplicate=True),
    [Input('config-column-diameter', 'value'),
     Input('config-column-height', 'value')],
    prevent_initial_call=True
)
def auto_calculate_column_volume(diameter, height):
    """Auto-calculate column volume when diameter or height changes"""
    if diameter and height:
        # Temporarily update for calculation
        controller.method_config['column_diameter'] = diameter
        controller.method_config['column_height'] = height * 10  # Convert cm to mm
        volume = controller.calculate_column_volume()
        return f"{volume:.3f} mL"
    return dash.no_update


# Manual Control Tab Callbacks

# Calculate pump speed for continuous flow
@app.callback(
    Output('manual-pump-speed', 'children'),
    [Input('manual-flow-rate', 'value')]
)
def update_manual_pump_speed(flow_rate):
    """Calculate and display pump speed based on flow rate"""
    if flow_rate and controller.syringe_size:
        # Convert flow rate from mL/min to mL/sec
        flow_rate_per_sec = flow_rate / 60
        # Calculate steps per mL (6000 steps = full syringe)
        steps_per_ml = 6000 / controller.syringe_size
        # Calculate pump speed in steps/sec
        pump_speed = int(steps_per_ml * flow_rate_per_sec)
        return f"{pump_speed} steps/sec"
    return "0 steps/sec"


# Handle continuous flow control
@app.callback(
    [Output('manual-flow-status', 'children'),
     Output('manual-flow-status', 'style')],
    [Input('manual-start-flow', 'n_clicks'),
     Input('manual-stop-flow', 'n_clicks'),
     Input('manual-pause-flow', 'n_clicks')],
    [State('manual-flow-rate', 'value'),
     State('manual-flow-direction', 'value')]
)
def handle_manual_continuous_flow(start_clicks, stop_clicks, pause_clicks, flow_rate, direction):
    """Handle continuous flow operations"""
    ctx = dash.callback_context
    
    if not ctx.triggered:
        return "Flow Status: Idle", {
            'padding': '12px',
            'backgroundColor': '#f1f5f9',
            'borderRadius': '8px',
            'textAlign': 'center',
            'fontWeight': '600'
        }
    
    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    
    if button_id == 'manual-start-flow' and start_clicks and flow_rate:
        # Start continuous flow
        controller.start_continuous_flow(flow_rate, direction)
        status = f"Flow Status: {direction.capitalize()}ing at {flow_rate} mL/min"
        style = {
            'padding': '12px',
            'backgroundColor': '#dcfce7',
            'borderRadius': '8px',
            'textAlign': 'center',
            'fontWeight': '600',
            'color': '#166534'
        }
        return status, style
    
    elif button_id == 'manual-stop-flow' and stop_clicks:
        # Stop flow
        controller.stop_continuous_flow()
        return "Flow Status: Stopped", {
            'padding': '12px',
            'backgroundColor': '#fee2e2',
            'borderRadius': '8px',
            'textAlign': 'center',
            'fontWeight': '600',
            'color': '#991b1b'
        }
    
    elif button_id == 'manual-pause-flow' and pause_clicks:
        # Pause flow
        controller.pause_operation()
        return "Flow Status: Paused", {
            'padding': '12px',
            'backgroundColor': '#fef3c7',
            'borderRadius': '8px',
            'textAlign': 'center',
            'fontWeight': '600',
            'color': '#92400e'
        }
    
    return dash.no_update, dash.no_update


# Handle volume-based operations
@app.callback(
    Output('manual-volume-status', 'children'),
    [Input('manual-aspirate', 'n_clicks'),
     Input('manual-dispense', 'n_clicks')],
    [State('manual-volume', 'value'),
     State('manual-speed', 'value')]
)
def handle_manual_volume_control(aspirate_clicks, dispense_clicks, volume, speed):
    """Handle volume-based aspirate/dispense operations"""
    ctx = dash.callback_context
    
    if not ctx.triggered:
        return ""
    
    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    
    if button_id == 'manual-aspirate' and aspirate_clicks and volume:
        controller.aspirate(volume, speed)
        return f"Aspirated {volume} μL"
    
    elif button_id == 'manual-dispense' and dispense_clicks and volume:
        controller.dispense(volume, speed)
        return f"Dispensed {volume} μL"
    
    return ""


# Handle inlet valve selection
@app.callback(
    Output('manual-inlet-status', 'children'),
    [Input({'type': 'manual-inlet-valve', 'index': dash.dependencies.ALL}, 'n_clicks')]
)
def handle_manual_inlet_valve(clicks):
    """Handle inlet valve selection"""
    ctx = dash.callback_context
    
    if not ctx.triggered or not any(clicks):
        return ""
    
    # Get the index of the clicked valve
    triggered_id = ctx.triggered[0]['prop_id']
    import json
    valve_index = json.loads(triggered_id.split('.')[0])['index']
    valve_name = f"A{valve_index}"
    
    # Move to selected inlet valve
    controller.selected_inlet_valve = valve_name
    controller.move_valve_to_port(valve_index)
    
    return f"Inlet valve set to {valve_name}"


# Handle outlet valve selection
@app.callback(
    Output('manual-outlet-status', 'children'),
    [Input('manual-outlet-waste', 'n_clicks'),
     Input('manual-outlet-collect', 'n_clicks')]
)
def handle_manual_outlet_valve(waste_clicks, collect_clicks):
    """Handle outlet valve selection"""
    ctx = dash.callback_context
    
    if not ctx.triggered:
        return ""
    
    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    
    if button_id == 'manual-outlet-waste' and waste_clicks:
        controller.selected_outlet_valve = 'Waste'
        controller.move_valve('Bypass')
        return "Outlet set to Waste"
    
    elif button_id == 'manual-outlet-collect' and collect_clicks:
        controller.selected_outlet_valve = 'Collect'
        controller.move_valve('Output')
        return "Outlet set to Collect"
    
    return ""


# Handle system operations
@app.callback(
    Output('manual-system-status', 'children'),
    [Input('manual-prime', 'n_clicks'),
     Input('manual-wash', 'n_clicks'),
     Input('manual-home', 'n_clicks')]
)
def handle_manual_system_operations(prime_clicks, wash_clicks, home_clicks):
    """Handle system operations like prime, wash, and home"""
    ctx = dash.callback_context
    
    if not ctx.triggered:
        return ""
    
    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    
    if button_id == 'manual-prime' and prime_clicks:
        controller.prime_system()
        return "System primed"
    
    elif button_id == 'manual-wash' and wash_clicks:
        controller.wash_valve()
        return "Valve washed"
    
    elif button_id == 'manual-home' and home_clicks:
        controller.home_syringe()
        return "Syringe homed"
    
    return ""


# Update status display
@app.callback(
    [Output('manual-current-position', 'children'),
     Output('manual-valve-position', 'children')],
    Input('manual-update-interval', 'n_intervals')
)
def update_manual_status(n):
    """Update real-time status display"""
    return (f"{controller.current_position} steps",
            controller.valve_position)


if __name__ == '__main__':
    app.run(debug=False, host='127.0.0.1', port=8050)
