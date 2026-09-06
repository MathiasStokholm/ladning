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


def test_resume_charger_retries_after_disconnected_charger(monkeypatch: pytest.MonkeyPatch) -> None:
    class DisconnectedCharger:
        def __init__(self) -> None:
            self.resume_attempts = 0

        async def resume(self) -> None:
            self.resume_attempts += 1
            if self.resume_attempts == 1:
                raise BadRequestException({"errorCodeName": "ChargerDisconnected"})

    async def no_sleep(_: float) -> None:
        pass

    monkeypatch.setattr("main.RESUME_RETRY_ATTEMPTS", 2)
    monkeypatch.setattr("main.asyncio.sleep", no_sleep)
    charger = DisconnectedCharger()

    asyncio.run(_resume_charger(charger))

    assert charger.resume_attempts == 2


def test_resume_charger_stops_after_unplugging(monkeypatch: pytest.MonkeyPatch) -> None:
    class DisconnectedCharger:
        async def resume(self) -> None:
            raise BadRequestException({"errorCodeName": "ChargerDisconnected"})

    async def no_sleep(_: float) -> None:
        pass

    monkeypatch.setattr("main.RESUME_RETRY_ATTEMPTS", 2)
    monkeypatch.setattr("main.asyncio.sleep", no_sleep)

    with pytest.raises(RuntimeError, match="remained disconnected"):
        asyncio.run(_resume_charger(DisconnectedCharger()))


def test_schedule_charge_sets_plan_before_resuming() -> None:
    class Response:
        ok = True

    class Charger:
        def __init__(self) -> None:
            self.actions: list[str] = []

        async def resume(self) -> None:
            self.actions.append("resume")

        async def set_basic_charge_plan(
            self,
            id: int,
            chargeStartTime: str,
            chargeStopTime: str | None,
            repeat: bool,
            isEnabled: bool,
        ) -> Response:
            self.actions.append("set_plan")
            return Response()

    charger = Charger()
    plan = ChargingPlan(
        start_time=dt.datetime.now().astimezone() + dt.timedelta(minutes=10),
        end_time=dt.datetime.now().astimezone() + dt.timedelta(hours=1),
        battery_start=50,
        battery_end=80,
        total_cost_dkk=1.0,
        range_added_km=10.0,
    )

    asyncio.run(schedule_charge(charger, plan))

    assert charger.actions == ["set_plan", "resume"]
