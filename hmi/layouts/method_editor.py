"""
Method editor layout for XLP6000 application
"""

from dash import dcc, html


def create_method_editor_layout():
    return html.Div([
        html.Div([
            # Method Steps Display
            html.Div([
                html.H3([html.I(className="fas fa-list"), " Method Steps"]),
                html.Div([
                    html.Button([html.I(className="fas fa-upload"), " Load"], className='control-button',
                                style={'margin': '5px'}),
                    html.Button([html.I(className="fas fa-download"), " Save"], className='control-button',
                                style={'margin': '5px'}),
                    html.Button([html.I(className="fas fa-trash"), " Clear"], id='clear-method-btn',
                                className='control-button', style={'margin': '5px', 'background': '#ef4444'}),
                ]),
                html.Div(id='method-steps-display',
                         style={'marginTop': '20px', 'maxHeight': '400px', 'overflowY': 'auto'})
            ], className='card', style={'width': '60%', 'display': 'inline-block', 'verticalAlign': 'top'}),

            # Step Editor
            html.Div([
                html.H3("Add Method Step"),
                html.Div([
                    html.Label("Step Type:"),
                    dcc.Dropdown(
                        id='step-type-dropdown',
                        options=[
                            {'label': 'Aspirate', 'value': 'aspirate'},
                            {'label': 'Dispense', 'value': 'dispense'},
                            {'label': 'Move Valve', 'value': 'move_valve'},
                            {'label': 'Wait/Delay', 'value': 'wait'},
                            {'label': 'Wash', 'value': 'wash'}
                        ],
                        value='aspirate'
                    )
                ], style={'marginBottom': '15px'}),

                html.Div([
                    html.Label("Volume (μL):"),
                    dcc.Input(id='step-volume-input', type='number', value=100, min=1, max=50000)
                ], style={'marginBottom': '15px'}),

                html.Div([
                    html.Label("Speed (steps/sec):"),
                    dcc.Input(id='step-speed-input', type='number', value=1000, min=1, max=5800)
                ], style={'marginBottom': '15px'}),

                html.Div([
                    html.Label("Valve Position:"),
                    dcc.Dropdown(
                        id='step-valve-dropdown',
                        options=[
                            {'label': 'Input', 'value': 'Input'},
                            {'label': 'Output', 'value': 'Output'},
                            {'label': 'Bypass', 'value': 'Bypass'}
                        ],
                        value='Input'
                    )
                ], style={'marginBottom': '15px'}),

                html.Div([
                    html.Label("Description:"),
                    dcc.Input(id='step-description-input', type='text', placeholder="Step description")
                ], style={'marginBottom': '15px'}),

                html.Button("Add Step", id='add-step-btn', className='control-button', style={'width': '100%'})
            ], className='card',
                style={'width': '35%', 'display': 'inline-block', 'verticalAlign': 'top', 'marginLeft': '5%'})
        ])
    ], style={'margin': '20px'})
