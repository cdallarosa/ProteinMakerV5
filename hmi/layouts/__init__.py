"""
Layout modules for XLP6000 Dash application
"""

from .dashboard import create_dashboard_layout
from .manual_control import create_manual_control_layout
from .sequence_builder import create_sequence_builder_layout
from .method_editor import create_method_editor_layout
from .configuration import create_configuration_layout, create_quick_actions_layout, create_operation_log_layout

__all__ = [
    'create_dashboard_layout',
    'create_manual_control_layout',
    'create_sequence_builder_layout',
    'create_method_editor_layout',
    'create_configuration_layout',
    'create_quick_actions_layout',
    'create_operation_log_layout'
]
