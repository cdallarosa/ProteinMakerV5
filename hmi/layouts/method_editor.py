"""
Method editor layout for XLP6000 application
Includes predefined method loading and step management
"""

from dash import dcc, html
import json


def create_method_editor_layout():
    # Load predefined methods for templates
    try:
        import os
        json_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'purification_process', 'example_processes.json')
        print(f"[METHOD EDITOR] Looking for JSON at: {json_path}")
        with open(json_path, 'r') as f:
            predefined_methods = json.load(f)
        print(f"[METHOD EDITOR] Successfully loaded {len(predefined_methods)} predefined methods")
        for key, value in predefined_methods.items():
            print(f"  - {key}: {value.get('process_name', 'Unknown')} ({len(value.get('steps', []))} steps)")
    except Exception as e:
        print(f"[METHOD EDITOR ERROR] Failed to load predefined methods: {e}")
        predefined_methods = {
            "protein_a_purification": {"process_name": "Protein A Purification", "steps": []},
            "size_exclusion_chromatography": {"process_name": "Size Exclusion Chromatography", "steps": []},
            "anion_exchange": {"process_name": "Anion Exchange Chromatography", "steps": []}
        }
        print("[METHOD EDITOR] Using default placeholder methods")
    
    return html.Div([
        # Header with title
        html.H2([
            html.I(className="fas fa-flask", style={'marginRight': '10px'}), 
            "Method Builder"
        ], className='page-title'),

        # Method Templates Section
        html.Div([
            html.H3([
                html.I(className="fas fa-book", style={'marginRight': '8px'}), 
                "Predefined Methods"
            ], className='section-title'),
            
            html.P("Select a predefined chromatography method to load or start building a custom method.",
                   style={'color': '#6b7280', 'marginBottom': '20px'}),
            
            html.Div([
                html.Div([
                    dcc.Dropdown(
                        id='predefined-method-dropdown',
                        options=[
                            {'label': method_data['process_name'], 'value': method_key}
                            for method_key, method_data in predefined_methods.items()
                        ],
                        placeholder="Select a predefined method...",
                        className='form-input',
                        style={'width': '400px', 'zIndex': 1000}
                    )
                ], style={'display': 'inline-block', 'marginRight': '15px', 'verticalAlign': 'top'}),
                html.Div([
                    html.Button(
                        [html.I(className="fas fa-download", style={'marginRight': '6px'}), "Load Method"],
                        id='load-predefined-method-btn',
                        className='control-button primary'
                    )
                ], style={'display': 'inline-block', 'verticalAlign': 'top'})
            ], style={'marginBottom': '30px', 'display': 'flex', 'alignItems': 'center'})
        ], className='card', style={'overflow': 'visible', 'position': 'relative', 'zIndex': 100}),

        # Main Method Editor Container
        html.Div([
            # Left Panel - Method Steps Display
            html.Div([
                html.Div([
                    html.H3([
                        html.I(className="fas fa-list", style={'marginRight': '8px'}), 
                        "Method Steps"
                    ], style={'display': 'inline-block', 'marginRight': '20px'}),
                    
                    html.Div([
                        html.Button(
                            [html.I(className="fas fa-file-export", style={'marginRight': '6px'}), "Save Method"],
                            id='save-method-btn',
                            className='control-button success',
                            style={'marginRight': '10px'}
                        ),
                        html.Button(
                            [html.I(className="fas fa-trash", style={'marginRight': '6px'}), "Clear All"],
                            id='clear-method-btn',
                            className='control-button danger'
                        )
                    ], style={'display': 'inline-block'})
                ], style={'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'center', 'marginBottom': '20px'}),
                
                # Method Steps List
                html.Div(
                    id='method-steps-display',
                    children=[
                        html.Div([
                            html.P("No steps added yet.", 
                                   style={'textAlign': 'center', 'color': '#6b7280', 'fontStyle': 'italic'})
                        ], style={'padding': '40px', 'textAlign': 'center'})
                    ],
                    style={
                        'minHeight': '400px', 
                        'maxHeight': '600px', 
                        'overflowY': 'auto',
                        'border': '1px solid #e2e8f0',
                        'borderRadius': '8px',
                        'padding': '15px',
                        'backgroundColor': '#f8fafc'
                    }
                ),
                
                # Process Control Buttons
                html.Div([
                    html.Button(
                        [html.I(className="fas fa-play", style={'marginRight': '6px'}), "Run Method"],
                        id='run-method-btn',
                        className='control-button success',
                        style={'marginRight': '10px', 'fontSize': '1.1rem', 'padding': '12px 24px'}
                    ),
                    html.Button(
                        [html.I(className="fas fa-pause", style={'marginRight': '6px'}), "Pause"],
                        id='pause-method-btn',
                        className='control-button warning',
                        style={'marginRight': '10px'}
                    ),
                    html.Button(
                        [html.I(className="fas fa-stop", style={'marginRight': '6px'}), "Stop"],
                        id='stop-method-btn',
                        className='control-button danger'
                    )
                ], style={'textAlign': 'center', 'marginTop': '20px', 'padding': '20px', 'backgroundColor': '#f1f5f9', 'borderRadius': '8px'})
            ], className='card', style={'width': '65%', 'marginRight': '2%'}),

            # Right Panel - Step Editor
            html.Div([
                html.H3([
                    html.I(className="fas fa-plus-circle", style={'marginRight': '8px'}), 
                    html.Span("Add New Step", id='step-editor-title')
                ], className='section-title', id='step-editor-header'),

                # Step Type Selection
                html.Div([
                    html.Label("Step Type:", className='input-label'),
                    dcc.Dropdown(
                        id='step-type-dropdown',
                        options=[
                            {'label': '🔄 Equilibration', 'value': 'equilibration'},
                            {'label': '💉 Sample Application', 'value': 'sample_application'},
                            {'label': '🚿 Wash', 'value': 'wash'},
                            {'label': '🧪 Elution', 'value': 'elution'},
                            {'label': '🧽 Cleaning', 'value': 'cleaning'},
                            {'label': '⚡ Prime', 'value': 'prime'},
                            {'label': '⏰ Wait/Delay', 'value': 'wait'}
                        ],
                        value='equilibration',
                        className='form-input'
                    )
                ], style={'marginBottom': '15px'}),

                # Volume Input
                html.Div([
                    html.Label("Volume (μL):", className='input-label'),
                    dcc.Input(
                        id='step-volume-input',
                        type='number',
                        value=1000,
                        min=1,
                        max=50000,
                        className='form-input',
                        style={'width': '100%'}
                    )
                ], style={'marginBottom': '15px'}),

                # Flow Rate Input
                html.Div([
                    html.Label("Flow Rate (μL/min):", className='input-label'),
                    dcc.Input(
                        id='step-flowrate-input',
                        type='number',
                        value=1000,
                        min=1,
                        max=10000,
                        className='form-input',
                        style={'width': '100%'}
                    )
                ], style={'marginBottom': '15px'}),

                # Inlet Valve Selection
                html.Div([
                    html.Label("Inlet Valve:", className='input-label'),
                    dcc.Dropdown(
                        id='step-inlet-valve-dropdown',
                        options=[
                            {'label': f'Inlet {i}', 'value': i}
                            for i in range(1, 11)
                        ],
                        value=1,
                        className='form-input'
                    )
                ], style={'marginBottom': '15px'}),

                # Outlet Valve Selection
                html.Div([
                    html.Label("Outlet Valve:", className='input-label'),
                    dcc.Dropdown(
                        id='step-outlet-valve-dropdown',
                        options=[
                            {'label': 'Waste', 'value': 1},
                            {'label': 'Collect', 'value': 2}
                        ],
                        value=1,
                        className='form-input'
                    )
                ], style={'marginBottom': '15px'}),

                # Prime Pump Option
                html.Div([
                    dcc.Checklist(
                        id='step-prime-pump-checkbox',
                        options=[{'label': ' Prime pump before step', 'value': 'prime'}],
                        value=[],
                        style={'marginBottom': '10px'}
                    ),
                    html.Div([
                        html.Label("Prime Volume (μL):", className='input-label'),
                        dcc.Input(
                            id='step-prime-volume-input',
                            type='number',
                            value=500,
                            min=1,
                            max=5000,
                            className='form-input',
                            style={'width': '100%'},
                            disabled=True
                        )
                    ], id='prime-volume-container', style={'display': 'none'})
                ], style={'marginBottom': '15px'}),

                # Description Input
                html.Div([
                    html.Label("Description:", className='input-label'),
                    dcc.Textarea(
                        id='step-description-input',
                        placeholder="Enter step description...",
                        className='form-input',
                        style={'width': '100%', 'height': '80px', 'resize': 'vertical'}
                    )
                ], style={'marginBottom': '20px'}),

                # Step Action Buttons
                html.Div([
                    html.Button(
                        [html.I(className="fas fa-plus", style={'marginRight': '6px'}), "Add Step to Method"],
                        id='add-step-btn',
                        className='control-button primary',
                        style={'width': '100%', 'padding': '12px', 'display': 'block'}
                    ),
                    html.Button(
                        [html.I(className="fas fa-save", style={'marginRight': '6px'}), "Update Step"],
                        id='update-step-btn',
                        className='control-button success',
                        style={'width': '48%', 'padding': '12px', 'marginRight': '4%', 'display': 'none'}
                    ),
                    html.Button(
                        [html.I(className="fas fa-times", style={'marginRight': '6px'}), "Cancel"],
                        id='cancel-edit-btn',
                        className='control-button secondary',
                        style={'width': '48%', 'padding': '12px', 'display': 'none'}
                    )
                ], id='step-action-buttons'),
                
                # Method Status Display
                html.Div(
                    id='method-status-display',
                    children="Ready to add steps",
                    style={
                        'padding': '12px',
                        'backgroundColor': '#f1f5f9',
                        'borderRadius': '8px',
                        'textAlign': 'center',
                        'fontWeight': '600',
                        'marginTop': '15px'
                    }
                )
            ], className='card', style={'width': '33%'})
        ], style={'display': 'flex', 'alignItems': 'flex-start'}),
        
        # Hidden divs to store method data and editing state
        html.Div(id='method-data-store', style={'display': 'none'}),
        dcc.Store(id='editing-step-index', data=None)
        
    ], style={'margin': '20px', 'maxWidth': '1400px', 'marginLeft': 'auto', 'marginRight': 'auto'})