import dataclasses
import datetime as dt
from typing import Optional, List

@dataclasses.dataclass
class VehicleChargeState:
    battery_level: int

@dataclasses.dataclass
class VehicleState:
    """
    VehicleState represents the vehicle's connection and battery information
    exposed via the web API. charge_level is optional and may be None when unknown.
    """
    connected: bool
    charge_level: Optional[int]

@dataclasses.dataclass
class Price:
    start: dt.datetime
    price_kwh_dkk: float

@dataclasses.dataclass
class ChargingPlan:
    start_time: dt.datetime
    end_time: dt.datetime
    battery_start: int
    battery_end: int
    total_cost_dkk: float
    range_added_km: float

@dataclasses.dataclass
class EnergyNeed:
    energy_signal: List[float]  # Energy needed per quarter-hour in kwh
    quarter_hours_required: float

@dataclasses.dataclass
class ChargingRequest:
    battery_target: int  # The battery level to charge to
    ready_by: Optional[dt.datetime]  # The date/time by which the charging should have reached the target battery level
    max_average_price_dkk_kwh: Optional[float]  # The maximum price to pay on average in DKK/kWh before tax reduction
    charge_immediately: bool = False  # Whether to immediately begin charging, regardless of price

@dataclasses.dataclass
class ChargingRequestResponse:
    success: bool  # Whether the charging request could be honored
    reason: str  # Reason that the charging request could not be honored (empty on success)
    plan: Optional[ChargingPlan]  # The created charging plan (None if not successful)