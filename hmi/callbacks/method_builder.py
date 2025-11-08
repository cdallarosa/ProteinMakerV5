"""
Callback functions for method builder functionality
"""

import json
from dash import Input, Output, State, callback, html, no_update
import dash

# Global method storage
current_method_steps = []


def register_method_builder_callbacks(app):
    """Register all method builder related callbacks"""
    print("[CALLBACKS] Registering method builder callbacks")
    
    # Handle clicking on a step or edit button to populate the editor
    @app.callback(
        [Output('step-type-dropdown', 'value', allow_duplicate=True),
         Output('step-volume-input', 'value', allow_duplicate=True),
         Output('step-flowrate-input', 'value', allow_duplicate=True),
         Output('step-inlet-valve-dropdown', 'value', allow_duplicate=True),
         Output('step-outlet-valve-dropdown', 'value', allow_duplicate=True),
         Output('step-prime-pump-checkbox', 'value', allow_duplicate=True),
         Output('step-prime-volume-input', 'value', allow_duplicate=True),
         Output('step-description-input', 'value', allow_duplicate=True),
         Output('editing-step-index', 'data', allow_duplicate=True),
         Output('step-editor-title', 'children', allow_duplicate=True),
         Output('add-step-btn', 'style', allow_duplicate=True),
         Output('update-step-btn', 'style', allow_duplicate=True),
         Output('cancel-edit-btn', 'style', allow_duplicate=True),
         Output('method-steps-display', 'children', allow_duplicate=True)],
        [Input({'type': 'method-step', 'index': dash.dependencies.ALL}, 'n_clicks'),
         Input({'type': 'edit-step-btn', 'index': dash.dependencies.ALL}, 'n_clicks'),
         Input('cancel-edit-btn', 'n_clicks')],
        [State('method-data-store', 'children'),
         State('editing-step-index', 'data')],
        prevent_initial_call=True
    )
    def handle_step_selection(step_clicks, edit_clicks, cancel_click, method_json, current_editing_index):
        global current_method_steps
        
        ctx = dash.callback_context
        if not ctx.triggered:
            return no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update
        
        trigger = ctx.triggered[0]['prop_id']
        print(f"[CALLBACK] Step selection triggered by: {trigger}")
        
        # Handle cancel button
        if 'cancel-edit-btn' in trigger:
            print("[CALLBACK] Cancel edit clicked - resetting editor")
            steps_display = create_steps_display(current_method_steps, None)
            return ('equilibration', 1000, 1000, 1, 1, [], 500, '', None, 'Add New Step',
                   {'width': '100%', 'padding': '12px', 'display': 'block'},
                   {'width': '48%', 'padding': '12px', 'marginRight': '4%', 'display': 'none'},
                   {'width': '48%', 'padding': '12px', 'display': 'none'},
                   steps_display)
        
        # Determine which button was clicked and get the index
        step_index = None
        if 'method-step' in trigger or 'edit-step-btn' in trigger:
            button_id = json.loads(trigger.split('.')[0])
            step_index = button_id['index']
            print(f"[CALLBACK] Step {step_index} selected for editing")
        
        if step_index is not None and 0 <= step_index < len(current_method_steps):
            step = current_method_steps[step_index]
            
            # Populate editor fields with step data
            prime_checkbox = ['prime'] if step.get('prime_pump', False) else []
            
            # Update steps display with selection
            steps_display = create_steps_display(current_method_steps, step_index)
            
            return (
                step.get('step_type', 'equilibration'),
                step.get('volume', 1000),
                step.get('flowrate', 1000),
                step.get('inlet_valve', 1),
                step.get('outlet_valve', 1),
                prime_checkbox,
                step.get('prime_volume', 500),
                step.get('description', ''),
                step_index,
                f"Edit Step {step_index + 1}",
                {'width': '100%', 'padding': '12px', 'display': 'none'},
                {'width': '48%', 'padding': '12px', 'marginRight': '4%', 'display': 'inline-block'},
                {'width': '48%', 'padding': '12px', 'display': 'inline-block'},
                steps_display
            )
        
        return no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update
    
    # Handle updating an existing step
    @app.callback(
        [Output('method-steps-display', 'children', allow_duplicate=True),
         Output('method-data-store', 'children', allow_duplicate=True),
         Output('method-status-display', 'children', allow_duplicate=True),
         Output('editing-step-index', 'data', allow_duplicate=True),
         Output('step-editor-title', 'children', allow_duplicate=True),
         Output('add-step-btn', 'style', allow_duplicate=True),
         Output('update-step-btn', 'style', allow_duplicate=True),
         Output('cancel-edit-btn', 'style', allow_duplicate=True)],
        Input('update-step-btn', 'n_clicks'),
        [State('editing-step-index', 'data'),
         State('step-type-dropdown', 'value'),
         State('step-volume-input', 'value'),
         State('step-flowrate-input', 'value'),
         State('step-inlet-valve-dropdown', 'value'),
         State('step-outlet-valve-dropdown', 'value'),
         State('step-prime-pump-checkbox', 'value'),
         State('step-prime-volume-input', 'value'),
         State('step-description-input', 'value')],
        prevent_initial_call=True
    )
    def update_existing_step(n_clicks, editing_index, step_type, volume, flowrate, inlet_valve, outlet_valve,
                            prime_checkbox, prime_volume, description):
        global current_method_steps
        
        if not n_clicks or editing_index is None:
            return no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update
        
        print(f"[CALLBACK] Updating step {editing_index}")
        
        if 0 <= editing_index < len(current_method_steps):
            # Update the step
            current_method_steps[editing_index] = {
                "step_name": f"Step {editing_index + 1}",
                "step_type": step_type,
                "volume": volume or 1000,
                "flowrate": flowrate or 1000,
                "inlet_valve": inlet_valve or 1,
                "outlet_valve": outlet_valve or 1,
                "prime_pump": 'prime' in prime_checkbox if prime_checkbox else False,
                "prime_volume": prime_volume if 'prime' in prime_checkbox else None,
                "wait_until_complete": True,
                "description": description or f"{step_type.replace('_', ' ').title()} step"
            }
            
            # Create updated display without selection
            steps_display = create_steps_display(current_method_steps, None)
            
            status_message = f"Updated Step {editing_index + 1}"
            print(f"[CALLBACK] Step updated successfully")
            
            # Reset editor to add mode
            return (steps_display, json.dumps(current_method_steps), status_message, None, 'Add New Step',
                   {'width': '100%', 'padding': '12px', 'display': 'block'},
                   {'width': '48%', 'padding': '12px', 'marginRight': '4%', 'display': 'none'},
                   {'width': '48%', 'padding': '12px', 'display': 'none'})
        
        return no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update

    # Show/hide prime volume input based on checkbox
    @app.callback(
        [Output('prime-volume-container', 'style'),
         Output('step-prime-volume-input', 'disabled')],
        Input('step-prime-pump-checkbox', 'value')
    )
    def toggle_prime_volume_input(prime_checkbox_value):
        if 'prime' in prime_checkbox_value:
            return {'marginBottom': '15px'}, False
        else:
            return {'display': 'none'}, True

    # Load predefined method
    @app.callback(
        [Output('method-steps-display', 'children'),
         Output('method-data-store', 'children'),
         Output('method-status-display', 'children')],
        Input('load-predefined-method-btn', 'n_clicks'),
        State('predefined-method-dropdown', 'value')
    )
    def load_predefined_method(n_clicks, selected_method):
        global current_method_steps
        
        print(f"[CALLBACK] Load predefined method called - n_clicks: {n_clicks}, selected: {selected_method}")
        
        if not n_clicks or not selected_method:
            return no_update, no_update, no_update
        
        # Load method from JSON
        try:
            import os
            json_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'purification_process', 'example_processes.json')
            print(f"[CALLBACK] Loading JSON from: {json_path}")
            with open(json_path, 'r') as f:
                methods = json.load(f)
            print(f"[CALLBACK] Loaded {len(methods)} methods from JSON")
            
            if selected_method in methods:
                method_data = methods[selected_method]
                current_method_steps = method_data['steps'].copy()
                print(f"[CALLBACK] Loading method '{selected_method}' with {len(current_method_steps)} steps")
                
                # Create method steps display
                steps_display = create_steps_display(current_method_steps)
                
                status_message = f"Loaded {method_data['process_name']} with {len(current_method_steps)} steps"
                print(f"[CALLBACK] Method loaded successfully: {status_message}")
                
                return steps_display, json.dumps(current_method_steps), status_message
            else:
                print(f"[CALLBACK ERROR] Method '{selected_method}' not found in loaded methods")
                return no_update, no_update, "Method not found"
        except Exception as e:
            print(f"[CALLBACK ERROR] Exception loading method: {e}")
            import traceback
            traceback.print_exc()
            return no_update, no_update, f"Error loading method: {str(e)}"

    # Add new step to method
    @app.callback(
        [Output('method-steps-display', 'children', allow_duplicate=True),
         Output('method-data-store', 'children', allow_duplicate=True),
         Output('method-status-display', 'children', allow_duplicate=True),
         Output('step-description-input', 'value', allow_duplicate=True)],
        Input('add-step-btn', 'n_clicks'),
        [State('step-type-dropdown', 'value'),
         State('step-volume-input', 'value'),
         State('step-flowrate-input', 'value'),
         State('step-inlet-valve-dropdown', 'value'),
         State('step-outlet-valve-dropdown', 'value'),
         State('step-prime-pump-checkbox', 'value'),
         State('step-prime-volume-input', 'value'),
         State('step-description-input', 'value'),
         State('method-data-store', 'children')],
        prevent_initial_call=True
    )
    def add_step_to_method(n_clicks, step_type, volume, flowrate, inlet_valve, outlet_valve, 
                          prime_checkbox, prime_volume, description, current_steps_json):
        global current_method_steps
        
        print(f"[CALLBACK] Add step called - n_clicks: {n_clicks}, type: {step_type}")
        
        if not n_clicks:
            return no_update, no_update, no_update, no_update
        
        # Create new step
        new_step = {
            "step_name": f"Step {len(current_method_steps) + 1}",
            "step_type": step_type,
            "volume": volume or 1000,
            "flowrate": flowrate or 1000,
            "inlet_valve": inlet_valve or 1,
            "outlet_valve": outlet_valve or 1,
            "prime_pump": 'prime' in prime_checkbox,
            "prime_volume": prime_volume if 'prime' in prime_checkbox else None,
            "wait_until_complete": True,
            "description": description or f"{step_type.replace('_', ' ').title()} step"
        }
        
        # Add to global steps
        current_method_steps.append(new_step)
        
        # Create updated display
        steps_display = create_steps_display(current_method_steps)
        
        status_message = f"Added {step_type.replace('_', ' ').title()} step. Method has {len(current_method_steps)} steps."
        
        return steps_display, json.dumps(current_method_steps), status_message, ""

    # Clear all method steps
    @app.callback(
        [Output('method-steps-display', 'children', allow_duplicate=True),
         Output('method-data-store', 'children', allow_duplicate=True),
         Output('method-status-display', 'children', allow_duplicate=True)],
        Input('clear-method-btn', 'n_clicks'),
        prevent_initial_call=True
    )
    def clear_method_steps(n_clicks):
        global current_method_steps
        
        if not n_clicks:
            return no_update, no_update, no_update
        
        current_method_steps = []
        
        empty_display = [
            html.Div([
                html.P("No steps added yet.", 
                       style={'textAlign': 'center', 'color': '#6b7280', 'fontStyle': 'italic'})
            ], style={'padding': '40px', 'textAlign': 'center'})
        ]
        
        return empty_display, json.dumps([]), "Method cleared. Ready to add steps."

    # Remove individual step
    @app.callback(
        [Output('method-steps-display', 'children', allow_duplicate=True),
         Output('method-data-store', 'children', allow_duplicate=True),
         Output('method-status-display', 'children', allow_duplicate=True)],
        Input({'type': 'remove-step-btn', 'index': dash.dependencies.ALL}, 'n_clicks'),
        prevent_initial_call=True
    )
    def remove_step(n_clicks_list):
        global current_method_steps
        
        if not any(n_clicks_list):
            return no_update, no_update, no_update
        
        # Find which button was clicked
        ctx = dash.callback_context
        if not ctx.triggered:
            return no_update, no_update, no_update
        
        button_id = ctx.triggered[0]['prop_id'].split('.')[0]
        step_index = json.loads(button_id)['index']
        
        # Remove step from global list
        if 0 <= step_index < len(current_method_steps):
            removed_step = current_method_steps.pop(step_index)
            
            # Update step numbering
            for i, step in enumerate(current_method_steps):
                step['step_name'] = f"Step {i + 1}"
            
            # Create updated display
            if current_method_steps:
                steps_display = create_steps_display(current_method_steps)
                status_message = f"Removed step. Method has {len(current_method_steps)} steps."
            else:
                steps_display = [
                    html.Div([
                        html.P("No steps added yet.", 
                               style={'textAlign': 'center', 'color': '#6b7280', 'fontStyle': 'italic'})
                    ], style={'padding': '40px', 'textAlign': 'center'})
                ]
                status_message = "All steps removed. Method is empty."
            
            return steps_display, json.dumps(current_method_steps), status_message
        
        return no_update, no_update, no_update


