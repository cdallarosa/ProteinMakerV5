"""
Manual control layout for XLP6000 application
Includes continuous pumping functionality
"""

from dash import dcc, html


def create_manual_control_layout(controller):
    """Create manual control tab for pump and valve operations"""
    return html.Div([
        html.H2([html.I(className="fas fa-sliders-h", style={'marginRight': '10px'}), "Manual Control"],
                className='page-title'),

        # Connection Status Card
        html.Div([
            html.Div([
                html.H3("System Status", className='section-title'),
                html.Div([
                    html.Div([
                        html.Span("Connection: ", style={'fontWeight': '600'}),
                        html.Span(
                            "Connected" if controller.is_connected else "Disconnected",
                            style={'color': '#16a34a' if controller.is_connected else '#dc2626'}
                        )
                    ], style={'marginBottom': '10px'}),
                    html.Div([
                        html.Span("Current Position: ", style={'fontWeight': '600'}),
                        html.Span(f"{controller.current_position} steps", id='manual-current-position')
                    ], style={'marginBottom': '10px'}),
                    html.Div([
                        html.Span("Valve Position: ", style={'fontWeight': '600'}),
                        html.Span(controller.valve_position, id='manual-valve-position')
                    ])
                ], style={'padding': '15px', 'backgroundColor': '#f8fafc', 'borderRadius': '8px'})
            ])
        ], className='card', style={'marginBottom': '20px'}),

        # Manual Pump Control Card
        html.Div([
            html.H3([html.I(className="fas fa-syringe", style={'marginRight': '8px'}), "Pump Control"],
                    className='section-title'),

            # NEW: Continuous Pumping Control
            html.Div([
                html.H4([html.I(className="fas fa-sync-alt", style={'marginRight': '8px'}), "Continuous Pumping"],
                        style={'marginBottom': '15px', 'fontSize': '1.1rem', 'color': '#2563eb'}),
                html.P("Automatically cycles between aspirate and dispense",
                       style={'color': '#64748b', 'fontSize': '0.9rem', 'marginBottom': '15px'}),

                # Flow Rate Input
                html.Div([
                    html.Label("Flow Rate (mL/min):", className='input-label'),
                    dcc.Input(
                        id='continuous-pump-flow-rate',
                        type='number',
                        min=0.01,
                        max=50.0,
                        step=0.01,
                        value=1.0,
                        className='form-input',
                        style={'width': '150px'}
                    )
                ], style={'marginBottom': '15px'}),

                # Inlet Valve Selection
                html.Div([
                    html.Label("Inlet Valve:", className='input-label'),
                    html.Div([
                        html.Button(
                            f"A{i}",
                            id={'type': 'continuous-pump-inlet', 'index': i},
                            className='valve-button' + (' valve-button-active' if f'A{i}' == controller.continuous_pumping_inlet else ''),
                            style={'width': '50px', 'marginRight': '5px', 'marginBottom': '5px'}
                        )
                        for i in range(1, 10)
                    ])
                ], style={'marginBottom': '15px'}),

                # Outlet Valve Selection
                html.Div([
                    html.Label("Outlet Valve:", className='input-label'),
                    html.Div([
                        html.Button(
                            "Waste",
                            id='continuous-pump-outlet-waste',
                            className='valve-button' + (' valve-button-active' if controller.continuous_pumping_outlet == 'Waste' else ''),
                            style={'width': '80px', 'marginRight': '10px'}
                        ),
                        html.Button(
                            "Collect",
                            id='continuous-pump-outlet-collect',
                            className='valve-button' + (' valve-button-active' if controller.continuous_pumping_outlet == 'Collect' else ''),
                            style={'width': '80px'}
                        )
                    ])
                ], style={'marginBottom': '20px'}),

                # Control Buttons
                html.Div([
                    html.Button(
                        [html.I(className="fas fa-play", style={'marginRight': '6px'}), "Start Pumping"],
                        id='continuous-pump-start',
                        className='control-button success',
                        style={'marginRight': '10px'}
                    ),
                    html.Button(
                        [html.I(className="fas fa-stop", style={'marginRight': '6px'}), "Stop Pumping"],
                        id='continuous-pump-stop',
                        className='control-button danger'
                    )
                ], className='button-group', style={'marginBottom': '15px'}),

                # Status Display
                html.Div(
                    id='continuous-pump-status',
                    children="Continuous Pumping: Idle",
                    style={
                        'padding': '12px',
                        'backgroundColor': '#f1f5f9',
                        'borderRadius': '8px',
                        'textAlign': 'center',
                        'fontWeight': '600'
                    }
                )
            ], style={'padding': '20px', 'backgroundColor': '#eff6ff', 'borderRadius': '8px', 'marginBottom': '20px', 'border': '2px solid #3b82f6'}),

            # Continuous Flow Control (Single Direction)
            html.Div([
                html.H4("Continuous Flow Control (Single Direction)", style={'marginBottom': '15px', 'fontSize': '1.1rem'}),

                # Flow Rate Input
                html.Div([
                    html.Label("Flow Rate (mL/min):", className='input-label'),
                    html.Div([
                        dcc.Input(
                            id='manual-flow-rate',
                            type='number',
                            min=0.01,
                            max=50.0,
                            step=0.01,
                            value=1.0,
                            className='form-input',
                            style={'width': '150px', 'marginRight': '15px'}
                        ),
                        html.Span(
                            id='manual-pump-speed',
                            children="0 steps/sec",
                            style={'color': 'var(--text-secondary)', 'fontSize': '0.9rem'}
                        )
                    ], style={'display': 'flex', 'alignItems': 'center'})
                ], style={'marginBottom': '20px'}),

                # Flow Direction
                html.Div([
                    html.Label("Flow Direction:", className='input-label'),
                    dcc.RadioItems(
                        id='manual-flow-direction',
                        options=[
                            {'label': ' Aspirate (Draw In)', 'value': 'aspirate'},
                            {'label': ' Dispense (Push Out)', 'value': 'dispense'}
                        ],
                        value='aspirate',
                        labelStyle={'display': 'inline-block', 'marginRight': '20px'}
                    )
                ], style={'marginBottom': '20px'}),

                # Control Buttons
                html.Div([
                    html.Button(
                        [html.I(className="fas fa-play", style={'marginRight': '6px'}), "Start Flow"],
                        id='manual-start-flow',
                        className='control-button success',
                        style={'marginRight': '10px'}
                    ),
                    html.Button(
                        [html.I(className="fas fa-stop", style={'marginRight': '6px'}), "Stop Flow"],
                        id='manual-stop-flow',
                        className='control-button danger',
                        style={'marginRight': '10px'}
                    ),
                    html.Button(
                        [html.I(className="fas fa-pause", style={'marginRight': '6px'}), "Pause"],
                        id='manual-pause-flow',
                        className='control-button warning'
                    )
                ], className='button-group', style={'marginBottom': '20px'}),

                # Flow Status
                html.Div(
                    id='manual-flow-status',
                    children="Flow Status: Idle",
                    style={
                        'padding': '12px',
                        'backgroundColor': '#f1f5f9',
                        'borderRadius': '8px',
                        'textAlign': 'center',
                        'fontWeight': '600'
                    }
                )
            ], style={'padding': '20px', 'backgroundColor': '#fafbfc', 'borderRadius': '8px', 'marginBottom': '20px'}),

            # Manual Volume Control
            html.Div([
                html.H4("Volume Control", style={'marginBottom': '15px', 'fontSize': '1.1rem'}),

                html.Div([
                    html.Div([
                        html.Label("Volume (μL):", className='input-label'),
                        dcc.Input(
                            id='manual-volume',
                            type='number',
                            min=1,
                            max=25000,
                            step=1,
                            value=100,
                            className='form-input',
                            style={'width': '150px'}
                        )
                    ], style={'marginRight': '30px'}),

                    html.Div([
                        html.Label("Speed (μL/sec):", className='input-label'),
                        dcc.Input(
                            id='manual-speed',
                            type='number',
                            min=1,
                            max=5000,
                            step=10,
                            value=100,
                            className='form-input',
                            style={'width': '150px'}
                        )
                    ])
                ], style={'display': 'flex', 'marginBottom': '20px'}),

                html.Div([
                    html.Button(
                        [html.I(className="fas fa-arrow-up", style={'marginRight': '6px'}), "Aspirate"],
                        id='manual-aspirate',
                        className='control-button primary',
                        style={'marginRight': '10px'}
                    ),
                    html.Button(
                        [html.I(className="fas fa-arrow-down", style={'marginRight': '6px'}), "Dispense"],
                        id='manual-dispense',
                        className='control-button primary'
                    )
                ], className='button-group'),

                # Volume operation status
                html.Div(id='manual-volume-status', style={'marginTop': '10px', 'textAlign': 'center'})
            ], style={'padding': '20px', 'backgroundColor': '#fafbfc', 'borderRadius': '8px'})
        ], className='card', style={'marginBottom': '20px'}),

        # Valve Control Card
        html.Div([
            html.H3([html.I(className="fas fa-exchange-alt", style={'marginRight': '8px'}), "Valve Control"],
                    className='section-title'),

            # Inlet Valve Selection
            html.Div([
                html.H4("Inlet Valve Selection", style={'marginBottom': '15px', 'fontSize': '1.1rem'}),
                html.Div([
                    html.Button(
                        f"A{i}",
                        id={'type': 'manual-inlet-valve', 'index': i},
                        className='valve-button' + (' valve-button-active' if f'A{i}' == controller.selected_inlet_valve else ''),
                        style={'width': '60px', 'marginRight': '10px', 'marginBottom': '10px'}
                    )
                    for i in range(1, 10)
                ]),
                html.Div(id='manual-inlet-status', style={'marginTop': '10px', 'textAlign': 'center'})
            ], style={'marginBottom': '25px'}),

            # Outlet Valve Selection
            html.Div([
                html.H4("Outlet Valve Selection", style={'marginBottom': '15px', 'fontSize': '1.1rem'}),
                html.Div([
                    html.Button(
                        "Waste",
                        id='manual-outlet-waste',
                        className='valve-button' + (' valve-button-active' if controller.selected_outlet_valve == 'Waste' else ''),
                        style={'width': '100px', 'marginRight': '10px'}
                    ),
                    html.Button(
                        "Collect",
                        id='manual-outlet-collect',
                        className='valve-button' + (' valve-button-active' if controller.selected_outlet_valve == 'Collect' else ''),
                        style={'width': '100px'}
                    )
                ]),
                html.Div(id='manual-outlet-status', style={'marginTop': '10px', 'textAlign': 'center'})
            ], style={'marginBottom': '25px'}),

            # System Operations
            html.Div([
                html.H4("System Operations", style={'marginBottom': '15px', 'fontSize': '1.1rem'}),
                html.Div([
                    html.Button(
                        [html.I(className="fas fa-fill-drip", style={'marginRight': '6px'}), "Prime System"],
                        id='manual-prime',
                        className='control-button secondary',
                        style={'marginRight': '10px'}
                    ),
                    html.Button(
                        [html.I(className="fas fa-tint", style={'marginRight': '6px'}), "Wash Valve"],
                        id='manual-wash',
                        className='control-button secondary',
                        style={'marginRight': '10px'}
                    ),
                    html.Button(
                        [html.I(className="fas fa-home", style={'marginRight': '6px'}), "Home"],
                        id='manual-home',
                        className='control-button secondary'
                    )
                ]),
                html.Div(id='manual-system-status', style={'marginTop': '10px', 'textAlign': 'center'})
            ])
        ], className='card'),

        # Update interval for real-time status
        dcc.Interval(id='manual-update-interval', interval=1000, n_intervals=0)

    ], style={'margin': '1.5rem', 'maxWidth': '1200px', 'marginLeft': 'auto', 'marginRight': 'auto'})
