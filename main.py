import asyncio
from typing import AsyncIterator, Tuple, Optional, List
import datetime as dt

from pyeasee import Easee
import argparse
import teslapy

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

import pyeasee
from pyeasee.charger import STATUS as CHARGER_STATUS, Charger

from ladning.charging_plan import create_charging_plan
from ladning.energy_prices import get_energy_prices
from ladning.logging import log
from ladning.types import ChargingPlan, HourlyPrice, VehicleChargeState, ChargingRequest, ChargingRequestResponse
from ladning.vehicle_query import get_vehicle_charge_state

from ladning.webservice import LadningService


class ApplicationState:
    def __init__(self, easee: Easee, tesla: teslapy.Tesla, hourly_prices: List[HourlyPrice]) -> None:
        self._easee = easee
        self._tesla = tesla
        self._hourly_prices = hourly_prices
        self._vehicle_charge_state: Optional[VehicleChargeState] = None
        self._charging_plan: Optional[ChargingPlan] = None
        self._charger: Optional[Charger] = None
        self._event_loop = asyncio.get_running_loop()

    async def get_charger(self) -> Charger:
        if self._charger is None:
            # Find the one charger that we intend to control/listen to
            chargers = await self._easee.get_chargers()
            if len(chargers) != 1:
                raise RuntimeError(f"Expected a single charger, got {len(chargers)}")
            self._charger = chargers[0]
        return self._charger

    def get_hourly_prices(self) -> List[HourlyPrice]:
        return self._hourly_prices

    def get_charging_plan(self) -> Optional[ChargingPlan]:
        return self._charging_plan

    async def smart_charge(self) -> None:
        async for previous_state, new_state in listen_for_charging_states(self._easee, await self.get_charger()):
            if new_state == "DISCONNECTED":
                # If vehicle was disconnected, cancel any existing charging plan
                log.info("Vehicle disconnected - cancelling charging plan")
                await self.cancel_charging()
                continue

            # If previous state was None (app just started) or disconnected, consider whether to perform planning
            app_just_launched = previous_state is None
            if app_just_launched or previous_state == "DISCONNECTED":
                # Plan if charger is ready to charge, awaiting a schedule or already started charging
                perform_planning = new_state == "READY_TO_CHARGE" or \
                                   new_state == "AWAITING_START" or \
                                   new_state == "CHARGING"

                if perform_planning:
                    self._vehicle_charge_state = get_vehicle_charge_state(self._tesla, allow_wakeup=True)
                    await self.plan_charging()

    async def plan_charging(self):
        if self._vehicle_charge_state is None:
            log.info("Skipping planning due to no vehicle charge state information")
            return

        new_charging_plan = create_charging_plan(self._vehicle_charge_state, self._hourly_prices)
        if new_charging_plan == self._charging_plan:
            log.info("Charging plan unchanged")
            return

        # Put new charging plan into effect
        if self._charging_plan is None:
            log.info(f"Car already at target battery level, no plan will be scheduled")
        else:
            await schedule_charge(await self.get_charger(), new_charging_plan)
            log.info(f"New charging plan scheduled: {new_charging_plan}")
        self._charging_plan = new_charging_plan

    async def cancel_charging(self) -> None:
        """
        Cancel any existing charging plan
        """
        charger = await self.get_charger()
        previous_plan = await charger.get_basic_charge_plan()
        if previous_plan is None:
            log.info("No plan to cancel")
        else:
            await charger.delete_basic_charge_plan()
            log.info("Charging plan cancelled")
        self._charging_plan = None

    async def on_new_hourly_prices(self, hourly_prices: List[HourlyPrice]) -> None:
        log.info("New hourly prices received")
        if hourly_prices == self._hourly_prices:
            log.info("New hourly prices were unchanged, skipping handling")
            return

        log.info(f"New hourly prices: {hourly_prices}")
        log.info("Checking if charging plan should be revised")
        self._hourly_prices = hourly_prices
        await self.plan_charging()

    async def on_charging_request(self, request: ChargingRequest) -> ChargingRequestResponse:
        log.info(f"Received charging request: {request}")
        return ChargingRequestResponse(False, "Charging requests not supported yet")

    def on_charging_request_sync(self, request: ChargingRequest) -> ChargingRequestResponse:
        async def _call() -> ChargingRequestResponse:
            return await self.on_charging_request(request)

        future = asyncio.run_coroutine_threadsafe(_call(), self._event_loop)
        return future.result()


