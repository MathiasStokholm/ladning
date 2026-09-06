import asyncio
import datetime as dt

import pytest
from pyeasee.exceptions import BadRequestException

from main import _charging_state_from_observations, _resume_charger, schedule_charge
from ladning.types import ChargingPlan


def test_charging_state_from_observations() -> None:
    observations = {"observations": [{"id": 109, "value": 3}]}

    assert _charging_state_from_observations(observations) == "CHARGING"


def test_charging_state_from_observations_requires_operation_mode() -> None:
    with pytest.raises(RuntimeError, match="was not returned"):
        _charging_state_from_observations({"observations": []})


def test_charging_state_from_observations_rejects_unknown_mode() -> None:
    with pytest.raises(RuntimeError, match="Unknown charger operation mode"):
        _charging_state_from_observations({"observations": [{"id": 109, "value": 999}]})


def test_resume_charger_ignores_disconnected_charger() -> None:
    class DisconnectedCharger:
        async def resume(self) -> None:
            raise BadRequestException({"errorCodeName": "ChargerDisconnected"})

    asyncio.run(_resume_charger(DisconnectedCharger()))


def test_schedule_charge_continues_when_charger_is_disconnected_during_resume() -> None:
    class Response:
        ok = True

    class DisconnectedCharger:
        def __init__(self) -> None:
            self.plan_set = False

        async def resume(self) -> None:
            raise BadRequestException({"errorCodeName": "ChargerDisconnected"})

        async def set_basic_charge_plan(self, **_: object) -> Response:
            self.plan_set = True
            return Response()

    charger = DisconnectedCharger()
    plan = ChargingPlan(
        start_time=dt.datetime.now().astimezone() + dt.timedelta(minutes=10),
        end_time=dt.datetime.now().astimezone() + dt.timedelta(hours=1),
        battery_start=50,
        battery_end=80,
        total_cost_dkk=1.0,
        range_added_km=10.0,
    )

    asyncio.run(schedule_charge(charger, plan))

    assert charger.plan_set
