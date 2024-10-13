from typing import List, Optional
import datetime as dt
import math

from ladning.constants import BATTERY_CAPACITY_KWH, CHARGING_KW_MAX, CHARGING_KW_END, APPROX_MAX_RANGE_KM, \
    TAX_REFUND_DKK_KWH
from ladning.types import VehicleChargeState, HourlyPrice, ChargingPlan, ChargingRequest, ChargingRequestResponse, \
    EnergyNeed


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


def shift_fractional_forward(energy_need: EnergyNeed) -> EnergyNeed:
    """
    Shifts an energy need to have a fractional start (but same total duration and required energy)

    :param energy_need: The energy need to shift
    :return: The shifted energy need
    """
    fractional_hour, full_hours = math.modf(energy_need.hours_required)
    shift = energy_need.energy_signal[0] * fractional_hour
    new_energy_signal = [shift]
    for i in range(len(energy_need.energy_signal) - 1):
        # Calculate what remains after previous shift
        remaining = energy_need.energy_signal[i] - shift

        # Calculate how much is possible to shift from next entry
        shift = min(energy_need.energy_signal[i] - remaining, energy_need.energy_signal[i + 1])
        new_energy_signal.append(remaining + shift)

    return EnergyNeed(energy_signal=new_energy_signal, hours_required=energy_need.hours_required)


def estimate_added_range(battery_state: int, target_state: int) -> float:
    """
    Estimate the added range by moving from the current battery state to a target battery state

    :param battery_state: The starting battery state in the range [0, 100]
    :param target_state: The target battery state in the range [0, 100]
    :return: The estimated added range in kilometers
    """
    range_per_percentage = APPROX_MAX_RANGE_KM / 100.0
    battery_diff = float(target_state - battery_state)
    return range_per_percentage * battery_diff


def calculate_energy_need(battery_state: int, target_state: int) -> Optional[EnergyNeed]:
    """
    Calculate the energy need required to charge from one battery state to the target battery state

    :param battery_state: The starting battery state in the range [0, 100]
    :param target_state: The target battery state in the range [0, 100]
    :return: The energy need object, or None if no charging is required
    """
    if battery_state < 0 or battery_state > 100:
        raise RuntimeError(f"Starting battery state has to be in range [0, 100], was '{battery_state}'")
    if target_state < 0 or target_state > 100:
        raise RuntimeError(f"Target battery state has to be in range [0, 100], was '{target_state}'")
    if battery_state >= target_state:
        return None

    if target_state < 95:
        # If target is below 95%, only consider the full charging speed
        hours_required = ((target_state - battery_state) / 100.0) * BATTERY_CAPACITY_KWH / CHARGING_KW_MAX

        # The energy signal is 'CHARGING_KW_MAX' for the full hours, followed by 'CHARGING_KW_MAX' for a fractional part
        # of the last hour
        fractional_hour, full_hours = math.modf(hours_required)
        energy_signal = [CHARGING_KW_MAX] * int(full_hours) + [CHARGING_KW_MAX * fractional_hour]
        return EnergyNeed(energy_signal=energy_signal, hours_required=hours_required)

    # If charging above 95%, first charge at full rate to 95% ...
    hours_required_to_95_percent = ((95 - battery_state) / 100.0) * BATTERY_CAPACITY_KWH / CHARGING_KW_MAX

    # ... then charge the remaining 5% at a lower rate
    hours_required_from_95_percent = ((target_state - 95) / 100.0) * BATTERY_CAPACITY_KWH / CHARGING_KW_END

    energy_signal: List[float] = []
    hours_required = 0
    if hours_required_to_95_percent > 0:
        hours_required += hours_required_to_95_percent
        fractional_hour_to_95, full_hours_to_95 = math.modf(hours_required_to_95_percent)
        energy_signal.extend([CHARGING_KW_MAX] * int(full_hours_to_95))
        if fractional_hour_to_95 > 0:
            energy_signal.append(CHARGING_KW_MAX * fractional_hour_to_95)
    if hours_required_from_95_percent > 0:
        hours_required += hours_required_from_95_percent

        # Modify existing fractional energy signal entry according to lower charge rate (for the remaining time)
        if len(energy_signal) > 0:
            available_time = 1.0 - math.modf(hours_required_to_95_percent)[0]
            used_time = min(available_time, hours_required_from_95_percent)
            energy_signal[-1] += used_time * CHARGING_KW_END
            hours_required_from_95_percent -= used_time

        # Add remaining reduced energy signal entries
        fractional_hour_from_95, full_hours_from_95 = math.modf(hours_required_from_95_percent)
        energy_signal.extend([CHARGING_KW_END] * int(full_hours_from_95))
        if fractional_hour_from_95 > 0.0:
            energy_signal.append(CHARGING_KW_END * fractional_hour_from_95)

    return EnergyNeed(energy_signal=energy_signal, hours_required=hours_required)


