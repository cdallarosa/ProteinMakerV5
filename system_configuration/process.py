"""
Chromatography Process Definition
Defines a complete purification process that can be run on any pump
"""

from dataclasses import dataclass
from typing import List, Optional, Dict
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ProcessType(Enum):
    """Types of chromatography processes"""
    PROTEIN_A_PURIFICATION = "protein_a_purification"
    BUFFER_EXCHANGE = "buffer_exchange"
    SAMPLE_LOADING = "sample_loading"
    COLUMN_WASH = "column_wash"
    ELUTION = "elution"
    REGENERATION = "regeneration"
    CUSTOM = "custom"


@dataclass
class ProcessStep:
    """Individual step in a chromatography process"""
    name: str
    inlet: int
    outlet: int
    volume_ml: float
    flow_rate_ml_min: float
    prime: bool = False
    delay_after_sec: float = 0


@dataclass
class ProcessConfig:
    """Configuration for a complete chromatography process"""
    name: str
    process_type: ProcessType
    description: str
    steps: List[ProcessStep]
    total_time_min: Optional[float] = None
    expected_yield_percent: Optional[float] = None


class ChromatographyProcess:
    """
    Defines a complete chromatography process that can be executed on any pump
    
    This class encapsulates the entire purification workflow including:
    - Sample loading
    - Washing
    - Elution
    - Regeneration
    """
    
    def __init__(self, config: ProcessConfig):
        self.config = config
        self.current_step = 0
        self.is_running = False
        self.is_completed = False
        self.execution_log = []
        
    def get_total_time_estimate(self) -> float:
        """Calculate estimated total time for the process"""
        if self.config.total_time_min:
            return self.config.total_time_min
        
        # Calculate from steps
        total_time = 0
        for step in self.config.steps:
            step_time = step.volume_ml / step.flow_rate_ml_min
            total_time += step_time + step.delay_after_sec / 60
        
        return total_time
    
    def get_total_volume(self) -> float:
        """Calculate total volume for the process"""
        return sum(step.volume_ml for step in self.config.steps)
    
    def get_step_info(self, step_index: int) -> Dict:
        """Get information about a specific step"""
        if 0 <= step_index < len(self.config.steps):
            step = self.config.steps[step_index]
            return {
                'name': step.name,
                'inlet': step.inlet,
                'outlet': step.outlet,
                'volume_ml': step.volume_ml,
                'flow_rate_ml_min': step.flow_rate_ml_min,
                'prime': step.prime,
                'delay_after_sec': step.delay_after_sec,
                'estimated_time_min': step.volume_ml / step.flow_rate_ml_min
            }
        return {}
    
    def get_process_summary(self) -> Dict:
        """Get summary of the entire process"""
        return {
            'name': self.config.name,
            'type': self.config.process_type.value,
            'description': self.config.description,
            'total_steps': len(self.config.steps),
            'total_volume_ml': self.get_total_volume(),
            'estimated_time_min': self.get_total_time_estimate(),
            'expected_yield_percent': self.config.expected_yield_percent
        }
    
    def reset(self):
        """Reset process to initial state"""
        self.current_step = 0
        self.is_running = False
        self.is_completed = False
        self.execution_log = []


# ============================================================================
# PRE-DEFINED PROCESSES
# ============================================================================

