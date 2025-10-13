"""
Mock Fraction Collector Class
Simulates a 6-plate fraction collector with 6 sections per plate (36 total positions)
Similar to AKTA FRAC-950 style collectors
"""

import time
import logging
from enum import Enum
from dataclasses import dataclass
from typing import Optional, Tuple, List

logger = logging.getLogger(__name__)


class CollectorStatus(Enum):
    IDLE = "idle"
    MOVING = "moving"
    COLLECTING = "collecting"
    ERROR = "error"
    HOMING = "homing"
    PAUSED = "paused"


class CollectionMode(Enum):
    TIME = "time"           # Collect for X seconds per fraction
    VOLUME = "volume"       # Collect X mL per fraction
    PEAK = "peak"          # Collect based on UV/detector signal
    MANUAL = "manual"      # Manual advance only


@dataclass
class PlatePosition:
    """Represents a position on the fraction collector"""
    plate: int      # 1-6
    section: int    # 1-6
    
    def to_absolute_position(self) -> int:
        """Convert plate/section to absolute position (1-36)"""
        return (self.plate - 1) * 6 + self.section
    
    @classmethod
    def from_absolute_position(cls, position: int) -> 'PlatePosition':
        """Create PlatePosition from absolute position (1-36)"""
        plate = ((position - 1) // 6) + 1
        section = ((position - 1) % 6) + 1
        return cls(plate=plate, section=section)
    
    def __str__(self):
        return f"Plate {self.plate}, Section {self.section}"


class MockFractionCollector:
    """
    Mock implementation of a fraction collector
    Simulates hardware without actual serial communication
    """
    
    def __init__(self):
        # Configuration
        self.num_plates = 6
        self.sections_per_plate = 6
        self.total_positions = self.num_plates * self.sections_per_plate
        
        # Current state
        self.status = CollectorStatus.IDLE
        self.current_position = PlatePosition(1, 1)
        self.home_position = PlatePosition(1, 1)
        self.is_connected = False
        self.is_initialized = False
        
        # Collection settings
        self.collection_mode = CollectionMode.MANUAL
        self.collection_time_sec = 60  # For TIME mode
        self.collection_volume_ml = 10  # For VOLUME mode
        self.current_fraction_start_time = None
        self.current_fraction_volume = 0
        
        # Movement simulation
        self.movement_time_sec = 2.0  # Time to move between positions
        self.is_moving = False
        self.move_start_time = None
        self.target_position = None
        
        # Collection tracking
        self.collected_fractions = []  # List of (position, volume, time) tuples
        self.total_volume_collected = 0
        
        # Plate layout (for visualization)
        self.plate_layout = self._generate_plate_layout()
        
    def _generate_plate_layout(self) -> dict:
        """Generate a mapping of plate positions for visualization"""
        layout = {}
        for plate in range(1, self.num_plates + 1):
            layout[plate] = {}
            for section in range(1, self.sections_per_plate + 1):
                position = PlatePosition(plate, section)
                layout[plate][section] = {
                    'position': position,
                    'absolute': position.to_absolute_position(),
                    'volume_collected': 0,
                    'fractions': []
                }
        return layout
    
    def connect(self) -> bool:
        """Simulate connection to fraction collector"""
        logger.info("Mock Fraction Collector: Simulating connection...")
        time.sleep(0.5)  # Simulate connection delay
        self.is_connected = True
        self.status = CollectorStatus.IDLE
        logger.info("Mock Fraction Collector: Connected successfully")
        return True
    
    def disconnect(self):
        """Simulate disconnection"""
        self.is_connected = False
        self.status = CollectorStatus.IDLE
        logger.info("Mock Fraction Collector: Disconnected")
    
    def initialize(self) -> bool:
        """Initialize collector and home the arm"""
        if not self.is_connected:
            logger.error("Cannot initialize - not connected")
            return False
        
        logger.info("Mock Fraction Collector: Initializing...")
        self.status = CollectorStatus.HOMING
        
        # Simulate homing sequence
        time.sleep(3)  # Simulate homing time
        
        self.current_position = self.home_position
        self.is_initialized = True
        self.status = CollectorStatus.IDLE
        logger.info(f"Mock Fraction Collector: Initialized at {self.current_position}")
        return True
    
    def move_to_position(self, plate: int, section: int, wait: bool = True) -> bool:
        """
        Move to specified plate and section
        
        Args:
            plate: Plate number (1-6)
            section: Section number (1-6)
            wait: If True, wait for movement to complete
            
        Returns:
            bool: True if movement started successfully
        """
        if not self.is_initialized:
            logger.error("Cannot move - not initialized")
            return False
        
        if not (1 <= plate <= self.num_plates):
            logger.error(f"Invalid plate number: {plate}")
            return False
            
        if not (1 <= section <= self.sections_per_plate):
            logger.error(f"Invalid section number: {section}")
            return False
        
        target = PlatePosition(plate, section)
        
        if self.current_position.plate == plate and self.current_position.section == section:
            logger.info(f"Already at position {target}")
            return True
        
        # Start movement
        self.status = CollectorStatus.MOVING
        self.is_moving = True
        self.target_position = target
        self.move_start_time = time.time()
        
        logger.info(f"Moving from {self.current_position} to {target}")
        
        if wait:
            # Wait for movement to complete
            time.sleep(self.movement_time_sec)
            self._complete_movement()
        
        return True
    
    def _complete_movement(self):
        """Complete the current movement"""
        if self.target_position:
            self.current_position = self.target_position
            self.target_position = None
            self.is_moving = False
            self.status = CollectorStatus.IDLE
            logger.info(f"Movement complete. Now at {self.current_position}")
    
    def advance_position(self, wait: bool = True) -> bool:
        """
        Advance to next collection position
        
        Args:
            wait: If True, wait for movement to complete
            
        Returns:
            bool: True if successful
        """
        current_abs = self.current_position.to_absolute_position()
        
        if current_abs >= self.total_positions:
            logger.warning("Already at last position, cannot advance")
            return False
        
        next_position = PlatePosition.from_absolute_position(current_abs + 1)
        return self.move_to_position(next_position.plate, next_position.section, wait)
    
    def start_collection(self):
        """Start collecting in current position"""
        if not self.is_initialized:
            logger.error("Cannot start collection - not initialized")
            return False
        
        self.status = CollectorStatus.COLLECTING
        self.current_fraction_start_time = time.time()
        self.current_fraction_volume = 0
        
        logger.info(f"Started collection at {self.current_position} in {self.collection_mode.value} mode")
        return True
    
    def stop_collection(self):
        """Stop current collection"""
        if self.status != CollectorStatus.COLLECTING:
            logger.warning("Not currently collecting")
            return False
        
        # Record collected fraction
        if self.current_fraction_start_time:
            collection_time = time.time() - self.current_fraction_start_time
            self.collected_fractions.append({
                'position': PlatePosition(self.current_position.plate, self.current_position.section),
                'volume': self.current_fraction_volume,
                'time': collection_time,
                'timestamp': time.time()
            })
            
            # Update plate layout
            plate = self.current_position.plate
            section = self.current_position.section
            self.plate_layout[plate][section]['volume_collected'] += self.current_fraction_volume
            self.plate_layout[plate][section]['fractions'].append({
                'volume': self.current_fraction_volume,
                'time': collection_time
            })
        
        self.status = CollectorStatus.IDLE
        self.current_fraction_start_time = None
        logger.info(f"Stopped collection at {self.current_position}")
        return True
    
    def simulate_volume_collected(self, volume_ml: float):
        """
        Simulate volume being collected (called by pump during dispensing)
        
        Args:
            volume_ml: Volume dispensed in mL
        """
        if self.status == CollectorStatus.COLLECTING:
            self.current_fraction_volume += volume_ml
            self.total_volume_collected += volume_ml
            
            # Check if we should advance based on collection mode
            if self.collection_mode == CollectionMode.VOLUME:
                if self.current_fraction_volume >= self.collection_volume_ml:
                    logger.info(f"Volume limit reached ({self.current_fraction_volume:.2f} mL), advancing...")
                    self.stop_collection()
                    self.advance_position()
                    self.start_collection()
            
            elif self.collection_mode == CollectionMode.TIME:
                elapsed = time.time() - self.current_fraction_start_time
                if elapsed >= self.collection_time_sec:
                    logger.info(f"Time limit reached ({elapsed:.1f} sec), advancing...")
                    self.stop_collection()
                    self.advance_position()
                    self.start_collection()
    
    def set_collection_mode(self, mode: CollectionMode, value: Optional[float] = None):
        """
        Set collection mode and parameters
        
        Args:
            mode: Collection mode
            value: Time in seconds (TIME mode) or volume in mL (VOLUME mode)
        """
        self.collection_mode = mode
        
        if mode == CollectionMode.TIME and value:
            self.collection_time_sec = value
            logger.info(f"Set collection mode to TIME: {value} seconds per fraction")
        elif mode == CollectionMode.VOLUME and value:
            self.collection_volume_ml = value
            logger.info(f"Set collection mode to VOLUME: {value} mL per fraction")
        else:
            logger.info(f"Set collection mode to {mode.value}")
    
    def get_status(self) -> dict:
        """Get current collector status"""
        status_dict = {
            'connected': self.is_connected,
            'initialized': self.is_initialized,
            'status': self.status.value,
            'current_position': {
                'plate': self.current_position.plate,
                'section': self.current_position.section,
                'absolute': self.current_position.to_absolute_position()
            },
            'collection_mode': self.collection_mode.value,
            'is_collecting': self.status == CollectorStatus.COLLECTING,
            'is_moving': self.is_moving,
            'total_volume_collected': self.total_volume_collected,
            'fractions_collected': len(self.collected_fractions)
        }
        
        # Add current collection info if collecting
        if self.status == CollectorStatus.COLLECTING and self.current_fraction_start_time:
            status_dict['current_fraction'] = {
                'volume': self.current_fraction_volume,
                'time_elapsed': time.time() - self.current_fraction_start_time
            }
        
        return status_dict
    
    def get_plate_map(self) -> str:
        """
        Get visual representation of plate layout
        
        Returns:
            str: ASCII representation of plates and fill status
        """
        output = []
        output.append("Fraction Collector Plate Map")
        output.append("=" * 50)
        
        for plate in range(1, self.num_plates + 1):
            output.append(f"\nPlate {plate}:")
            row = []
            for section in range(1, self.sections_per_plate + 1):
                vol = self.plate_layout[plate][section]['volume_collected']
                
                # Mark current position
                if self.current_position.plate == plate and self.current_position.section == section:
                    if self.status == CollectorStatus.COLLECTING:
                        marker = f"[*{section}*]"  # Currently collecting
                    else:
                        marker = f"[>{section}<]"  # Current position
                else:
                    marker = f"[ {section} ]"
                
                # Add volume indicator
                if vol > 0:
                    marker += f" {vol:.1f}mL"
                else:
                    marker += " empty"
                    
                row.append(marker)
            
            output.append("  " + "  ".join(row))
        
        output.append("\n" + "=" * 50)
        output.append(f"Total Volume Collected: {self.total_volume_collected:.2f} mL")
        output.append(f"Fractions Collected: {len(self.collected_fractions)}")
        
        return "\n".join(output)
    
    def reset(self):
        """Reset collector to initial state"""
        logger.info("Resetting fraction collector...")
        
        # Clear collection data
        self.collected_fractions = []
        self.total_volume_collected = 0
        self.current_fraction_volume = 0
        self.current_fraction_start_time = None
        
        # Reset plate layout
        self.plate_layout = self._generate_plate_layout()
        
        # Return to home
        if self.is_initialized:
            self.move_to_position(self.home_position.plate, self.home_position.section)
        
        logger.info("Fraction collector reset complete")
    
    def pause(self):
        """Pause current operation"""
        if self.status == CollectorStatus.COLLECTING:
            self.status = CollectorStatus.PAUSED
            logger.info("Collection paused")
            return True
        return False
    
    def resume(self):
        """Resume paused operation"""
        if self.status == CollectorStatus.PAUSED:
            self.status = CollectorStatus.COLLECTING
            logger.info("Collection resumed")
            return True
        return False
    
    def update(self):
        """
        Update method to be called periodically to simulate real-time operations
        This would be called by the system controller in a loop
        """
        # Complete movement if time has elapsed
        if self.is_moving and self.move_start_time:
            elapsed = time.time() - self.move_start_time
            if elapsed >= self.movement_time_sec:
                self._complete_movement()
        
        # Auto-advance based on collection mode
        if self.status == CollectorStatus.COLLECTING:
            if self.collection_mode == CollectionMode.TIME:
                elapsed = time.time() - self.current_fraction_start_time
                if elapsed >= self.collection_time_sec:
                    self.stop_collection()
                    if self.advance_position(wait=False):
                        self.start_collection()