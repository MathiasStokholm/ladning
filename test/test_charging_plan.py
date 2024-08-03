from typing import List

from ladning.charging_plan import create_charging_plan
from ladning.types import VehicleChargeState, HourlyPrice


def test_create_charging_plan() -> None:
    vehicle_charge_state = VehicleChargeState(battery_level=50, range_km=200, minutes_to_full_charge=0)
    hourly_prices: List[HourlyPrice] = []
    target_battery_level = 100

    charging_plan = create_charging_plan(vehicle_charge_state, hourly_prices, target_battery_level)
    assert charging_plan is not None
