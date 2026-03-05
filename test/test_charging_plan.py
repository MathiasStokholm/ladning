import math
from typing import List

import pytest
import datetime as dt

from ladning.charging_plan import create_charging_plan, argmin, convolve_valid, calculate_energy_need, \
    shift_fractional
from ladning.constants import BATTERY_CAPACITY_KWH, CHARGING_KW_MAX, CHARGING_KW_END, SAMPLING_PERIOD
from ladning.types import VehicleChargeState, Price, ChargingRequest, EnergyNeed


@pytest.fixture()
def vehicle_50_percent() -> VehicleChargeState:
    return VehicleChargeState(battery_level=50)


@pytest.fixture()
def vehicle_90_percent() -> VehicleChargeState:
    return VehicleChargeState(battery_level=90)


def vehicle_charge_state_required_for_charging_duration_to_full(hours_of_charging: float) \
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
    return VehicleChargeState(battery_state)


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


def test_convolve_valid_basic() -> None:
    signal1 = [1.0, 2.0, 3.0, 4.0]
    signal2 = [0.5, 1.0, 0.5]
    expected = [4.0, 6.0]
    assert convolve_valid(signal1, signal2) == expected


def test_convolve_valid_equal_length() -> None:
    signal1 = [1.0, 2.0, 3.0]
    signal2 = [1.0, 2.0, 3.0]
    expected = [14.0]
    assert convolve_valid(signal1, signal2) == expected


def test_convolve_valid_signal2_longer() -> None:
    signal1 = [1.0, 2.0]
    signal2 = [1.0, 2.0, 3.0]
    expected = []  # No valid portion
    assert convolve_valid(signal1, signal2) == expected


def test_convolve_valid_empty_signal1() -> None:
    signal1 = []
    signal2 = [1.0, 2.0, 3.0]
    expected = []  # No valid portion
    assert convolve_valid(signal1, signal2) == expected


def test_convolve_valid_empty_signal2() -> None:
    signal1 = [1.0, 2.0, 3.0]
    signal2 = []
    expected = []  # No valid portion
    assert convolve_valid(signal1, signal2) == expected


def test_convolve_valid_both_empty() -> None:
    signal1 = []
    signal2 = []
    expected = []  # No valid portion
    assert convolve_valid(signal1, signal2) == expected


def test_shift_fractional_single_hour() -> None:
    """
    When shifting an EnergyNeed of less than a quarter-hour, simple return as is
    """
    energy_need = EnergyNeed([2.65 * 0.5], 0.5)
    shifted_need = shift_fractional(energy_need, fraction=0.5)
    assert shifted_need == energy_need


def test_shift_fractional() -> None:
    """
    Test that shifting a "full" energy signal back by 50% changes the first entry appropriately and adds a new entry
    at the end
    """
    energy_need = EnergyNeed([10, 10, 10], 3.0)
    fraction = 0.5
    shifted_need = shift_fractional(energy_need, fraction)
    assert shifted_need.quarter_hours_required == energy_need.quarter_hours_required
    assert len(shifted_need.energy_signal) == len(energy_need.energy_signal) + 1
    assert shifted_need.energy_signal[0] == pytest.approx(10 * 0.5)
    assert shifted_need.energy_signal[1] == pytest.approx(10)
    assert shifted_need.energy_signal[2] == pytest.approx(10)
    assert shifted_need.energy_signal[3] == pytest.approx(10 * 0.5)
    assert sum(shifted_need.energy_signal) == pytest.approx(sum(energy_need.energy_signal))


def test_calculate_energy_need_invalid_inputs() -> None:
    # Target state less than current battery state
    assert calculate_energy_need(battery_state=90, target_state=89) is None

    # Negative inputs
    with pytest.raises(RuntimeError):
        calculate_energy_need(battery_state=10, target_state=-1)
    with pytest.raises(RuntimeError):
        calculate_energy_need(battery_state=-1, target_state=10)

    # Inputs above 100%
    with pytest.raises(RuntimeError):
        calculate_energy_need(battery_state=110, target_state=90)
    with pytest.raises(RuntimeError):
        calculate_energy_need(battery_state=90, target_state=110)