def create_charging_plan(vehicle_charge_state: VehicleChargeState, hourly_prices: List[HourlyPrice],
                         charging_request: ChargingRequest) -> ChargingRequestResponse:
    # Check if charging is needed at all
    if not vehicle_charge_state.battery_level < charging_request.battery_target:
        return ChargingRequestResponse(False, reason="Vehicle battery level already at or above target", plan=None)

    if len(hourly_prices) == 0:
        raise RuntimeError("Empty list of hourly prices, cannot create charging plan")

    # Charging is needed - calculate plan
    maybe_energy_need = calculate_energy_need(vehicle_charge_state.battery_level, charging_request.battery_target)
    if maybe_energy_need is None:
        return ChargingRequestResponse(False, reason="Vehicle battery level already at or above target", plan=None)
    energy_need = maybe_energy_need

    # Determine valid hourly prices
    hourly_prices_valid = []
    for p in hourly_prices:
        # Disregard hours fully in the past (ongoing hour is valid) ...
        valid = p.start >= dt.datetime.now().astimezone() - dt.timedelta(hours=1)
        # ... and disregard hourly prices later than the charging request's end time if applicable ...
        if charging_request.ready_by is not None:
            valid &= p.start + dt.timedelta(hours=1) <= charging_request.ready_by
        if valid:
            hourly_prices_valid.append(p)

    # Check if a sufficient amount of hours exists for the ready by time to be honored
    if len(hourly_prices_valid) < math.ceil(energy_need.hours_required):
        return ChargingRequestResponse(False, reason="Not enough time to charge to the requested level", plan=None)

    # Pick cheapest consecutive hours for charging
    # This yields the total price for starting at time N and finishing the required M hours later
    # Note that the array is shorter than the input array by M due to not being able to sum past the end of the array
    prices_after_refund = [p.price_kwh_dkk - TAX_REFUND_DKK_KWH for p in hourly_prices_valid]
    full_hour_total_prices = convolve_valid(prices_after_refund, energy_need.energy_signal)
    partial_hour_energy_need = shift_fractional_forward(energy_need)
    partial_hour_total_prices = convolve_valid(prices_after_refund, partial_hour_energy_need.energy_signal)

    # Estimate the added range in km
    range_added = estimate_added_range(vehicle_charge_state.battery_level, charging_request.battery_target)

    # Check which hourly strategy yields the lowest total price
    if min(full_hour_total_prices) <= min(partial_hour_total_prices):
        # Full hour strategy works best
        start_idx = argmin(full_hour_total_prices)
        start_time = hourly_prices_valid[start_idx].start
        end_time = start_time + dt.timedelta(hours=energy_need.hours_required)
        return ChargingRequestResponse(success=True, reason="",
                                       plan=ChargingPlan(start_time=start_time, end_time=end_time,
                                                         battery_start=vehicle_charge_state.battery_level,
                                                         battery_end=charging_request.battery_target,
                                                         total_cost_dkk=min(full_hour_total_prices),
                                                         range_added_km=range_added
                                                         ))
    else:
        # Partial hour strategy works best
        start_idx = argmin(partial_hour_total_prices)
        starting_hour = hourly_prices_valid[start_idx].start

        # Determine how many minutes into the hour to start
        hourly_fraction = math.modf(energy_need.hours_required)[0]
        minutes_into_hour = (1.0 - hourly_fraction) * 60.0
        start_time = starting_hour + dt.timedelta(minutes=minutes_into_hour)
        end_time = start_time + dt.timedelta(hours=energy_need.hours_required)
        return ChargingRequestResponse(success=True, reason="",
                                       plan=ChargingPlan(start_time=start_time, end_time=end_time,
                                                         battery_start=vehicle_charge_state.battery_level,
                                                         battery_end=charging_request.battery_target,
                                                         total_cost_dkk=min(partial_hour_total_prices),
                                                         range_added_km=range_added
                                                         ))
