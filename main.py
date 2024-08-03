import asyncio
from typing import AsyncIterator

from pyeasee import Easee
import argparse

import pyeasee
from pyeasee.charger import STATUS as CHARGER_STATUS, Charger

from ladning.charging_plan import create_charging_plan
from ladning.energy_prices import get_energy_prices
from ladning.vehicle_query import get_vehicle_charge_state


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


async def smart_charge(easee: Easee) -> None:
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--easee_username", help="The Easee username to use", required=True)
    parser.add_argument("--easee_password", help="The Easee password to use", required=True)
    args = parser.parse_args()

    easee = Easee(args.easee_username, args.easee_password)
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(smart_charge(easee))
    except KeyboardInterrupt:
        print(f"Quitting due to keyboard interrupt")
    finally:
        loop.run_until_complete(easee.close())


if __name__ == "__main__":
    main()