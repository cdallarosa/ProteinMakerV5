"""
XLP6000 Pump Control System - Main Application
"""

import dash
from dash import dcc, html, Input, Output
import dash_bootstrap_components as dbc
from layouts.dashboard import create_dashboard_layout
from layouts.manual_control import create_manual_control_layout
from layouts.method_editor import create_method_editor_layout
from layouts.sequence_builder import create_sequence_builder_layout
from layouts.configuration import create_configuration_layout
from callbacks.method_builder import register_method_builder_callbacks

# Initialize controller first
controller = None
try:
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from system_configuration.pump.pump_class import Pump
    controller = Pump()
    print("[SUCCESS] Controller initialized successfully.")
except ImportError as e:
    print(f"[WARNING] Controller module not found: {e}")
    print("[INFO] Running in DEMO MODE with mock controller")
    # Create a mock controller for demo mode
    class MockController:
        def __init__(self):
            self.is_connected = False
            self.current_position = 0
            self.valve_position = "INPUT_1"
            self.selected_inlet_valve = "A1"
            self.selected_outlet_valve = "Waste"
            self.continuous_pumping_inlet = "A1"
            self.continuous_pumping_outlet = "Waste"
            # Load method templates from JSON
            try:
                import json
                import os
                json_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'purification_process', 'example_processes.json')
                print(f"[DEBUG] Looking for JSON at: {json_path}")
                with open(json_path, 'r') as f:
                    self.method_templates = json.load(f)
                print(f"[SUCCESS] Loaded {len(self.method_templates)} method templates")
            except Exception as e:
                print(f"[ERROR] Failed to load method templates: {e}")
                self.method_templates = {}
    controller = MockController()
except Exception as e:
    print(f"Warning: Could not initialize controller: {e}")
    # Create a mock controller for error cases
    class MockController:
        def __init__(self):
            self.is_connected = False
            self.current_position = 0
            self.valve_position = "INPUT_1"
            self.selected_inlet_valve = "A1"
            self.selected_outlet_valve = "Waste"
            self.continuous_pumping_inlet = "A1"
            self.continuous_pumping_outlet = "Waste"
            # Load method templates from JSON
            try:
                import json
                import os
                json_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'purification_process', 'example_processes.json')
                print(f"[DEBUG] Looking for JSON at: {json_path}")
                with open(json_path, 'r') as f:
                    self.method_templates = json.load(f)
                print(f"[SUCCESS] Loaded {len(self.method_templates)} method templates")
            except Exception as e:
                print(f"[ERROR] Failed to load method templates: {e}")
                self.method_templates = {}
    controller = MockController()

app = dash.Dash(__name__, 
                external_stylesheets=[dbc.themes.BOOTSTRAP],
                suppress_callback_exceptions=True)

app.layout = html.Div([
    dcc.Location(id='url', refresh=False),
    
    html.Div([
        html.H1("XLP6000 Pump Control System", 
                style={'textAlign': 'center', 'color': '#2d3748', 'marginBottom': '20px'}),
        
        dbc.Nav([
            dbc.NavLink("Dashboard", href="/", active="exact"),
            dbc.NavLink("Manual Control", href="/manual", active="exact"),
            dbc.NavLink("Method Editor", href="/method", active="exact"),
            dbc.NavLink("Sequence Builder", href="/sequence", active="exact"),
            dbc.NavLink("Configuration", href="/config", active="exact"),
        ], pills=True, style={'marginBottom': '20px', 'justifyContent': 'center'}),
    ], style={'padding': '20px', 'backgroundColor': '#f7fafc'}),
    
    html.Div(id='page-content')
])

@app.callback(Output('page-content', 'children'),
              Input('url', 'pathname'))
def display_page(pathname):
    print(f"[NAVIGATION] Loading page: {pathname}")
    try:
        if pathname == '/manual':
            print("[INFO] Loading Manual Control layout")
            return create_manual_control_layout(controller)
        elif pathname == '/method':
            print("[INFO] Loading Method Editor layout")
            return create_method_editor_layout()
        elif pathname == '/sequence':
            print("[INFO] Loading Sequence Builder layout")
            return create_sequence_builder_layout(controller)
        elif pathname == '/config':
            print("[INFO] Loading Configuration layout")
            return create_configuration_layout()
        else:
            print("[INFO] Loading Dashboard layout (default)")
            return create_dashboard_layout()
    except Exception as e:
        print(f"[ERROR] Failed to load page {pathname}: {e}")
        import traceback
        traceback.print_exc()
        return html.Div([
            html.H3("Error loading page", style={'color': 'red'}),
            html.P(f"Error: {str(e)}")
        ])

# Register callbacks
register_method_builder_callbacks(app)

if __name__ == '__main__':
    print("\n" + "="*60)
    print("XLP6000 PUMP CONTROL SYSTEM - HMI APPLICATION")
    print("="*60)
    print(f"[INFO] Controller Type: {'Hardware' if controller.__class__.__name__ == 'Pump' else 'Mock'}")
    print(f"[INFO] Debug Mode: ON")
    print(f"[INFO] Server: http://127.0.0.1:8050")
    print("="*60 + "\n")
    app.run(debug=True, host='127.0.0.1', port=8050)