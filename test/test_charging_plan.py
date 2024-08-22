from typing import List

import pytest
import datetime as dt

from ladning.charging_plan import create_charging_plan, argmin, convolve_valid, hours_as_signal
from ladning.constants import BATTERY_CAPACITY_KWH, CHARGING_KW_MAX, CHARGING_KW_END
from ladning.types import VehicleChargeState, HourlyPrice, ChargingRequest


@pytest.fixture()
def vehicle_50_percent() -> VehicleChargeState:
    return VehicleChargeState(battery_level=50, range_km=200, minutes_to_full_charge=0)


@pytest.fixture()
def vehicle_90_percent() -> VehicleChargeState:
    return VehicleChargeState(battery_level=90, range_km=350, minutes_to_full_charge=0)


def vehicle_charge_state_required_for_charging_duration_to_full(hours_of_charging: float)\
        -> VehicleChargeState:
    """
    This is essentially the inverse of calculate_hours_required_to_charge()
    """
    target_state = 100
    hours_required_from_95_percent = ((100 - 95) / 100.0) * BATTERY_CAPACITY_KWH / CHARGING_KW_END

    if hours_of_charging < hours_required_from_95_percent:
        # Charging between 95 and 100%
        battery_state = int(target_state - hours_of_charging * CHARGING_KW_END / BATTERY_CAPACITY_KWH * 100.0)
    else:
        # Charging between <95% and 100%
        battery_state = 95
        additional_hours = hours_of_charging - hours_required_from_95_percent
        battery_state -= int(additional_hours * CHARGING_KW_MAX / BATTERY_CAPACITY_KWH * 100.0)
    return VehicleChargeState(battery_state, 350, 0)


def test_argmin() -> None:
    vals = [i for i in range(10)]
    for i in range(10):
        vals[i] = -i
        assert argmin(vals) == i


def test_convolve_valid() -> None:
    def sum_0_to_n(_n: int) -> int:
        # Use triangular number formula to get sum of numbers from 0 to n
        return _n * (_n + 1) // 2

    num_values = 20
    vals = [i for i in range(num_values)]
    for n in range(1, 10):
        results = convolve_valid(vals, [1.0] * n)
        assert len(results) == num_values - n + 1
        for i, result in enumerate(results):
            expected_val = sum_0_to_n(i - 1 + n) - sum_0_to_n(i - 1)
            assert result == expected_val


def test_convolve_valid_basic():
    signal1 = [1.0, 2.0, 3.0, 4.0]
    signal2 = [0.5, 1.0, 0.5]
    expected = [4.0, 6.0]
    assert convolve_valid(signal1, signal2) == expected


def test_convolve_valid_equal_length():
    signal1 = [1.0, 2.0, 3.0]
    signal2 = [1.0, 2.0, 3.0]
    expected = [14.0]
    assert convolve_valid(signal1, signal2) == expected


def test_convolve_valid_signal2_longer():
    signal1 = [1.0, 2.0]
    signal2 = [1.0, 2.0, 3.0]
    expected = []  # No valid portion
    assert convolve_valid(signal1, signal2) == expected


def test_convolve_valid_empty_signal1():
    signal1 = []
    signal2 = [1.0, 2.0, 3.0]
    expected = []  # No valid portion
    assert convolve_valid(signal1, signal2) == expected


def test_convolve_valid_empty_signal2():
    signal1 = [1.0, 2.0, 3.0]
    signal2 = []
    expected = []  # No valid portion
    assert convolve_valid(signal1, signal2) == expected


def test_convolve_valid_both_empty():
    signal1 = []
    signal2 = []
    expected = []  # No valid portion
    assert convolve_valid(signal1, signal2) == expected


def test_hours_as_signal():
    assert hours_as_signal(4.0, partial_first=True) == [1.0] * 4
    assert hours_as_signal(4.0, partial_first=False) == [1.0] * 4
    assert hours_as_signal(2.5, partial_first=True) == [0.5, 1.0, 1.0]
    assert hours_as_signal(2.5, partial_first=False) == [1.0, 1.0, 0.5]


def test_create_charging_plan_no_hours(vehicle_50_percent: VehicleChargeState) -> None:
    with pytest.raises(RuntimeError):
        create_charging_plan(vehicle_charge_state=vehicle_50_percent, hourly_prices=[],
                             charging_request=ChargingRequest(battery_target=100, ready_by=None))


