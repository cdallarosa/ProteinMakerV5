"""
XLP6000 Pump Control Package
Provides hardware control and process orchestration for XLP6000 syringe pumps
"""

from .pump_class import Pump, PumpConfig

# from system_configuration.pump.backup.controller import XLP6000Controller  # Backward compatibility

__all__ = ['Pump', 'PumpConfig']
