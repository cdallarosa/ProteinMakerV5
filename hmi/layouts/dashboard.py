"""
Dashboard layout for XLP6000 application
"""

from dash import dcc, html


def create_dashboard_layout():
    return html.Div([
        # UNICORN-Style Run Data Table (Top Section)
        html.Div([
            html.H3("Run Data", style={
                'color': '#2d3748', 'fontSize': '1.1rem', 'fontWeight': '600',
                'marginBottom': '10px', 'borderBottom': '2px solid #e2e8f0', 'paddingBottom': '5px'
            }),

            # Status Grid - UNICORN Style
            html.Table([
                html.Thead([
                    html.Tr([
                        html.Th("Process Volume", style={'textAlign': 'center', 'padding': '8px', 'fontSize': '0.9rem',
                                                         'fontWeight': '600'}),
                        html.Th("Block Volume", style={'textAlign': 'center', 'padding': '8px', 'fontSize': '0.9rem',
                                                       'fontWeight': '600'}),
                        html.Th("Time", style={'textAlign': 'center', 'padding': '8px', 'fontSize': '0.9rem',
                                               'fontWeight': '600'}),
                        html.Th("Sample Flow", style={'textAlign': 'center', 'padding': '8px', 'fontSize': '0.9rem',
                                                      'fontWeight': '600'}),
                        html.Th("Sample Pressure", style={'textAlign': 'center', 'padding': '8px', 'fontSize': '0.9rem',
                                                          'fontWeight': '600'}),
                        html.Th("UV 280", style={'textAlign': 'center', 'padding': '8px', 'fontSize': '0.9rem',
                                                 'fontWeight': '600'}),
                    ])
                ]),
                html.Tbody([
                    html.Tr([
                        html.Td(id='process-volume-display', children="0.0 ml",
                                style={'textAlign': 'center', 'padding': '8px', 'fontSize': '1rem',
                                       'fontWeight': '700'}),
                        html.Td(id='block-volume-display', children="0.0 ml",
                                style={'textAlign': 'center', 'padding': '8px', 'fontSize': '1rem',
                                       'fontWeight': '700'}),
                        html.Td(id='time-display', children="0.0 min",
                                style={'textAlign': 'center', 'padding': '8px', 'fontSize': '1rem',
                                       'fontWeight': '700'}),
                        html.Td(id='sample-flow-display', children="0.0 ml/min",
                                style={'textAlign': 'center', 'padding': '8px', 'fontSize': '1rem',
                                       'fontWeight': '700'}),
                        html.Td(id='sample-pressure-display', children="0.0 MPa",
                                style={'textAlign': 'center', 'padding': '8px', 'fontSize': '1rem',
                                       'fontWeight': '700'}),
                        html.Td(id='uv-280-display', children="0 mAU",
                                style={'textAlign': 'center', 'padding': '8px', 'fontSize': '1rem',
                                       'fontWeight': '700'}),
                    ])
                ])
            ], style={
                'width': '100%', 'borderCollapse': 'collapse',
                'border': '1px solid #e2e8f0', 'backgroundColor': 'white'
            }),

        ], style={
            'backgroundColor': '#f7fafc', 'padding': '15px', 'borderRadius': '8px',
            'border': '1px solid #e2e8f0', 'marginBottom': '20px'
        }),

        # Chromatogram Section (Middle)
        html.Div([
            html.Div([
                html.H3("Chromatogram", style={
                    'color': '#2d3748', 'fontSize': '1.1rem', 'fontWeight': '600',
                    'marginBottom': '10px', 'borderBottom': '2px solid #e2e8f0', 'paddingBottom': '5px',
                    'display': 'inline-block', 'marginRight': '20px'
                }),
                html.Div([
                    html.Label("Show: ", style={'fontWeight': '600', 'marginRight': '10px'}),
                    dcc.Checklist(
                        id='chromatogram-variables',
                        options=[
                            {'label': 'UV 280', 'value': 'uv280'},
                            {'label': 'Conductivity', 'value': 'cond'},
                            {'label': 'Pressure', 'value': 'pressure'},
                            {'label': 'Flow Rate', 'value': 'flow'}
                        ],
                        value=['uv280', 'cond'],  # Default selections
                        inline=True,
                        style={'display': 'inline-block'}
                    )
                ], style={'display': 'inline-block', 'verticalAlign': 'bottom', 'marginBottom': '10px'})
            ], style={'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'flex-end'}),

            dcc.Graph(
                id='realtime-chromatogram',
                style={'height': '350px', 'backgroundColor': 'white'}
            )
        ], style={
            'backgroundColor': '#f7fafc', 'padding': '15px', 'borderRadius': '8px',
            'border': '1px solid #e2e8f0', 'marginBottom': '20px'
        }),

        # Process Picture Section (Bottom)
        html.Div([
            html.H3("Process Picture", style={
                'color': '#2d3748', 'fontSize': '1.1rem', 'fontWeight': '600',
                'marginBottom': '15px', 'borderBottom': '2px solid #e2e8f0', 'paddingBottom': '5px'
            }),

            # Interactive P&ID Diagram
            html.Div(id='pid-diagram', style={
                'padding': '20px', 'minHeight': '300px', 'backgroundColor': 'white',
                'border': '1px solid #e2e8f0', 'borderRadius': '8px'
            }),

        ], style={
            'backgroundColor': 'white', 'padding': '15px', 'borderRadius': '8px',
            'border': '1px solid #e2e8f0'
        }),

    ], style={'margin': '15px'})
