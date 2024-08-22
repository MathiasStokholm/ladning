from typing import List, Optional
import datetime as dt
import math

from ladning.constants import BATTERY_CAPACITY_KWH, CHARGING_KW_MAX, CHARGING_KW_END
from ladning.types import VehicleChargeState, HourlyPrice, ChargingPlan, ChargingRequest, ChargingRequestResponse


def argmin(a: List[float]) -> int:
    """
    Returns the index in the list with the minimum value. Returns -1 on an empty input list.

    :param a: The list to process
    :return: The index that corresponds to the minimum value in the input list
    """
    return min(range(len(a)), key=lambda x: a[x], default=-1)


def convolve_valid(signal1: List[float], signal2: List[float]) -> List[float]:
    """
    Convolves two signals and returns the valid portion

    :param signal1: The first signal
    :param signal2: The second signal
    :return: The valid portion of the result of convolution
    """
    len1 = len(signal1)
    len2 = len(signal2)
    valid_length = len1 - len2 + 1
    if valid_length <= 0 or len2 == 0:
        return []  # No valid portion

    result = []
    for i in range(valid_length):
        conv_sum = 0
        for j in range(len2):
            conv_sum += signal1[i + j] * signal2[j]
        result.append(conv_sum)

    return result


def hours_as_signal(hours: float, partial_first: bool) -> List[float]:
    """
    Create a signal to use for convolution from a number of hours, e.g. 3.1 -> [1.0, 1.0, 1.0, 0.1]

    :param hours: The (possibly fractional) number of hours to create a signal for
    :param partial_first: Whether to place the fractional hour at the front of the signal (otherwise place at back)
    :return: The created signal
    """
    fractional_hour, full_hours = math.modf(hours)
    sig = [1.0] * int(full_hours)
    if fractional_hour != 0:
        if partial_first:
            sig.insert(0, fractional_hour)
        else:
            sig.append(fractional_hour)
    return sig


def calculate_hours_required_to_charge(battery_state: int, target_state: int,
                                       full_charge_safety_margin_minutes: int = 0) -> Optional[float]:
    """
    Calculate the number of hours required to charge from one battery state to the target battery state

    :param battery_state: The starting battery state in the range [0, 100]
    :param target_state: The target battery state in the range [0, 100]
    :param full_charge_safety_margin_minutes: Additional number of minutes to add as a safety margin when charging to
    100%
    :return: The fractional number of hours required to charge, or None if no charging is required
    """
    if battery_state < 0 or battery_state > 100:
        raise RuntimeError(f"Starting battery state has to be in range [0, 100], was '{battery_state}'")
    if target_state < 0 or target_state > 100:
        raise RuntimeError(f"Target battery state has to be in range [0, 100], was '{target_state}'")
    if battery_state >= target_state:
        return None

    if target_state < 95:
        # If target is below 95%, only consider the full charging speed
        return ((target_state - battery_state) / 100.0) * BATTERY_CAPACITY_KWH / CHARGING_KW_MAX

    # If charging above 95%, consider the slower charging at the end
    hours_required_to_95_percent = ((95 - battery_state) / 100.0) * BATTERY_CAPACITY_KWH / CHARGING_KW_MAX
    hours_required_from_95_percent = ((target_state - 95) / 100.0) * BATTERY_CAPACITY_KWH / CHARGING_KW_END

    hours_required = 0
    if hours_required_to_95_percent > 0:
        hours_required += hours_required_to_95_percent
    if hours_required_from_95_percent > 0:
        hours_required += hours_required_from_95_percent

    # Add safety margin if applicable
    if target_state == 100 and full_charge_safety_margin_minutes > 0:
        hours_required += full_charge_safety_margin_minutes / 60.0
    return hours_required


def create_charging_plan(vehicle_charge_state: VehicleChargeState, hourly_prices: List[HourlyPrice],
                         charging_request: ChargingRequest,
                         full_charge_safety_margin_minutes: int = 0) -> ChargingRequestResponse:
    # Check if charging is needed at all
    if not vehicle_charge_state.battery_level < charging_request.battery_target:
        return ChargingRequestResponse(False, reason="Vehicle battery level already at or above target", plan=None)

    if len(hourly_prices) == 0:
        raise RuntimeError("Empty list of hourly prices, cannot create charging plan")

    # Charging is needed - calculate plan
    maybe_hours_required_to_charge = calculate_hours_required_to_charge(vehicle_charge_state.battery_level,
                                                                        charging_request.battery_target,
                                                                        full_charge_safety_margin_minutes)
    if maybe_hours_required_to_charge is None:
        return ChargingRequestResponse(False, reason="Vehicle battery level already at or above target", plan=None)
    hours_required_to_charge = maybe_hours_required_to_charge

    # Disregard hourly prices later than the charging request's end time if applicable, and disregard hourly prices
    # fully in the past (ongoing hour is valid)
    hourly_prices_valid = [
        p for p in hourly_prices
        if (charging_request.ready_by is not None and (p.start + dt.timedelta(hours=1) <= charging_request.ready_by)) or
           (p.start >= dt.datetime.now().astimezone() - dt.timedelta(hours=1))
    ]

    # Check if a sufficient amount of hours exists for the ready by time to be honored
    if len(hourly_prices_valid) < math.ceil(hours_required_to_charge):
        return ChargingRequestResponse(False, reason="Not enough time to charge to the requested level", plan=None)

    # Compute signals that define potential starting strategies
    full_hour_start_strategy = hours_as_signal(hours_required_to_charge, partial_first=False)
    partial_hour_start_strategy = hours_as_signal(hours_required_to_charge, partial_first=True)

    # Pick cheapest consecutive hours for charging
    # This yields the total price for starting at time N and finishing the required M hours later
    # Note that the array is shorter than the input array by M due to not being able to sum past the end of the array
    full_hour_total_prices = convolve_valid([p.price_kwh_dkk for p in hourly_prices_valid], full_hour_start_strategy)
    partial_hour_total_prices = convolve_valid([p.price_kwh_dkk for p in hourly_prices_valid],
                                               partial_hour_start_strategy)

    # Check which hourly strategy yields the lowest total price
    if min(full_hour_total_prices) <= min(partial_hour_total_prices):
        # Full hour strategy works best
        start_idx = argmin(full_hour_total_prices)
        start_time = hourly_prices_valid[start_idx].start
        end_time = start_time + dt.timedelta(hours=hours_required_to_charge)
        return ChargingRequestResponse(success=True, reason="",
                                       plan=ChargingPlan(start_time=start_time, end_time=end_time,
                                                         battery_start=vehicle_charge_state.battery_level,
                                                         battery_end=charging_request.battery_target))
    else:
        # Partial hour strategy works best
        start_idx = argmin(partial_hour_total_prices)
        starting_hour = hourly_prices_valid[start_idx].start

        # Determine how many minutes into the hour to start
        hourly_fraction = partial_hour_start_strategy[0]
        minutes_into_hour = (1.0 - hourly_fraction) * 60.0
        start_time = starting_hour + dt.timedelta(minutes=minutes_into_hour)
        end_time = start_time + dt.timedelta(hours=hours_required_to_charge)
        return ChargingRequestResponse(success=True, reason="",
                                       plan=ChargingPlan(start_time=start_time, end_time=end_time,
                                                         battery_start=vehicle_charge_state.battery_level,
                                                         battery_end=charging_request.battery_target))