def create_steps_display(steps, selected_index=None):
    """Create the visual display of method steps"""
    if not steps:
        return [
            html.Div([
                html.P("No steps added yet.", 
                       style={'textAlign': 'center', 'color': '#6b7280', 'fontStyle': 'italic'})
            ], style={'padding': '40px', 'textAlign': 'center'})
        ]
    
    step_components = []
    
    for i, step in enumerate(steps):
        # Get step icon
        step_icons = {
            'equilibration': '🔄',
            'sample_application': '💉',
            'wash': '🚿',
            'elution': '🧪',
            'cleaning': '🧽',
            'prime': '⚡',
            'wait': '⏰'
        }
        
        icon = step_icons.get(step['step_type'], '📝')
        
        # Check if this step is selected for editing
        is_selected = (selected_index == i)
        
        step_component = html.Div([
            html.Div([
                html.Span(str(i + 1), className='step-number'),
                html.Div([
                    html.H4([
                        html.Span(icon, style={'marginRight': '8px'}),
                        step['step_name']
                    ], style={'margin': '0', 'fontSize': '1rem', 'fontWeight': '600'}),
                    html.P(step['description'], className='step-description'),
                    html.Div([
                        html.Span(f"Volume: {step['volume']} μL", 
                                 style={'marginRight': '15px', 'fontSize': '0.875rem'}),
                        html.Span(f"Flow: {step['flowrate']} μL/min", 
                                 style={'marginRight': '15px', 'fontSize': '0.875rem'}),
                        html.Span(f"Inlet: {step['inlet_valve']}", 
                                 style={'marginRight': '15px', 'fontSize': '0.875rem'}),
                        html.Span(f"Outlet: {'Waste' if step['outlet_valve'] == 1 else 'Collect'}", 
                                 style={'fontSize': '0.875rem'})
                    ], style={'color': '#6b7280'})
                ], className='step-info'),
                html.Div([
                    html.Button(
                        [html.I(className="fas fa-edit", style={'marginRight': '4px'}), "Edit"],
                        id={'type': 'edit-step-btn', 'index': i},
                        className='control-button secondary',
                        style={'marginRight': '5px', 'padding': '4px 8px', 'fontSize': '0.75rem'}
                    ),
                    html.Button(
                        [html.I(className="fas fa-trash", style={'marginRight': '4px'}), "Remove"],
                        id={'type': 'remove-step-btn', 'index': i},
                        className='control-button danger',
                        style={'padding': '4px 8px', 'fontSize': '0.75rem'}
                    )
                ], className='step-controls')
            ], style={'display': 'flex', 'alignItems': 'center'})
        ], 
        className='method-step method-step-selected' if is_selected else 'method-step',
        style={'marginBottom': '10px', 'cursor': 'pointer'},
        id={'type': 'method-step', 'index': i})
        
        step_components.append(step_component)
    
    return step_components