def test_calculate_energy_need_below_95() -> None:
    current = 0.4
    target = 0.95
    diff = target - current
    energy_need = calculate_energy_need(battery_state=int(current * 100), target_state=int(target * 100))
    assert energy_need is not None

    # The energy signal should sum to the total energy need
    assert sum(energy_need.energy_signal) == pytest.approx(diff * BATTERY_CAPACITY_KWH)

    # All the full hours (except the last fractional hour) should charge at max rate
    # The last fractional hour should also charge at max rate, but for less than a full hour
    fractional_quarter_hour, full_quarter_hours = math.modf(energy_need.quarter_hours_required)
    assert energy_need.energy_signal[:-1] == [CHARGING_KW_MAX / 4] * int(full_quarter_hours)
    assert energy_need.energy_signal[-1] == pytest.approx(fractional_quarter_hour * CHARGING_KW_MAX / 4)


def test_calculate_energy_need_to_full() -> None:
    current = 0.4
    target = 1.0
    diff = target - current
    energy_need = calculate_energy_need(battery_state=int(current * 100), target_state=int(target * 100))
    assert energy_need is not None

    # The energy signal should sum to the total energy need
    assert sum(energy_need.energy_signal) == pytest.approx(diff * BATTERY_CAPACITY_KWH)

    # Charging should happen at max rate until 95%, and then drop to a lower rate
    # TODO: Find a way to check this


def test_create_charging_plan_no_hours(vehicle_50_percent: VehicleChargeState) -> None:
    with pytest.raises(RuntimeError):
        create_charging_plan(vehicle_charge_state=vehicle_50_percent, prices=[],
                             charging_request=ChargingRequest(battery_target=100, ready_by=None,
                                                              max_average_price_dkk_kwh=2.0),
                             current_time=dt.datetime.now().astimezone())


def test_create_charging_plan_ready_by(vehicle_50_percent: VehicleChargeState) -> None:
    """
    Test that charge planning honors the 'ready_by' setting even though it results in suboptimal cost
    """
    start_time = dt.datetime.now().astimezone()
    prices: List[Price] = [
        Price(start=start_time + dt.timedelta(minutes=i * 15), price_kwh_dkk=2.0)
        for i in range(24 * 4)
    ]

    # Make entries 13:00-16:00 the optimal time to charge, but force charging to finish by 14:00
    expected_ready_by = prices[14 * 4].start
    for price in prices[13 * 4: 13 * 4 + 4]:
        price.price_kwh_dkk = 1.5
    for price in prices[14 * 4: 14 * 4 + 4]:
        price.price_kwh_dkk = 1.3
    for price in prices[15 * 4: 15 * 4 + 4]:
        price.price_kwh_dkk = 1.1
    result = create_charging_plan(vehicle_50_percent, prices,
                                  ChargingRequest(battery_target=100, ready_by=expected_ready_by,
                                                  max_average_price_dkk_kwh=2.0),
                                  current_time=start_time)
    assert result.success
    assert result.plan is not None
    assert result.plan.end_time <= expected_ready_by


def test_create_charging_plan_immediate_start(vehicle_90_percent: VehicleChargeState) -> None:
    """
    Test that the charging plan will ignore hours in the past, but allow starting in the currently ongoing quarter-hour
    if doing so is optimal from a cost perspective
    """
    now = dt.datetime.now().astimezone()
    five_minutes_ago = now - dt.timedelta(minutes=5)

    def _add_quarter_hour_prices(_hour_start: int, _price: float) -> List[Price]:
        return [
            Price(start=five_minutes_ago - dt.timedelta(hours=_hour_start), price_kwh_dkk=_price),
            Price(start=five_minutes_ago - dt.timedelta(hours=_hour_start) + SAMPLING_PERIOD, price_kwh_dkk=_price),
            Price(start=five_minutes_ago - dt.timedelta(hours=_hour_start) + SAMPLING_PERIOD * 2, price_kwh_dkk=_price),
            Price(start=five_minutes_ago - dt.timedelta(hours=_hour_start) + SAMPLING_PERIOD * 3, price_kwh_dkk=_price),
        ]

    prices: List[Price] = []
    # Make some hours in the past the cheapest
    prices.extend(_add_quarter_hour_prices(_hour_start=5, _price=0.1))
    prices.extend(_add_quarter_hour_prices(_hour_start=4, _price=0.1))
    prices.extend(_add_quarter_hour_prices(_hour_start=3, _price=0.1))
    prices.extend(_add_quarter_hour_prices(_hour_start=2, _price=1.0))
    prices.extend(_add_quarter_hour_prices(_hour_start=1, _price=1.0))

    # Make the quarter-hour that started 5 minutes ago the next best selection
    prices.extend(_add_quarter_hour_prices(_hour_start=0, _price=0.5))
    prices.extend(_add_quarter_hour_prices(_hour_start=1, _price=1.0))
    prices.extend(_add_quarter_hour_prices(_hour_start=2, _price=1.0))
    prices.extend(_add_quarter_hour_prices(_hour_start=3, _price=1.0))

    result = create_charging_plan(vehicle_90_percent, prices,
                                  ChargingRequest(battery_target=100, ready_by=None, max_average_price_dkk_kwh=2.0),
                                  current_time=now)
    assert result.success
    assert result.plan is not None
    assert result.plan.start_time == now


