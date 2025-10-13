"""
Chromatography Column Class
Represents a column connected to a pump in the purification system
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional

class ColumnType(Enum):
    """Types of chromatography columns"""
    PROTEIN_A = "protein_a"
    PROTEIN_G = "protein_g"
    ION_EXCHANGE = "ion_exchange"
    SIZE_EXCLUSION = "size_exclusion"
    HYDROPHOBIC = "hydrophobic"
    AFFINITY = "affinity"
    CUSTOM = "custom"


@dataclass
class ColumnConfig:
    """Column configuration parameters"""
    name: str
    column_type: ColumnType
    volume_ml: float  # Column bed volume
    max_pressure_bar: float = 5.0
    max_flow_rate_ml_min: float = 5.0
    diameter_mm: float = 10.0
    height_mm: float = 100.0


class Column:
    """
    Represents a chromatography column
    
    Tracks column usage, washing, and regeneration cycles
    """
    
    def __init__(self, config: ColumnConfig):
        self.config = config
        self.is_equilibrated = False
        self.total_volume_processed_ml = 0
        self.cycles_run = 0
        self.current_buffer = None
        
    def equilibrate(self, buffer_name: str, volume_ml: float):
        """Record column equilibration"""
        self.current_buffer = buffer_name
        self.is_equilibrated = True
        return True
    
    def process_sample(self, volume_ml: float):
        """Record sample processing"""
        self.total_volume_processed_ml += volume_ml
        self.cycles_run += 1
    
    def get_info(self) -> dict:
        """Get column information"""
        return {
            'name': self.config.name,
            'type': self.config.column_type.value,
            'volume_ml': self.config.volume_ml,
            'is_equilibrated': self.is_equilibrated,
            'current_buffer': self.current_buffer,
            'cycles_run': self.cycles_run,
            'total_volume_ml': self.total_volume_processed_ml
        }