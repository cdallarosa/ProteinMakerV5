"""
Sequence builder layout for XLP6000 application
"""

from dash import dcc, html


def create_sequence_builder_layout(controller):
    return html.Div([
        html.Div([
            # Left Panel - Step Library and Templates
            html.Div([
                # Method Templates
                html.Div([
                    html.H3([html.I(className="fas fa-book", style={'marginRight': '8px'}), "Method Templates"],
                            className='section-title'),
                    dcc.Dropdown(
                        id='template-dropdown',
                        options=[{'label': name, 'value': name} for name in controller.method_templates.keys()],
                        placeholder="Select a template...",
                        style={'marginBottom': '10px'}
                    ),
                    html.Button("Load Template", id='load-template-btn', className='control-button',
                                style={'width': '100%', 'marginBottom': '20px'})
                ], className='card', style={'marginBottom': '20px'}),

                # Step Library
                html.Div([
                    html.H3([html.I(className="fas fa-cube", style={'marginRight': '8px'}), "Step Library"],
                            className='section-title'),
                    html.P("Click to add steps to your sequence:",
                           style={'marginBottom': '1rem', 'color': 'var(--text-secondary)', 'fontSize': '0.9rem'}),
                    html.Div([
                        # Clickable step buttons
                        html.Div([
                            html.Button([
                                html.Div("🔄", style={'fontSize': '1.2rem', 'marginBottom': '5px'}),
                                html.Div("Equilibrate", style={'fontSize': '0.8rem', 'fontWeight': '600'})
                            ], className='step-card', id='add-equilibrate-btn',
                                style={'cursor': 'pointer', 'border': 'none', 'background': 'white'}),

                            html.Button([
                                html.Div("💉", style={'fontSize': '1.2rem', 'marginBottom': '5px'}),
                                html.Div("Load Sample", style={'fontSize': '0.8rem', 'fontWeight': '600'})
                            ], className='step-card', id='add-load-btn',
                                style={'cursor': 'pointer', 'border': 'none', 'background': 'white'}),

                            html.Button([
                                html.Div("🚿", style={'fontSize': '1.2rem', 'marginBottom': '5px'}),
                                html.Div("Wash", style={'fontSize': '0.8rem', 'fontWeight': '600'})
                            ], className='step-card', id='add-wash-btn',
                                style={'cursor': 'pointer', 'border': 'none', 'background': 'white'}),

                            html.Button([
                                html.Div("🧪", style={'fontSize': '1.2rem', 'marginBottom': '5px'}),
                                html.Div("Elute", style={'fontSize': '0.8rem', 'fontWeight': '600'})
                            ], className='step-card', id='add-elute-btn',
                                style={'cursor': 'pointer', 'border': 'none', 'background': 'white'}),

                            html.Button([
                                html.Div("♻️", style={'fontSize': '1.2rem', 'marginBottom': '5px'}),
                                html.Div("Regenerate", style={'fontSize': '0.8rem', 'fontWeight': '600'})
                            ], className='step-card', id='add-regenerate-btn',
                                style={'cursor': 'pointer', 'border': 'none', 'background': 'white'}),

                            html.Button([
                                html.Div("⏸️", style={'fontSize': '1.2rem', 'marginBottom': '5px'}),
                                html.Div("Hold", style={'fontSize': '0.8rem', 'fontWeight': '600'})
                            ], className='step-card', id='add-hold-btn',
                                style={'cursor': 'pointer', 'border': 'none', 'background': 'white'}),

                            html.Button([
                                html.Div("📊", style={'fontSize': '1.2rem', 'marginBottom': '5px'}),
                                html.Div("Gradient", style={'fontSize': '0.8rem', 'fontWeight': '600'})
                            ], className='step-card', id='add-gradient-btn',
                                style={'cursor': 'pointer', 'border': 'none', 'background': 'white'}),
                        ], style={'display': 'grid', 'gridTemplateColumns': 'repeat(2, 1fr)', 'gap': '10px'})
                    ])
                ], className='card'),
            ], style={'width': '25%', 'marginRight': '20px'}),

            # Center Panel - Sequence Builder
            html.Div([
                html.H3([html.I(className="fas fa-list-ol", style={'marginRight': '8px'}), "Current Sequence"],
                        className='section-title'),

                # Sequence steps container (droppable area)
                html.Div(id='sequence-container', className='sequence-dropzone', children=[
                    html.Div("Drop steps here to build your sequence",
                             style={'padding': '40px', 'textAlign': 'center', 'color': '#94a3b8',
                                    'border': '2px dashed #cbd5e1', 'borderRadius': '8px'})
                ], style={'minHeight': '400px', 'padding': '20px', 'background': '#f8fafc',
                          'borderRadius': '8px', 'marginBottom': '20px'}),

                # Sequence controls
                html.Div([
                    html.Button("Clear All", id='clear-sequence-btn', className='control-button warning',
                                style={'marginRight': '10px'}),
                    html.Button("Save Sequence", id='save-sequence-btn', className='control-button',
                                style={'marginRight': '10px'}),
                    html.Button("Run Sequence", id='run-sequence-btn', className='control-button success'),
                ], style={'display': 'flex', 'justifyContent': 'center'})
            ], className='card', style={'flex': '1', 'marginRight': '20px'}),

            # Right Panel - Step Parameters
            html.Div([
                html.H3([html.I(className="fas fa-sliders-h", style={'marginRight': '8px'}), "Step Parameters"],
                        className='section-title'),
                html.Div(id='step-parameters', children=[
                    html.P("Select a step to edit parameters",
                           style={'textAlign': 'center', 'color': '#94a3b8', 'padding': '20px'})
                ])
            ], className='card', style={'width': '30%'})
        ], style={'display': 'flex', 'height': 'calc(100vh - 300px)'}),

        # Hidden stores for sequence data - start with configuration step by default
        dcc.Store(id='sequence-store', data=[{"type": "configuration", "name": "Method Configuration", "config": controller.method_config.copy(), "id": 0}]),
        dcc.Store(id='selected-step-index', data=None),
    ])
