import asyncio
from typing import AsyncIterator, Optional, List

from pyeasee import Easee
import argparse

import pyeasee
from pyeasee.charger import STATUS as CHARGER_STATUS, Charger
import teslapy
import datetime as dt

from ladning.constants import BATTERY_CAPACITY_KWH, CHARGING_KW, MILES_TO_KILOMETERS
from ladning.energy_prices import get_energy_prices
from ladning.types import VehicleChargeState, ChargingPlan, HourlyPrice


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
