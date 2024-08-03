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
    start_time = dt.datetime.now()
    hourly_prices: List[HourlyPrice] = [
        HourlyPrice(start=start_time + dt.timedelta(hours=i), price_kwh_dkk=1.0, co2_emission=None)
        for i in range(24)
    ]
    target_battery_level = 100

    charging_plan = create_charging_plan(vehicle_50_percent, hourly_prices, target_battery_level)
    assert charging_plan is not None
