from typing import List, Optional
import datetime as dt

from ladning.constants import BATTERY_CAPACITY_KWH, CHARGING_KW
from ladning.types import VehicleChargeState, HourlyPrice, ChargingPlan


def create_charging_plan(vehicle_charge_state: VehicleChargeState, hourly_prices: List[HourlyPrice],
                         target_battery_level: int = 100) -> Optional[ChargingPlan]:
    # Check if charging is needed at all
    if target_battery_level <= vehicle_charge_state.battery_level:
        return None

    # Charging is needed - calculate plan
    hours_required_to_charge_to_full = ((target_battery_level -
                                         vehicle_charge_state.battery_level) / 100.0) * BATTERY_CAPACITY_KWH / CHARGING_KW

    # Naive approach - start right now
    start_time = dt.datetime.now()
    end_time = start_time + dt.timedelta(hours=hours_required_to_charge_to_full)
    return ChargingPlan(start_time=start_time, end_time=end_time, battery_start=vehicle_charge_state.battery_level,
                        battery_end=100)
