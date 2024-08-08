import teslapy

from ladning.constants import MILES_TO_KILOMETERS
from ladning.logging import log
from ladning.types import VehicleChargeState


def get_vehicle_charge_state(allow_wakeup: bool = False) -> VehicleChargeState:
    with teslapy.Tesla('mathias.stokholm@gmail.com') as tesla:
        vehicles = tesla.vehicle_list()
        if len(vehicles) != 1:
            raise RuntimeError(f"Expected a single vehicle, got {len(vehicles)}")
        vehicle = vehicles[0]
        if vehicle["state"] == "asleep":
            if allow_wakeup:
                log.warning(f"Waking up car to get battery level")
                vehicle.sync_wake_up()
            else:
                raise RuntimeError("Car is asleep and wakeup wasn't allowed")
        charge_state = vehicle['charge_state']
        battery_level = charge_state['battery_level']
        range_km = charge_state['battery_range'] * MILES_TO_KILOMETERS
        minutes_to_full_charge = charge_state['minutes_to_full_charge']
        return VehicleChargeState(battery_level, range_km, minutes_to_full_charge)
