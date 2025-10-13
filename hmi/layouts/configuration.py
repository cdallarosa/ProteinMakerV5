"""
Configuration, quick actions, and operation log layouts for XLP6000 application
"""

from dash import dcc, html
import dash_bootstrap_components as dbc


def create_configuration_layout():
    return dbc.Container([
        # Row 1 - Communication and Pump Configuration
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.H4(
                            [html.I(className="fas fa-plug", style={'marginRight': '10px'}), "Communication Settings"],
                            className="text-center mb-0")
                    ]),
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("Serial Port:"),
                                dcc.Dropdown(id='port-dropdown', placeholder="Select port", value='COM12'),
                            ], className="mb-3"),
                        ]),
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("Baud Rate:"),
                                dcc.Dropdown(
                                    id='baud-dropdown',
                                    options=[
                                        {'label': '9600', 'value': 9600},
                                        {'label': '38400', 'value': 38400}
                                    ],
                                    value=9600
                                )
                            ], className="mb-3"),
                        ]),
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("Pump Address:"),
                                dbc.Input(id='pump-address-input', type='number', min=0, max=14, value=1)
                            ], className="mb-3"),
                        ]),
                        dbc.Row([
                            dbc.Col([
                                dbc.ButtonGroup([
                                    dbc.Button("Connect", id='connect-btn', color="success", className="me-2"),
                                    dbc.Button("Disconnect", id='disconnect-btn', color="danger")
                                ], className="d-flex justify-content-center")
                            ])
                        ])
                    ])
                ])
            ], md=6, className="mb-4"),

            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.H4([html.I(className="fas fa-cog", style={'marginRight': '10px'}), "Pump Configuration"],
                                className="text-center mb-0")
                    ]),
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("Valve Type:"),
                                dcc.Dropdown(
                                    id='valve-type-dropdown',
                                    options=[
                                        {'label': '3-Port Valve', 'value': '3-port'},
                                        {'label': '4-Port Valve', 'value': '4-port'},
                                        {'label': 'T-Valve', 'value': 't-valve'},
                                        {'label': '6-Port Distribution', 'value': '6-port'},
                                        {'label': '9-Port Distribution', 'value': '9-port'}
                                    ],
                                    value='9-port'
                                )
                            ], className="mb-3"),
                        ]),
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("Syringe Size:"),
                                dcc.Dropdown(
                                    id='syringe-size-dropdown',
                                    options=[
                                        {'label': '50 μL', 'value': 0.05},
                                        {'label': '100 μL', 'value': 0.1},
                                        {'label': '250 μL', 'value': 0.25},
                                        {'label': '500 μL', 'value': 0.5},
                                        {'label': '1.0 mL', 'value': 1.0},
                                        {'label': '2.5 mL', 'value': 2.5},
                                        {'label': '5.0 mL', 'value': 5.0},
                                        {'label': '10 mL', 'value': 10.0},
                                        {'label': '25 mL', 'value': 25.0},
                                        {'label': '50 mL', 'value': 50.0}
                                    ],
                                    value=25.0
                                )
                            ], className="mb-3"),
                        ]),
                        dbc.Row([
                            dbc.Col([
                                dbc.ButtonGroup([
                                    dbc.Button("Initialize Pump", id='init-pump-btn', color="warning",
                                               className="me-2"),
                                    dbc.Button("Query Status", id='query-status-btn', color="primary")
                                ], className="d-flex justify-content-center")
                            ])
                        ])
                    ])
                ])
            ], md=6, className="mb-4")
        ]),

        # Row 2 - System Information and Status
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.H4([html.I(className="fas fa-info-circle", style={'marginRight': '10px'}),
                                 "System Information"],
                                className="text-center mb-0")
                    ]),
                    dbc.CardBody([
                        html.Div(id='system-info-display')
                    ])
                ])
            ], md=6, className="mb-4"),

            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.H4([html.I(className="fas fa-exclamation-triangle", style={'marginRight': '10px'}),
                                 "Status & Errors"],
                                className="text-center mb-0")
                    ]),
                    dbc.CardBody([
                        html.Div(id='error-log-display')
                    ])
                ])
            ], md=6, className="mb-4")
        ])
    ], fluid=True)


