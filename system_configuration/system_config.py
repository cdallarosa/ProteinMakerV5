from system_configuration.pump.pump_class import Pump, PumpConfig
from system_configuration.process import ChromatographyProcess, ProcessLibrary
import logging
import time
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class System:
    # System configuration - MODIFY THIS SECTION TO CONFIGURE YOUR SYSTEM
    PUMP_COUNT = 1  # Number of pumps in the system
    PUMP_PORT = "COM12"  # Serial port for pump communication
    DEFAULT_SYRINGE_SIZE_ML = 5.0  # Default syringe size in mL

    def __init__(self, pump_count: Optional[int] = None, pump_port: Optional[str] = None, syringe_size_ml: Optional[float] = None):
        # Allow override of configuration
        self.pump_count = pump_count if pump_count is not None else self.PUMP_COUNT
        self.pump_port = pump_port if pump_port is not None else self.PUMP_PORT
        self.syringe_size_ml = syringe_size_ml if syringe_size_ml is not None else self.DEFAULT_SYRINGE_SIZE_ML
        
        # Create pumps dynamically based on pump count
        self.pumps = {}
        for i in range(1, self.pump_count + 1):
            pump_config = PumpConfig(
                port=self.pump_port,
                address=i,
                syringe_size_ml=self.syringe_size_ml
            )
            self.pumps[f"pump{i}"] = Pump(pump_config)
            # Also set as attributes for backward compatibility
            setattr(self, f"pump{i}", self.pumps[f"pump{i}"])
        
        # System state
        self.is_connected = False
        self.is_initialized = False
    
    def connect_all(self) -> bool:
        """Connect to all pumps"""
        logger.info(f"Connecting to {self.pump_count} pumps...")
        
        all_success = True
        for pump_name, pump in self.pumps.items():
            success = pump.connect(verify_device=True)
            if not success:
                logger.error(f"Failed to connect {pump_name}")
                all_success = False
            else:
                logger.info(f"{pump_name} connected successfully")
        
        self.is_connected = all_success
        
        if self.is_connected:
            logger.info("All pumps connected successfully")
        else:
            logger.error("Failed to connect one or more pumps")
            
        return self.is_connected
    
    def initialize_all(self) -> bool:
        """Initialize all pumps"""
        if not self.is_connected:
            logger.error("Pumps not connected")
            return False
            
        logger.info(f"Initializing {self.pump_count} pumps...")
        
        all_success = True
        for pump_name, pump in self.pumps.items():
            success = pump.initialize(wait=True)
            if not success:
                logger.error(f"Failed to initialize {pump_name}")
                all_success = False
            else:
                logger.info(f"{pump_name} initialized successfully")
        
        self.is_initialized = all_success
        
        if self.is_initialized:
            logger.info("All pumps initialized successfully")
        else:
            logger.error("Failed to initialize one or more pumps")
            
        return self.is_initialized
    
    def process_step(self, pump_name: str, inlet: int, outlet: int, 
                    volume_ml: float, flow_rate_ml_min: float = 1.0, 
                    prime: bool = False, wait: bool = False) -> bool:
        """
        Execute a single process step with specified parameters
        
        Args:
            pump_name: Which pump to use ("pump1", "pump2", "pump3")
            inlet: Inlet valve position (1-10)
            outlet: Outlet valve position (11=bypass, 12=output)
            volume_ml: Volume to pump in mL
            flow_rate_ml_min: Flow rate in mL/min
            prime: If True, prime the lines first
            wait: Wait for completion (default False for parallel operation)
            
        Returns:
            bool: True if successful
        """
        # Get the specified pump
        pump = self.pumps.get(pump_name)
        if not pump:
            logger.error(f"Pump '{pump_name}' not found")
            return False
            
        if not pump.is_connected():
            logger.error(f"Pump '{pump_name}' not connected")
            return False
        
        logger.info(f"Process step: {pump_name} - {volume_ml}mL from inlet {inlet} to outlet {outlet} @ {flow_rate_ml_min}mL/min")
        
        try:
            # Prime if requested - now uses the pump's prime() method
            if prime:
                logger.info(f"Priming {pump_name}...")
                success = pump.prime(
                    inlet=inlet,
                    outlet=outlet,
                    volume_ml=0.5,  # Default prime volume
                    flow_rate_ml_min=2.0,  # Fast priming
                    wait=True
                )

                if not success:
                    logger.error(f"Priming failed for {pump_name}")
                    return False

            # Execute the main operation - uses continuous_pump
            volume_ul = volume_ml * 1000

            success = pump.continuous_pump(
                volume_ul=volume_ul,
                flowrate_ul_min=flow_rate_ml_min * 1000,
                inlet=inlet,
                outlet=outlet,
                wait=wait  # Default False for parallel operation
            )

            if success:
                logger.info(f"Process step started for {pump_name}")
            else:
                logger.error(f"Process step failed for {pump_name}")

            return success

        except Exception as e:
            logger.error(f"Error during process step: {e}")
            return False
    
    def run_parallel_chromatography(self, pump_configs: dict) -> bool:
        """
        Run chromatography processes on multiple pumps in parallel
        
        Args:
            pump_configs: Dict with pump_name as key and config dict as value
                         Each config should have: inlet, outlet, volume_ml, flow_rate_ml_min, prime
                         
        Example:
            configs = {
                "pump1": {"inlet": 1, "outlet": 12, "volume_ml": 5.0, "flow_rate_ml_min": 1.0, "prime": True},
                "pump2": {"inlet": 2, "outlet": 12, "volume_ml": 3.0, "flow_rate_ml_min": 1.5, "prime": False},
                "pump3": {"inlet": 3, "outlet": 12, "volume_ml": 4.0, "flow_rate_ml_min": 2.0, "prime": True}
            }
            
        Returns:
            bool: True if all processes started successfully
        """
        if not self.is_initialized:
            logger.error("System not initialized")
            return False
        
        logger.info(f"Starting parallel chromatography on {len(pump_configs)} pumps")
        
        # Start all processes without waiting
        all_started = True
        for pump_name, config in pump_configs.items():
            success = self.process_step(
                pump_name=pump_name,
                inlet=config["inlet"],
                outlet=config["outlet"], 
                volume_ml=config["volume_ml"],
                flow_rate_ml_min=config["flow_rate_ml_min"],
                prime=config.get("prime", False),
                wait=False  # Don't wait - run in parallel
            )
            
            if not success:
                logger.error(f"Failed to start process on {pump_name}")
                all_started = False
        
        if all_started:
            logger.info("All parallel chromatography processes started successfully")
        else:
            logger.warning("Some processes failed to start")
            
        return all_started
    
    def wait_for_all_pumps(self, timeout: float = 600) -> bool:
        """
        Wait for all pumps to complete their current operations
        
        Args:
            timeout: Maximum time to wait in seconds (default 10 minutes)
            
        Returns:
            bool: True if all pumps completed successfully
        """
        import time
        start_time = time.time()
        
        logger.info("Waiting for all pumps to complete...")
        
        while (time.time() - start_time) < timeout:
            all_ready = True
            
            for pump_name, pump in self.pumps.items():
                if pump.is_connected():
                    if not pump.is_ready():
                        all_ready = False
                        break
            
            if all_ready:
                elapsed = time.time() - start_time
                logger.info(f"All pumps completed after {elapsed:.1f} seconds")
                return True
                
            time.sleep(1)  # Check every second
        
        logger.warning(f"Timeout waiting for pumps to complete ({timeout}s)")
        return False
    
    def stop_all_pumps(self):
        """Emergency stop all pumps"""
        logger.warning("EMERGENCY STOP - Stopping all pumps")
        
        for pump_name, pump in self.pumps.items():
            if pump.is_connected():
                pump.stop()
                logger.info(f"{pump_name} stopped")
    
    def get_parallel_status(self) -> dict:
        """Get status of all pumps for parallel monitoring"""
        status = {
            'system_ready': True,
            'pumps_running': 0,
            'pumps_ready': 0,
            'pumps': {}
        }
        
        for pump_name, pump in self.pumps.items():
            if pump.is_connected():
                pump_status = pump.get_status()
                is_ready = pump_status.get('is_idle', False)
                is_running = not is_ready and pump_status.get('state') != 'error'
                
                status['pumps'][pump_name] = {
                    'state': pump_status.get('state', 'unknown'),
                    'ready': is_ready,
                    'running': is_running,
                    'position': pump_status.get('position', 0)
                }
                
                if is_running:
                    status['pumps_running'] += 1
                elif is_ready:
                    status['pumps_ready'] += 1
                else:
                    status['system_ready'] = False
            else:
                status['pumps'][pump_name] = {'state': 'disconnected', 'ready': False, 'running': False}
                status['system_ready'] = False
        
        return status
    
    def get_system_status(self) -> dict:
        """Get status of all system components"""
        status = {
            'connected': self.is_connected,
            'initialized': self.is_initialized,
            'pumps': {}
        }
        
        # Get pump statuses
        for pump_name, pump in self.pumps.items():
            if pump.is_connected():
                status['pumps'][pump_name] = pump.get_status()
            else:
                status['pumps'][pump_name] = {'state': 'disconnected'}
        
        return status
    
    # ========================================================================
    # PROCESS EXECUTION METHODS
    # ========================================================================
    
    def run_process_on_pumps(self, process: ChromatographyProcess, pump_names: List[str]) -> bool:
        """
        Run a chromatography process on selected pumps
        
        Args:
            process: ChromatographyProcess to execute
            pump_names: List of pump names to run the process on (e.g., ["pump1", "pump2"])
            
        Returns:
            bool: True if all processes started successfully
        """
        if not self.is_initialized:
            logger.error("System not initialized")
            return False
        
        # Validate pump names
        available_pumps = list(self.pumps.keys())
        invalid_pumps = [name for name in pump_names if name not in available_pumps]
        if invalid_pumps:
            logger.error(f"Invalid pump names: {invalid_pumps}")
            return False
        
        logger.info(f"Running process '{process.config.name}' on pumps: {pump_names}")
        logger.info(f"Process details: {process.get_process_summary()}")
        
        # Start process on each selected pump
        all_started = True
        for pump_name in pump_names:
            logger.info(f"Starting process on {pump_name}...")
            
            success = self._execute_process_on_pump(process, pump_name)
            if not success:
                logger.error(f"Failed to start process on {pump_name}")
                all_started = False
        
        if all_started:
            logger.info(f"Process '{process.config.name}' started on all selected pumps")
        else:
            logger.warning("Some processes failed to start")
            
        return all_started
    
    def _execute_process_on_pump(self, process: ChromatographyProcess, pump_name: str) -> bool:
        """
        Execute a complete process on a single pump
        
        Args:
            process: ChromatographyProcess to execute
            pump_name: Name of pump to run process on
            
        Returns:
            bool: True if process started successfully
        """
        pump = self.pumps.get(pump_name)
        if not pump or not pump.is_connected():
            logger.error(f"Pump {pump_name} not available")
            return False
        
        try:
            # Execute each step in the process
            for i, step in enumerate(process.config.steps):
                logger.info(f"{pump_name} - Step {i+1}/{len(process.config.steps)}: {step.name}")
                
                # Execute the step
                success = self.process_step(
                    pump_name=pump_name,
                    inlet=step.inlet,
                    outlet=step.outlet,
                    volume_ml=step.volume_ml,
                    flow_rate_ml_min=step.flow_rate_ml_min,
                    prime=step.prime,
                    wait=True  # Wait for each step to complete
                )
                
                if not success:
                    logger.error(f"{pump_name} - Step {i+1} failed: {step.name}")
                    return False
                
                # Add delay if specified
                if step.delay_after_sec > 0:
                    logger.info(f"{pump_name} - Waiting {step.delay_after_sec}s after {step.name}")
                    time.sleep(step.delay_after_sec)
            
            logger.info(f"{pump_name} - Process '{process.config.name}' completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error executing process on {pump_name}: {e}")
            return False
    
    def run_all_pumps(self, process: ChromatographyProcess) -> bool:
        """
        Run a process on all pumps
        
        Args:
            process: ChromatographyProcess to execute
            
        Returns:
            bool: True if process started on all pumps
        """
        return self.run_process_on_pumps(process, list(self.pumps.keys()))
    
    def run_selected_pumps(self, process: ChromatographyProcess, pump_selection: str) -> bool:
        """
        Run a process on a predefined selection of pumps
        
        Args:
            process: ChromatographyProcess to execute
            pump_selection: Selection mode ("all", "half", "first", "last", "middle")
            
        Returns:
            bool: True if process started successfully
        """
        pump_names = list(self.pumps.keys())
        selections = {
            "all": pump_names,
            "half": pump_names[:len(pump_names)//2 + len(pump_names)%2],
            "first": [pump_names[0]] if pump_names else [],
            "last": [pump_names[-1]] if pump_names else [],
            "middle": [pump_names[len(pump_names)//2]] if pump_names else [],
            "first_and_last": [pump_names[0], pump_names[-1]] if len(pump_names) >= 2 else pump_names
        }
        
        if pump_selection not in selections:
            logger.error(f"Invalid pump selection: {pump_selection}")
            logger.info(f"Available selections: {list(selections.keys())}")
            return False
        
        pump_names = selections[pump_selection]
        logger.info(f"Running process on {pump_selection} pumps: {pump_names}")
        
        return self.run_process_on_pumps(process, pump_names)
    
    def get_available_processes(self) -> List[str]:
        """Get list of available pre-defined processes"""
        return ProcessLibrary.list_available_processes()
    
    def load_process(self, process_name: str) -> Optional[ChromatographyProcess]:
        """Load a pre-defined process by name"""
        return ProcessLibrary.get_process(process_name)
    
    def get_process_summary(self, process_name: str) -> Dict:
        """Get summary of a process without loading it"""
        process = self.load_process(process_name)
        if process:
            return process.get_process_summary()
        return {}
    
    def disconnect_all(self):
        """Disconnect all pumps"""
        logger.info(f"Disconnecting {self.pump_count} pumps...")
        for pump_name, pump in self.pumps.items():
            pump.disconnect()
            logger.info(f"{pump_name} disconnected")
        self.is_connected = False
        self.is_initialized = False
    
    def get_pump_names(self) -> List[str]:
        """Get list of all pump names in the system"""
        return list(self.pumps.keys())
    
    def get_pump(self, pump_name: str) -> Optional[Pump]:
        """Get a specific pump by name"""
        return self.pumps.get(pump_name)


