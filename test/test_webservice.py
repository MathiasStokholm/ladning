from typing import List, Optional, Callable

import datetime as dt

import pytest
import requests

from ladning.types import Price, ChargingPlan, ChargingRequest, ChargingRequestResponse, VehicleState
from ladning.webservice import LadningService

# Use any free port for web services
FREE_PORT = 0
HOST_ADDRESS = "127.0.0.1"  # This has to be an IPv4 address for webservice to not break


@pytest.fixture
def price_getter() -> Callable[[], List[Price]]:
    def fg() -> List[Price]:
        now = dt.datetime.now().astimezone()
        return [Price(start=now + dt.timedelta(hours=i), price_kwh_dkk=1.0 + i) for i in range(24)]
    return fg

@pytest.fixture
def charging_plan_getter() -> Callable[[], Optional[ChargingPlan]]:
    def fg() -> Optional[ChargingPlan]:
        return None
    return fg

@pytest.fixture()
def charging_request_setter() -> Callable[[ChargingRequest], ChargingRequestResponse]:
    def fg(req: ChargingRequest) -> ChargingRequestResponse:
        return ChargingRequestResponse(success=True, reason="", plan=None)
    return fg


# New simple vehicle state getter for tests
@pytest.fixture()
def vehicle_state_getter() -> Callable[[], VehicleState]:
    return lambda: VehicleState(connected=True, charge_level=42)

def test_webservice_query(price_getter: Callable[[], List[Price]],
                          charging_plan_getter: Callable[[], Optional[ChargingPlan]],
                          charging_request_setter: Callable[[ChargingRequest], ChargingRequestResponse],
                          vehicle_state_getter: Callable[[], VehicleState]) -> None:
    service = LadningService(host=HOST_ADDRESS, port=FREE_PORT,
                             electricity_price_getter=price_getter,
                             charging_plan_getter=charging_plan_getter,
                             charging_request_setter=charging_request_setter,
                             vehicle_state_getter=vehicle_state_getter)
    service.start()
    try:
        resp = requests.get(f"{service.endpoint}/electricity")
        assert resp.status_code == 200
        data = resp.json()
        assert "prices" in data
        assert "charging_plan" in data
        assert "vehicle_state" in data
        # spot check structure
        vs = data["vehicle_state"]
        assert isinstance(vs, dict)
        assert "connected" in vs
        assert "charge_level" in vs
    finally:
        service.stop()