def create_quick_actions_layout(controller):
    return html.Div([
        html.H2([html.I(className="fas fa-bolt", style={'marginRight': '10px'}), "Quick Actions"],
                className='section-title', style={'marginBottom': '2rem'}),

        # Emergency Controls
        html.Div([
            html.H3(
                [html.I(className="fas fa-exclamation-triangle", style={'marginRight': '8px'}), "Emergency Controls"],
                className='section-title'),
            html.Div([
                html.Button([
                    html.I(className="fas fa-stop", style={'marginRight': '8px'}),
                    "EMERGENCY STOP"
                ], id='emergency-stop-btn', className='control-button emergency-button',
                    style={'padding': '1rem 2rem', 'fontSize': '1.1rem'}),

                html.Button([
                    html.I(className="fas fa-pause", style={'marginRight': '8px'}),
                    "Pause Operation"
                ], id='pause-operation-btn', className='control-button warning'),

                html.Button([
                    html.I(className="fas fa-play", style={'marginRight': '8px'}),
                    "Resume Operation"
                ], id='resume-operation-btn', className='control-button success')
            ], className='button-group')
        ], className='card'),

        # Flow Control Section
        html.Div([
            html.Div([
                html.H3([html.I(className="fas fa-tint", style={'marginRight': '8px'}), "Flow Rate Presets"],
                        className='section-title'),
                html.P("Click to start continuous flow at preset rate:",
                       style={'marginBottom': '1rem', 'color': 'var(--text-secondary)'}),
                html.Div([
                    html.Div(f"{rate} mL/min",
                             id={'type': 'flow-preset', 'index': i},
                             className='quick-preset')
                    for i, rate in enumerate(controller.flow_presets)
                ], style={'marginBottom': '1.5rem'}),

                html.Div([
                    html.Label("Custom Flow Rate:", className='input-label'),
                    html.Div([
                        dcc.Input(id='custom-flow-input', type='number', value=1.0, min=0.01, max=50.0, step=0.01,
                                  className='form-input', style={'width': '120px'}),
                        html.Span("mL/min", style={'marginLeft': '8px', 'color': 'var(--text-secondary)'})
                    ], className='input-row', style={'marginBottom': '1rem'}),
                    html.Div([
                        html.Button(
                            [html.I(className="fas fa-arrow-up", style={'marginRight': '6px'}), "Start Aspirate"],
                            id='start-aspirate-btn', className='control-button success'),
                        html.Button(
                            [html.I(className="fas fa-arrow-down", style={'marginRight': '6px'}), "Start Dispense"],
                            id='start-dispense-btn', className='control-button info'),
                        html.Button([html.I(className="fas fa-stop", style={'marginRight': '6px'}), "Stop Flow"],
                                    id='stop-flow-btn', className='control-button danger')
                    ], className='button-group')
                ])
            ], className='card layout-col'),

            # Volume Presets
            html.Div([
                html.H3([html.I(className="fas fa-flask", style={'marginRight': '8px'}), "Volume Presets"],
                        className='section-title'),
                html.P("Quick volume operations (aspirate):",
                       style={'marginBottom': '1rem', 'color': 'var(--text-secondary)'}),
                html.Div([
                    html.Div(f"{vol} μL",
                             id={'type': 'volume-preset', 'index': i},
                             className='quick-preset')
                    for i, vol in enumerate(controller.volume_presets)
                ])
            ], className='card layout-col')
        ], className='layout-row'),

        # System Operations
        html.Div([
            html.H3([html.I(className="fas fa-tools", style={'marginRight': '8px'}), "System Operations"],
                    className='section-title'),
            html.Div([
                html.Button([
                    html.I(className="fas fa-fill-drip", style={'marginRight': '8px'}),
                    "Prime System"
                ], id='prime-system-btn', className='control-button info'),

                html.Button([
                    html.I(className="fas fa-sync-alt", style={'marginRight': '8px'}),
                    "Purge System"
                ], id='purge-system-btn', className='control-button warning'),

                html.Button([
                    html.I(className="fas fa-home", style={'marginRight': '8px'}),
                    "Home Position"
                ], id='home-position-btn', className='control-button'),

                html.Button([
                    html.I(className="fas fa-question-circle", style={'marginRight': '8px'}),
                    "Query Status"
                ], id='query-status-quick-btn', className='control-button')
            ], className='button-group')
        ], className='card')
    ], style={'margin': '1.5rem', 'maxWidth': '1400px', 'marginLeft': 'auto', 'marginRight': 'auto'})


def create_operation_log_layout():
    return html.Div([
        html.H2([html.I(className="fas fa-clipboard-list", style={'marginRight': '10px'}), "Operation Log"],
                className='section-title', style={'marginBottom': '2rem'}),

        html.Div([
            html.Div([
                html.Button([
                    html.I(className="fas fa-download", style={'marginRight': '8px'}),
                    "Export CSV"
                ], id='export-log-btn', className='control-button info'),

                html.Button([
                    html.I(className="fas fa-trash", style={'marginRight': '8px'}),
                    "Clear Log"
                ], id='clear-log-btn', className='control-button danger'),

                dcc.Dropdown(
                    id='log-filter-dropdown',
                    options=[
                        {'label': 'All Messages', 'value': 'all'},
                        {'label': 'Info Only', 'value': 'info'},
                        {'label': 'Warnings Only', 'value': 'warning'},
                        {'label': 'Errors Only', 'value': 'error'}
                    ],
                    value='all',
                    style={'width': '150px', 'marginLeft': '1rem'}
                )
            ], className='button-group', style={'marginBottom': '1.5rem'}),

            html.Div(id='operation-log-display', className='operation-log')
        ], className='card')
    ], style={'margin': '1.5rem', 'maxWidth': '1400px', 'marginLeft': 'auto', 'marginRight': 'auto'})