async def listen_for_charging_states(easee: Easee, charger: Charger) -> AsyncIterator[Tuple[Optional[str], str]]:
    queue = asyncio.Queue()

    # Query the current charger mode
    current_charging_state: str = (await charger.get_state())["chargerOpMode"]
    log.info(f"Initial charging state: {current_charging_state}")
    yield None, current_charging_state

    async def _signalr_callback(_, __, data_id, value):
        if pyeasee.ChargerStreamData(data_id) == pyeasee.ChargerStreamData.state_chargerOpMode:
            new_charging_state = CHARGER_STATUS[value]

            nonlocal current_charging_state
            if new_charging_state != current_charging_state:
                log.info(f"New charging state: {new_charging_state}")
                await queue.put((current_charging_state, new_charging_state))
                current_charging_state = new_charging_state

    await easee.sr_subscribe(charger, _signalr_callback)
    while True:
        yield await queue.get()


async def schedule_charge(charger: Charger, charging_plan: ChargingPlan) -> None:
    def _format(d: dt.datetime):
        # Convert to UTC - required by Easee API
        return d.astimezone(dt.timezone.utc).isoformat(timespec='milliseconds').replace("+00:00", "Z")

    response = await charger.set_basic_charge_plan(id=42,  # Unsure what ID to use here
                                                   chargeStartTime=_format(charging_plan.start_time),
                                                   chargeStopTime=_format(charging_plan.end_time),
                                                   repeat=False,
                                                   isEnabled=True)
    if not response.ok:
        raise RuntimeError(f"Scheduling charge failed: '{response.reason}' (code {response.status})")


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tesla_username", help="The Tesla username to use", required=True)
    parser.add_argument("--easee_username", help="The Easee username to use", required=True)
    parser.add_argument("--easee_password", help="The Easee password to use", required=True)
    parser.add_argument("--webservice_port", help="The port to use for the webservice", default=5042)
    args = parser.parse_args()

    # Connect to Easee charger and log in
    easee = Easee(args.easee_username, args.easee_password)

    # Connect to Tesla API
    tesla = teslapy.Tesla(args.tesla_username)

    # Create application state to tie together different pieces of the app
    state = ApplicationState(easee, tesla, get_energy_prices())

    # Start the webservice used to query and control charging on a worker thread
    webservice = LadningService(host="0.0.0.0", port=args.webservice_port,
                                electricity_price_getter=state.get_hourly_prices,
                                charging_plan_getter=state.get_charging_plan,
                                charging_request_setter=state.on_charging_request_sync)
    webservice.start()

    # Create a scheduler that will query new energy prices every day at 13:00 local time
    scheduler = AsyncIOScheduler()

    async def _try_update_prices():
        try:
            prices = get_energy_prices()
            await state.on_new_hourly_prices(prices)
        except Exception as e:
            log.error(f"Error while loading new energy prices: '{e}'")

    scheduler.add_job(_try_update_prices, CronTrigger(hour=13, timezone=dt.datetime.now().astimezone().tzinfo))
    scheduler.start()

    # Run the main smart charging loop
    try:
        await state.smart_charge()
    except:
        log.warning(f"Quitting due to keyboard interrupt or error")
        raise
    finally:
        # Clean up
        await easee.close()
        tesla.close()
        webservice.stop()
        log.info("Web service shut down")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