def test_create_charging_plan_early_partial_start() -> None:
    """
    Test that the charging plan will start early (partial hour) in the event that charging mostly in a given hour is
    optimal
    """
    # Create a situation where vehicle needs to charge for 1.5 hours and the optimal time is the full third hour, plus
    # half of the second hour
    vehicle_state = vehicle_charge_state_required_for_charging_duration_to_full(1.5)
    now = dt.datetime.now().astimezone()

    def _add_quarter_hour_prices(_hour_start: int, _price: float) -> List[Price]:
        return [
            Price(start=now + dt.timedelta(hours=_hour_start), price_kwh_dkk=_price),
            Price(start=now + dt.timedelta(hours=_hour_start) + SAMPLING_PERIOD, price_kwh_dkk=_price),
            Price(start=now + dt.timedelta(hours=_hour_start) + SAMPLING_PERIOD * 2, price_kwh_dkk=_price),
            Price(start=now + dt.timedelta(hours=_hour_start) + SAMPLING_PERIOD * 3, price_kwh_dkk=_price),
        ]

    prices: List[Price] = []
    prices.extend(_add_quarter_hour_prices(_hour_start=1, _price=2))
    prices.extend(_add_quarter_hour_prices(_hour_start=2, _price=1.4))
    prices.extend(_add_quarter_hour_prices(_hour_start=3, _price=1.1))
    prices.extend(_add_quarter_hour_prices(_hour_start=4, _price=1.91))
    prices.extend(_add_quarter_hour_prices(_hour_start=5, _price=2))
    prices.extend(_add_quarter_hour_prices(_hour_start=6, _price=2))

    result = create_charging_plan(vehicle_state, prices,
                                  ChargingRequest(battery_target=100, ready_by=None, max_average_price_dkk_kwh=2.0),
                                  current_time=now)
    assert result.success
    assert result.plan is not None
    assert prices[1 * 4].start < result.plan.start_time < prices[2 * 4].start
    # Note: Rounding errors mean that we cannot check the start time precisely here


def test_create_charging_plan_max_price() -> None:
    """
    Test that charging plan creation fails if price is higher than maximum requested value
    """
    # Assume that charging will take almost two hours
    vehicle_state = vehicle_charge_state_required_for_charging_duration_to_full(2.0)
    now = dt.datetime.now().astimezone()
    hourly_prices: List[Price] = [
        Price(start=now + dt.timedelta(minutes=0), price_kwh_dkk=1.0),
        Price(start=now + dt.timedelta(minutes=15), price_kwh_dkk=1.0),
        Price(start=now + dt.timedelta(minutes=30), price_kwh_dkk=1.0),
        Price(start=now + dt.timedelta(minutes=45), price_kwh_dkk=1.0),
        Price(start=now + dt.timedelta(hours=1, minutes=0), price_kwh_dkk=2.0),
        Price(start=now + dt.timedelta(hours=1, minutes=15), price_kwh_dkk=2.0),
        Price(start=now + dt.timedelta(hours=1, minutes=30), price_kwh_dkk=2.0),
        Price(start=now + dt.timedelta(hours=1, minutes=45), price_kwh_dkk=2.0),
    ]

    # Plan should succeed if maximum average price is higher than actual average price or if argument is left out
    result = create_charging_plan(vehicle_state, hourly_prices,
                                  ChargingRequest(battery_target=100, ready_by=None, max_average_price_dkk_kwh=1.51),
                                  current_time=now)
    assert result.success
    result = create_charging_plan(vehicle_state, hourly_prices,
                                  ChargingRequest(battery_target=100, ready_by=None, max_average_price_dkk_kwh=None),
                                  current_time=now)
    assert result.success

    # Plan should fail if maximum average price is lower than actual average price
    result = create_charging_plan(vehicle_state, hourly_prices,
                                  ChargingRequest(battery_target=100, ready_by=None, max_average_price_dkk_kwh=1.45),
                                  current_time=now)
    assert not result.success


