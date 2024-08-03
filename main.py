import asyncio
from typing import AsyncIterator, Optional, Dict, Any, List

from pyeasee import Easee
import argparse

import pyeasee
from pyeasee.charger import STATUS as CHARGER_STATUS, Charger
import teslapy
import dataclasses
import datetime as dt
import requests

MILES_TO_KILOMETERS = 1.609344
BATTERY_CAPACITY_KWH = 57.5  # Tesla Model 3 Highland RWD
CHARGING_KW = 11.0  # Easee Lite


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


def next_datetime_at_hour(current: dt.datetime, hour: int) -> dt.datetime:
    repl = current.replace(hour=hour, minute=0, second=0, microsecond=0)
    while repl <= current:
        repl = repl + dt.timedelta(days=1)
    return repl


def create_charging_plan(vehicle_charge_state: VehicleChargeState, hourly_prices: List[HourlyPrice],
                         target_battery_level: int = 100) -> Optional[ChargingPlan]:
    # Check if charging is needed at all
    if target_battery_level <= vehicle_charge_state.battery_level:
        return None

    # Charging is needed - calculate plan
    hours_required_to_charge_to_full = ((target_battery_level -
                                         vehicle_charge_state.battery_level) / 100.0) * BATTERY_CAPACITY_KWH / CHARGING_KW

    # Naive approach - pick cheapest hour
    # TODO
    start_time = next_datetime_at_hour(dt.datetime.now(), 13)
    end_time = start_time + dt.timedelta(hours=hours_required_to_charge_to_full)
    return ChargingPlan(start_time=start_time, end_time=end_time, battery_start=vehicle_charge_state.battery_level,
                        battery_end=100)


def get_energy_prices() -> List[HourlyPrice]:
    price_area = "DK2"  # Price area for Sealand and Copenhagen
    date_str = dt.datetime.now().strftime("%Y-%m-%dT%H:00")
    url = f'https://api.energidataservice.dk/dataset/elspotprices?start={date_str}&filter={{"PriceArea":["{price_area}"]}}'
    records = requests.get(url).json()["records"]

    def _convert(record: Dict[str, Any]) -> HourlyPrice:
        start = dt.datetime.strptime(record["HourDK"], "%Y-%m-%dT%H:%M:%S")
        price_mwh_dkk = record["SpotPriceDKK"]
        price_kwh_dkk = price_mwh_dkk / 1000.0
        return HourlyPrice(start=start, price_kwh_dkk=price_kwh_dkk, co2_emission=None)

    # Sort hourly prices by datetime (first entry is closest to current time)
    hourly_prices = sorted([_convert(r) for r in records], key=lambda p: p.start)
    return hourly_prices


def get_energy_prices_bolius() -> List[HourlyPrice]:
    """
    Get the energy prices including tariffs and taxes from Bolius.

    See https://www.bolius.dk/elpriser for more info.

    :return: The hourly energy prices from now until the most recently published price
    """
    endpoint = "https://api.bolius.dk/livedata/v2/type/power"
    price_area = "DK2"  # Price area for Sealand and Copenhagen
    date_start_str = dt.datetime.now().strftime("%Y-%m-%dT%H:00")
    date_end_str = next_datetime_at_hour(dt.datetime.now(), hour=0).strftime("%Y-%m-%dT%H:00")
    url = f"{endpoint}?region={price_area}&co2=1&start={date_start_str}&end={date_end_str}"
    records = requests.get(url).json()["data"]

    def _convert(record: Dict[str, Any]) -> HourlyPrice:
        start = dt.datetime.strptime(record["date"], "%Y-%m-%d") + dt.timedelta(hours=record["hour"])
        price_kwh_dkk = float(record["price"])
        co2_emission = record["co2"]["average"]
        return HourlyPrice(start=start, price_kwh_dkk=price_kwh_dkk, co2_emission=co2_emission)

    # Sort hourly prices by datetime (first entry is closest to current time)
    hourly_prices = sorted([_convert(r) for r in records], key=lambda p: p.start)
    return hourly_prices


async def listen_for_charging_states(easee: Easee, charger: Charger) -> AsyncIterator[str]:
    queue = asyncio.Queue()

    # Query the current charger mode
    current_charging_state: str = (await charger.get_state())["chargerOpMode"]
    print(f"Initial charging state: {current_charging_state}")
    yield current_charging_state

    async def _signalr_callback(_, __, data_id, value):
        if pyeasee.ChargerStreamData(data_id) == pyeasee.ChargerStreamData.state_chargerOpMode:
            new_charging_state = CHARGER_STATUS[value]

            nonlocal current_charging_state
            if new_charging_state != current_charging_state:
                print(f"New charging state: {new_charging_state}")
                current_charging_state = new_charging_state
                await queue.put(new_charging_state)

    await easee.sr_subscribe(charger, _signalr_callback)
    while True:
        yield await queue.get()


async def ged(easee: Easee) -> None:
    # Find the one charger that we intend to control/listen to
    chargers = await easee.get_chargers()
    if len(chargers) != 1:
        raise RuntimeError(f"Expected a single charger, got {len(chargers)}")
    charger = chargers[0]

    async for new_charging_state in listen_for_charging_states(easee, charger):
        if new_charging_state == "AWAITING_START":
            charge_state = get_vehicle_charge_state(allow_wakeup=True)
            hourly_prices = get_energy_prices()
            charging_plan = create_charging_plan(charge_state, hourly_prices)
            print(f"New charging plan created: {charging_plan}")
        elif new_charging_state == "DISCONNECTED":
            print("Vehicle not connected to charger - awaiting connection")


def get_vehicle_charge_state(allow_wakeup: bool = False) -> VehicleChargeState:
    with teslapy.Tesla('mathias.stokholm@gmail.com') as tesla:
        vehicles = tesla.vehicle_list()
        if len(vehicles) != 1:
            raise RuntimeError(f"Expected a single vehicle, got {len(vehicles)}")
        vehicle = vehicles[0]
        if vehicle["state"] == "asleep":
            if allow_wakeup:
                print(f"WARNING: Waking up car to get battery level")
                vehicle.sync_wake_up()
            else:
                raise RuntimeError("Car is asleep and wakeup wasn't allowed")
        charge_state = vehicle['charge_state']
        battery_level = charge_state['battery_level']
        range_km = charge_state['battery_range'] * MILES_TO_KILOMETERS
        minutes_to_full_charge = charge_state['minutes_to_full_charge']
        return VehicleChargeState(battery_level, range_km, minutes_to_full_charge)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--easee_username", help="The Easee username to use", required=True)
    parser.add_argument("--easee_password", help="The Easee password to use", required=True)
    args = parser.parse_args()

    easee = Easee(args.easee_username, args.easee_password)
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(ged(easee))
    except KeyboardInterrupt:
        print(f"Quitting due to keyboard interrupt")
    finally:
        loop.run_until_complete(easee.close())


if __name__ == "__main__":
    main()
