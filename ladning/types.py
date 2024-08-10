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


@dataclasses.dataclass
class ChargingRequest:
    battery_target: int  # The battery level to charge to
    ready_by: Optional[dt.datetime]  # The date/time by which the charging should have reached the target battery level


@dataclasses.dataclass
class ChargingRequestResponse:
    success: bool  # Whether the charging request could be honored
    reason: str  # Reason that the charging request could not be honored (empty on success)
    plan: Optional[ChargingPlan]  # The created charging plan (None if not successful)
