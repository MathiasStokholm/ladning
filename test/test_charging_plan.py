from typing import List

import pytest
import datetime as dt

from ladning.charging_plan import create_charging_plan, argmin, sum_n_sequential
from ladning.types import VehicleChargeState, HourlyPrice, ChargingRequest


@pytest.fixture()
def vehicle_50_percent() -> VehicleChargeState:
    return VehicleChargeState(battery_level=50, range_km=200, minutes_to_full_charge=0)


@pytest.fixture()
def charge_to_full_request() -> ChargingRequest:
    return ChargingRequest(battery_target=100, ready_by=None)


def test_argmin() -> None:
    vals = [i for i in range(10)]
    for i in range(10):
        vals[i] = -i
        assert argmin(vals) == i


def test_sum_n_sequential() -> None:
    def sum_0_to_n(_n: int) -> int:
        # Use triangular number formula to get sum of numbers from 0 to n
        return _n * (_n + 1) // 2

    num_values = 20
    vals = [i for i in range(num_values)]
    for n in range(1, 10):
        results = sum_n_sequential(vals, n)
        assert len(results) == num_values - n
        for i, result in enumerate(results):
            expected_val = sum_0_to_n(i - 1 + n) - sum_0_to_n(i - 1)
            assert result == expected_val


def test_create_charging_plan_no_hours(vehicle_50_percent: VehicleChargeState,
                                       charge_to_full_request: ChargingRequest) -> None:
    with pytest.raises(RuntimeError):
        create_charging_plan(vehicle_charge_state=vehicle_50_percent, hourly_prices=[],
                             charging_request=charge_to_full_request)


def test_create_charging_plan(vehicle_50_percent: VehicleChargeState, charge_to_full_request: ChargingRequest) -> None:
    start_time = dt.datetime(2024, 8, 3, 0, 0, 0, 0)
    hourly_prices: List[HourlyPrice] = [
        HourlyPrice(start=start_time + dt.timedelta(hours=i), price_kwh_dkk=1.0, co2_emission=None)
        for i in range(24)
    ]

    # Make entries 13-16 the optimal time to charge, and check that 13 gets picked as the start time even though
    # hours 14 and 15 are cheaper
    hourly_prices[13].price_kwh_dkk = 0.5
    hourly_prices[14].price_kwh_dkk = 0.3
    hourly_prices[15].price_kwh_dkk = 0.1
    result = create_charging_plan(vehicle_50_percent, hourly_prices, charge_to_full_request)
    assert result.success
    assert result.plan is not None
    assert result.plan.start_time == hourly_prices[13].start
