import dataclasses
import datetime as dt
from typing import Optional


@dataclasses.dataclass
class VehicleChargeState:
    battery_level: int
    range_km: float
    minutes_to_full_charge: int


@dataclasses.dataclass
class HourlyPrice:
    start: dt.datetime
    price_kwh_dkk: float
    co2_emission: Optional[float]


@dataclasses.dataclass
class ChargingPlan:
    start_time: dt.datetime
    end_time: dt.datetime
    battery_start: int
    battery_end: int
