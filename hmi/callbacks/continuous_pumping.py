"""
Callbacks for continuous pumping functionality
"""

from dash import Input, Output, State, callback_context, MATCH


def register_continuous_pumping_callbacks(app, controller):
    """Register all continuous pumping related callbacks"""

    # Inlet valve selection for continuous pumping
    @app.callback(
        Output('continuous-pump-status', 'children'),
        Output('continuous-pump-status', 'style'),
        [Input({'type': 'continuous-pump-inlet', 'index': MATCH}, 'n_clicks')],
        prevent_initial_call=True
    )
    def select_continuous_pump_inlet(n_clicks):
        """Handle inlet valve selection for continuous pumping"""
        ctx = callback_context
        if not ctx.triggered:
            return "Continuous Pumping: Idle", {
                'padding': '12px', 'backgroundColor': '#f1f5f9',
                'borderRadius': '8px', 'textAlign': 'center', 'fontWeight': '600'
            }

        # Extract valve index from button id
        button_id = ctx.triggered[0]['prop_id'].split('.')[0]
        import json
        valve_data = json.loads(button_id)
        valve_index = valve_data['index']

        controller.continuous_pumping_inlet = f"A{valve_index}"

        return f"Inlet selected: A{valve_index}", {
            'padding': '12px', 'backgroundColor': '#dbeafe',
            'borderRadius': '8px', 'textAlign': 'center', 'fontWeight': '600', 'color': '#1e40af'
        }

    # Outlet valve selection for continuous pumping
    @app.callback(
        Output('continuous-pump-status', 'children', allow_duplicate=True),
        Output('continuous-pump-status', 'style', allow_duplicate=True),
        [Input('continuous-pump-outlet-waste', 'n_clicks'),
         Input('continuous-pump-outlet-collect', 'n_clicks')],
        prevent_initial_call=True
    )
    def select_continuous_pump_outlet(waste_clicks, collect_clicks):
        """Handle outlet valve selection for continuous pumping"""
        ctx = callback_context
        if not ctx.triggered:
            return "Continuous Pumping: Idle", {
                'padding': '12px', 'backgroundColor': '#f1f5f9',
                'borderRadius': '8px', 'textAlign': 'center', 'fontWeight': '600'
            }

        button_id = ctx.triggered[0]['prop_id'].split('.')[0]

        if button_id == 'continuous-pump-outlet-waste':
            controller.continuous_pumping_outlet = 'Waste'
            return "Outlet selected: Waste", {
                'padding': '12px', 'backgroundColor': '#dbeafe',
                'borderRadius': '8px', 'textAlign': 'center', 'fontWeight': '600', 'color': '#1e40af'
            }
        elif button_id == 'continuous-pump-outlet-collect':
            controller.continuous_pumping_outlet = 'Collect'
            return "Outlet selected: Collect", {
                'padding': '12px', 'backgroundColor': '#dbeafe',
                'borderRadius': '8px', 'textAlign': 'center', 'fontWeight': '600', 'color': '#1e40af'
            }

        return "Continuous Pumping: Idle", {
            'padding': '12px', 'backgroundColor': '#f1f5f9',
            'borderRadius': '8px', 'textAlign': 'center', 'fontWeight': '600'
        }

    # Start/Stop continuous pumping
    @app.callback(
        Output('continuous-pump-status', 'children', allow_duplicate=True),
        Output('continuous-pump-status', 'style', allow_duplicate=True),
        [Input('continuous-pump-start', 'n_clicks'),
         Input('continuous-pump-stop', 'n_clicks')],
        [State('continuous-pump-flow-rate', 'value')],
        prevent_initial_call=True
    )
    def control_continuous_pumping(start_clicks, stop_clicks, flow_rate):
        """Handle start/stop for continuous pumping"""
        ctx = callback_context

        if not ctx.triggered:
            return "Continuous Pumping: Idle", {
                'padding': '12px', 'backgroundColor': '#f1f5f9',
                'borderRadius': '8px', 'textAlign': 'center', 'fontWeight': '600'
            }

        button_id = ctx.triggered[0]['prop_id'].split('.')[0]

        if button_id == 'continuous-pump-start' and start_clicks and flow_rate:
            # Start continuous pumping
            inlet = controller.continuous_pumping_inlet
            outlet = controller.continuous_pumping_outlet

            controller.start_continuous_pumping(flow_rate, inlet, outlet)

            return f"ACTIVE: {inlet} → {outlet} @ {flow_rate} mL/min", {
                'padding': '12px', 'backgroundColor': '#dcfce7',
                'borderRadius': '8px', 'textAlign': 'center', 'fontWeight': '600', 'color': '#166534'
            }

        elif button_id == 'continuous-pump-stop' and stop_clicks:
            # Stop continuous pumping
            controller.stop_continuous_pumping()

            return "Continuous Pumping: Stopped", {
                'padding': '12px', 'backgroundColor': '#fee2e2',
                'borderRadius': '8px', 'textAlign': 'center', 'fontWeight': '600', 'color': '#991b1b'
            }

        return "Continuous Pumping: Idle", {
            'padding': '12px', 'backgroundColor': '#f1f5f9',
            'borderRadius': '8px', 'textAlign': 'center', 'fontWeight': '600'
        }