def test_create_charging_plan_ready_by(vehicle_50_percent: VehicleChargeState) -> None:
    start_time = dt.datetime(2024, 8, 3, 0, 0, 0, 0).astimezone()
    hourly_prices: List[HourlyPrice] = [
        HourlyPrice(start=start_time + dt.timedelta(hours=i), price_kwh_dkk=1.0, co2_emission=None)
        for i in range(24)
    ]

    # Make entries 13-16 the optimal time to charge, but force charging to finish by 14:00
    hourly_prices[13].price_kwh_dkk = 0.5
    hourly_prices[14].price_kwh_dkk = 0.3
    hourly_prices[15].price_kwh_dkk = 0.1
    result = create_charging_plan(vehicle_50_percent, hourly_prices,
                                  ChargingRequest(battery_target=100, ready_by=hourly_prices[14].start))
    assert result.success
    assert result.plan is not None
    assert result.plan.end_time <= hourly_prices[14].start


def test_create_charging_plan_immediate_start(vehicle_90_percent: VehicleChargeState) -> None:
    """
    Test that the charging plan will ignore hours in the past, but allow starting in the currently ongoing hour
    """
    five_minutes_ago = dt.datetime.now().astimezone() - dt.timedelta(minutes=5)
    hourly_prices: List[HourlyPrice] = [
        # Make some hours in the past the cheapest
        HourlyPrice(start=five_minutes_ago - dt.timedelta(hours=5), price_kwh_dkk=0.1, co2_emission=None),
        HourlyPrice(start=five_minutes_ago - dt.timedelta(hours=4), price_kwh_dkk=0.1, co2_emission=None),
        HourlyPrice(start=five_minutes_ago - dt.timedelta(hours=3), price_kwh_dkk=0.1, co2_emission=None),
        HourlyPrice(start=five_minutes_ago - dt.timedelta(hours=2), price_kwh_dkk=1.0, co2_emission=None),
        HourlyPrice(start=five_minutes_ago - dt.timedelta(hours=1), price_kwh_dkk=1.0, co2_emission=None),
        # Make the hour that started 5 minutes ago the next best selection
        HourlyPrice(start=five_minutes_ago, price_kwh_dkk=0.5, co2_emission=None),
        HourlyPrice(start=five_minutes_ago + dt.timedelta(hours=1), price_kwh_dkk=1.0, co2_emission=None),
        HourlyPrice(start=five_minutes_ago + dt.timedelta(hours=2), price_kwh_dkk=1.0, co2_emission=None),
        HourlyPrice(start=five_minutes_ago + dt.timedelta(hours=3), price_kwh_dkk=1.0, co2_emission=None),
    ]

    result = create_charging_plan(vehicle_90_percent, hourly_prices, ChargingRequest(battery_target=100, ready_by=None))
    assert result.success
    assert result.plan is not None
    assert result.plan.start_time == five_minutes_ago


def test_create_charging_plan_early_partial_start() -> None:
    """
    Test that the charging plan will start early (partial hour) in the event that charging mostly in a given hour is
    optimal
    """
    # Create a situation where vehicle needs to charge for 1.5 hours and the optimal time is the full third hour, plus
    # half of the second hour
    vehicle_state = vehicle_charge_state_required_for_charging_duration_to_full(1.5)
    now = dt.datetime.now().astimezone()
    hourly_prices: List[HourlyPrice] = [
        # Make some hours in the past the cheapest
        HourlyPrice(start=now + dt.timedelta(hours=1), price_kwh_dkk=1, co2_emission=None),
        HourlyPrice(start=now + dt.timedelta(hours=2), price_kwh_dkk=0.6, co2_emission=None),
        HourlyPrice(start=now + dt.timedelta(hours=3), price_kwh_dkk=0.1, co2_emission=None),
        HourlyPrice(start=now + dt.timedelta(hours=4), price_kwh_dkk=0.61, co2_emission=None),
        HourlyPrice(start=now + dt.timedelta(hours=5), price_kwh_dkk=1, co2_emission=None),
        HourlyPrice(start=now + dt.timedelta(hours=6), price_kwh_dkk=1, co2_emission=None),
    ]
    result = create_charging_plan(vehicle_state, hourly_prices, ChargingRequest(battery_target=100, ready_by=None))
    assert result.success
    assert result.plan is not None
    assert hourly_prices[1].start < result.plan.start_time < hourly_prices[2].start
    # Note: Rounding errors mean that we cannot check the start time precisely here
