    def get_vehicle_state(self) -> VehicleState:
        if self._vehicle_charge_state is None:
            return VehicleState(connected=False, charge_level=None)
        else:
            return VehicleState(connected=True, charge_level=self._vehicle_charge_state.battery_level)

# When constructing the webservice after creating `state`:
webservice = LadningService(host="0.0.0.0", port=args.webservice_port,
                            electricity_price_getter=state.get_hourly_prices,
                            charging_plan_getter=state.get_charging_plan,
                            charging_request_setter=state.on_charging_request_sync,
                            vehicle_state_getter=state.get_vehicle_state)