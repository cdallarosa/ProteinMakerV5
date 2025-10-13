"""
Callback modules for XLP6000 Dash application
"""

from .connection import register_connection_callbacks
from .manual_control import register_manual_control_callbacks
from .sequence import register_sequence_callbacks
from .method import register_method_callbacks

__all__ = [
    'register_connection_callbacks',
    'register_manual_control_callbacks',
    'register_sequence_callbacks',
    'register_method_callbacks'
]
