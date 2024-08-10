from typing import List, Optional
import datetime as dt
import math

from ladning.constants import BATTERY_CAPACITY_KWH, CHARGING_KW
from ladning.types import VehicleChargeState, HourlyPrice, ChargingPlan, ChargingRequest, ChargingRequestResponse


def argmin(a):
    return min(range(len(a)), key=lambda x: a[x])


def sum_n_sequential(values: List[float], n: int) -> List[float]:
    num_values = len(values)
    if n >= num_values:
        raise RuntimeError(f"Too few entries to compute sum: {num_values} < {n}")
    return [sum(values[i:i + n]) for i in range(len(values) - n)]


def create_charging_plan(vehicle_charge_state: VehicleChargeState, hourly_prices: List[HourlyPrice],
                         charging_request: ChargingRequest) -> ChargingRequestResponse:
    # Check if charging is needed at all
    if not vehicle_charge_state.battery_level < charging_request.battery_target:
        return ChargingRequestResponse(False, reason="Vehicle battery level already at or above target", plan=None)

    if len(hourly_prices) == 0:
        raise RuntimeError("Empty list of hourly prices, cannot create charging plan")

    # Charging is needed - calculate plan
    hours_required_to_charge_to_full = ((charging_request.battery_target -
                                         vehicle_charge_state.battery_level) / 100.0) * BATTERY_CAPACITY_KWH / CHARGING_KW

    # Disregard hourly prices later than the charging request's end time if applicable
    hourly_prices_valid = hourly_prices if charging_request.ready_by is None \
        else [p for p in hourly_prices if p.start + dt.timedelta(hours=1) <= charging_request.ready_by]

    # Check if a sufficient amount of hours exists for the ready by time to be honored
    if len(hourly_prices_valid) < math.ceil(hours_required_to_charge_to_full):
        return ChargingRequestResponse(False, reason="Not enough time to charge to the requested level", plan=None)

    # Pick cheapest consecutive hours for charging
    # This yields the total price for starting at time N and finishing the required M hours later
    # Note that the array is shorter than the input array by M due to not being able to sum past the end of the array
    total_price_per_block = sum_n_sequential([p.price_kwh_dkk for p in hourly_prices_valid],
                                             n=math.ceil(hours_required_to_charge_to_full))
    start_idx = argmin(total_price_per_block)
    start_time = hourly_prices_valid[start_idx].start
    end_time = start_time + dt.timedelta(hours=hours_required_to_charge_to_full)
    return ChargingRequestResponse(success=True, reason="",
                                   plan=ChargingPlan(start_time=start_time, end_time=end_time,
                                                     battery_start=vehicle_charge_state.battery_level,
                                                     battery_end=charging_request.battery_target))