class ProcessLibrary:
    """Library of pre-defined chromatography processes"""
    
    @staticmethod
    def protein_a_purification() -> ChromatographyProcess:
        """Standard Protein A purification process"""
        steps = [
            ProcessStep(
                name="Equilibration",
                inlet=1,        # Equilibration buffer
                outlet=12,      # To column
                volume_ml=5.0,
                flow_rate_ml_min=2.0,
                prime=True
            ),
            ProcessStep(
                name="Sample Loading",
                inlet=2,        # Sample
                outlet=12,      # To column
                volume_ml=10.0,
                flow_rate_ml_min=1.0,
                delay_after_sec=30  # Let sample bind
            ),
            ProcessStep(
                name="Wash 1 - Low Salt",
                inlet=3,        # Wash buffer 1
                outlet=11,      # To waste
                volume_ml=15.0,
                flow_rate_ml_min=2.0
            ),
            ProcessStep(
                name="Wash 2 - High Salt",
                inlet=4,        # Wash buffer 2
                outlet=11,      # To waste
                volume_ml=10.0,
                flow_rate_ml_min=2.0
            ),
            ProcessStep(
                name="Elution",
                inlet=5,        # Elution buffer
                outlet=12,      # To fraction collector
                volume_ml=8.0,
                flow_rate_ml_min=1.0
            ),
            ProcessStep(
                name="Regeneration",
                inlet=6,        # Regeneration buffer
                outlet=11,      # To waste
                volume_ml=5.0,
                flow_rate_ml_min=2.0
            )
        ]
        
        config = ProcessConfig(
            name="Protein A Purification",
            process_type=ProcessType.PROTEIN_A_PURIFICATION,
            description="Standard Protein A affinity purification with wash and elution",
            steps=steps,
            total_time_min=35.0,
            expected_yield_percent=85.0
        )
        
        return ChromatographyProcess(config)
    
    @staticmethod
    def buffer_exchange() -> ChromatographyProcess:
        """Simple buffer exchange process"""
        steps = [
            ProcessStep(
                name="Sample Loading",
                inlet=1,        # Sample in old buffer
                outlet=12,      # To column
                volume_ml=5.0,
                flow_rate_ml_min=1.0,
                prime=True
            ),
            ProcessStep(
                name="Buffer Exchange",
                inlet=2,        # New buffer
                outlet=12,      # To fraction collector
                volume_ml=15.0,
                flow_rate_ml_min=1.5
            )
        ]
        
        config = ProcessConfig(
            name="Buffer Exchange",
            process_type=ProcessType.BUFFER_EXCHANGE,
            description="Simple buffer exchange using size exclusion",
            steps=steps,
            total_time_min=13.0,
            expected_yield_percent=95.0
        )
        
        return ChromatographyProcess(config)
    
    @staticmethod
    def quick_wash() -> ChromatographyProcess:
        """Quick column wash and regeneration"""
        steps = [
            ProcessStep(
                name="High Salt Wash",
                inlet=1,        # High salt buffer
                outlet=11,      # To waste
                volume_ml=10.0,
                flow_rate_ml_min=3.0,
                prime=True
            ),
            ProcessStep(
                name="Regeneration",
                inlet=2,        # Regeneration buffer
                outlet=11,      # To waste
                volume_ml=5.0,
                flow_rate_ml_min=3.0
            ),
            ProcessStep(
                name="Storage Buffer",
                inlet=3,        # Storage buffer
                outlet=11,      # To waste
                volume_ml=3.0,
                flow_rate_ml_min=2.0
            )
        ]
        
        config = ProcessConfig(
            name="Quick Column Wash",
            process_type=ProcessType.REGENERATION,
            description="Fast column cleaning and regeneration",
            steps=steps,
            total_time_min=8.0
        )
        
        return ChromatographyProcess(config)
    
    @staticmethod
    def custom_process(name: str, steps: List[ProcessStep], description: str = "") -> ChromatographyProcess:
        """Create a custom process from provided steps"""
        config = ProcessConfig(
            name=name,
            process_type=ProcessType.CUSTOM,
            description=description or f"Custom process: {name}",
            steps=steps
        )
        
        return ChromatographyProcess(config)
    
    @staticmethod
    def list_available_processes() -> List[str]:
        """Get list of available pre-defined processes"""
        return [
            "protein_a_purification",
            "buffer_exchange", 
            "quick_wash"
        ]
    
    @staticmethod
    def get_process(process_name: str) -> Optional[ChromatographyProcess]:
        """Get a pre-defined process by name"""
        processes = {
            "protein_a_purification": ProcessLibrary.protein_a_purification,
            "buffer_exchange": ProcessLibrary.buffer_exchange,
            "quick_wash": ProcessLibrary.quick_wash
        }
        
        if process_name in processes:
            return processes[process_name]()
        else:
            logger.error(f"Unknown process: {process_name}")
            return None