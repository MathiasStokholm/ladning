from typing import List

import pytest
import datetime as dt

from ladning.charging_plan import create_charging_plan
from ladning.types import VehicleChargeState, HourlyPrice


@pytest.fixture()
def vehicle_50_percent() -> VehicleChargeState:
    return VehicleChargeState(battery_level=50, range_km=200, minutes_to_full_charge=0)


def test_create_charging_plan_no_hours(vehicle_50_percent: VehicleChargeState) -> None:
    with pytest.raises(RuntimeError):
        create_charging_plan(vehicle_charge_state=vehicle_50_percent, hourly_prices=[], target_battery_level=100)


def test_create_charging_plan(vehicle_50_percent: VehicleChargeState) -> None:
    start_time = dt.datetime(2024, 8, 3, 0, 0, 0, 0)
    hourly_prices: List[HourlyPrice] = [
        HourlyPrice(start=start_time + dt.timedelta(hours=i), price_kwh_dkk=1.0, co2_emission=None)
        for i in range(24)
    ]
    target_battery_level = 100

    # Make entries 13-16 the optimal time to charge, and check that 13 gets picked as the start time even though
    # hours 14 and 15 are cheaper
    hourly_prices[13].price_kwh_dkk = 0.5
    hourly_prices[14].price_kwh_dkk = 0.3
    hourly_prices[15].price_kwh_dkk = 0.1
    charging_plan = create_charging_plan(vehicle_50_percent, hourly_prices, target_battery_level)
    assert charging_plan is not None
    assert charging_plan.start_time == hourly_prices[13].start
