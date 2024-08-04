from typing import List, Optional
import datetime as dt
import numpy as np
import math

from ladning.constants import BATTERY_CAPACITY_KWH, CHARGING_KW
from ladning.types import VehicleChargeState, HourlyPrice, ChargingPlan


def create_charging_plan(vehicle_charge_state: VehicleChargeState, hourly_prices: List[HourlyPrice],
                         target_battery_level: int = 100) -> Optional[ChargingPlan]:
    # Check if charging is needed at all
    if target_battery_level <= vehicle_charge_state.battery_level:
        return None

    if len(hourly_prices) == 0:
        raise RuntimeError("Empty list of hourly prices, cannot create charging plan")

    # Charging is needed - calculate plan
    hours_required_to_charge_to_full = ((target_battery_level -
                                         vehicle_charge_state.battery_level) / 100.0) * BATTERY_CAPACITY_KWH / CHARGING_KW

    # Pick cheapest consecutive hours for charging
    prices = np.array([p.price_kwh_dkk for p in hourly_prices])

    # This yields the total price for starting at time N and finishing the required M hours later
    # Note that the array is shorter than the input array by M due to not being able to sum past the end of the array
    total_price_per_block = np.convolve(prices, np.ones(math.ceil(hours_required_to_charge_to_full)), mode='valid')
    start_idx = np.argmin(total_price_per_block)
    start_time = hourly_prices[start_idx].start
    end_time = start_time + dt.timedelta(hours=hours_required_to_charge_to_full)
    return ChargingPlan(start_time=start_time, end_time=end_time, battery_start=vehicle_charge_state.battery_level,
                        battery_end=100)