def test_create_charging_plan_less_than_one_hour() -> None:
    """
    Test that charging plan creation favors starting from the beginning of the cheapest hour when charging is expected
    to take less than a quarter of an hour
    """
    vehicle_state = vehicle_charge_state_required_for_charging_duration_to_full(hours_of_charging=0.5 / 4)
    now = dt.datetime.now().astimezone()
    hourly_prices: List[Price] = [
        Price(start=now + dt.timedelta(minutes=0), price_kwh_dkk=2),
        Price(start=now + dt.timedelta(minutes=15), price_kwh_dkk=1.4),
        Price(start=now + dt.timedelta(minutes=30), price_kwh_dkk=2),
    ]
    result = create_charging_plan(vehicle_state, hourly_prices,
                                  ChargingRequest(battery_target=100, ready_by=None, max_average_price_dkk_kwh=1.8),
                                  current_time=now)

    # Plan should start exactly when the cheapest hour begins
    assert result.success
    assert result.plan is not None
    assert result.plan.start_time == hourly_prices[1].start


def test_create_charging_plan_immediate_battery_at_target() -> None:
    """
    Test that charging plan creation with charge_immediately=True always attempts to start charging, even when
    the battery is already at the target level (e.g. to allow another car to charge from the outlet)
    """
    vehicle_state = VehicleChargeState(battery_level=100)
    now = dt.datetime.now().astimezone()
    prices: List[Price] = [
        Price(start=now + dt.timedelta(minutes=i * 15), price_kwh_dkk=1.0)
        for i in range(8)
    ]

    # Without charge_immediately, charging plan should fail since battery is already at target
    result = create_charging_plan(vehicle_state, prices,
                                  ChargingRequest(battery_target=100, ready_by=None, max_average_price_dkk_kwh=None,
                                                  charge_immediately=False), current_time=now)
    assert not result.success

    # With charge_immediately=True, charging plan should succeed even though battery is already at target
    result = create_charging_plan(vehicle_state, prices,
                                  ChargingRequest(battery_target=100, ready_by=None, max_average_price_dkk_kwh=None,
                                                  charge_immediately=True), current_time=now)
    assert result.success
    assert result.plan is not None
    assert result.plan.start_time == now
    assert result.plan.battery_start == 100
    assert result.plan.battery_end == 100
    assert result.plan.total_cost_dkk == 0.0
    assert result.plan.range_added_km == 0.0


def test_create_charging_plan_immediate() -> None:
    """
    Test that charging plan creation can create a plan that begins immediately, regardless of price
    """
    vehicle_state = vehicle_charge_state_required_for_charging_duration_to_full(hours_of_charging=2.8)
    now = dt.datetime.now().astimezone()

    def _add_quarter_hour_prices(_hour_start: int, _price: float) -> List[Price]:
        return [
            Price(start=now + dt.timedelta(hours=_hour_start), price_kwh_dkk=_price),
            Price(start=now + dt.timedelta(hours=_hour_start) + SAMPLING_PERIOD, price_kwh_dkk=_price),
            Price(start=now + dt.timedelta(hours=_hour_start) + SAMPLING_PERIOD * 2, price_kwh_dkk=_price),
            Price(start=now + dt.timedelta(hours=_hour_start) + SAMPLING_PERIOD * 3, price_kwh_dkk=_price),
        ]

    prices: List[Price] = []
    prices.extend(_add_quarter_hour_prices(_hour_start=0, _price=3))
    prices.extend(_add_quarter_hour_prices(_hour_start=1, _price=2))
    prices.extend(_add_quarter_hour_prices(_hour_start=2, _price=1))
    prices.extend(_add_quarter_hour_prices(_hour_start=3, _price=1))
    prices.extend(_add_quarter_hour_prices(_hour_start=4, _price=1))
    result = create_charging_plan(vehicle_state, prices,
                                  ChargingRequest(battery_target=100, ready_by=None, max_average_price_dkk_kwh=None,
                                                  charge_immediately=True), current_time=now)

    # Plan should start exactly when the cheapest hour begins
    assert result.success
    assert result.plan is not None
    assert result.plan.start_time == prices[0].start
    assert result.plan.battery_end == 100
    assert result.plan.end_time > prices[2 * 4].start
    assert result.plan.end_time < prices[3 * 4].start
